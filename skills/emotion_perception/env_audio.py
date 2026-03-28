"""
env_audio.py - Environment audio classification for v3 architecture.

Design goals:
- Prefer PANNs for non-speech sound classification.
- Degrade gracefully to lightweight librosa heuristics when dependencies are
  not available.
- Normalize to project emotion set and write canonical EventStore events.
"""

from __future__ import annotations

import math
import os
import tempfile
import time
import wave
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from skills.shared.event_store import store


@dataclass
class EnvAudioResult:
    labels: List[str]
    confidence: float
    mapped_emotion: str
    db: float
    backend: str


class EnvAudioDetector:
    NEGATIVE_SOUNDS = {
        "thunder",
        "thunderstorm",
        "dog",
        "dog_bark",
        "bark",
        "siren",
        "drill",
        "jackhammer",
        "construction_noise",
        "explosion",
        "alarm",
        "crying",
        "baby_cry",
        "chainsaw",
        "gunshot",
    }

    POSITIVE_SOUNDS = {
        "music",
        "singing",
        "laughter",
        "laughing",
        "purr",
        "birds",
        "birdsong",
        "applause",
        "street_music",
        "children_playing",
    }

    LOCAL_PANNS_CKPT = "/opt/catagent/models/panns/Cnn14_mAP=0.431.pth"
    LOCAL_URBAN_SOUND_MODEL = "/opt/catagent/models/urbansound8k_ecapa"

    def __init__(self, min_confidence: float = 0.45, emit_cooldown_sec: float = 8.0):
        self.min_confidence = min_confidence
        self.emit_cooldown_sec = emit_cooldown_sec

        self._audio_tagging = None
        self._sb_classifier = None
        self._labels = None
        self._librosa = None
        self._last_emit_time = 0.0
        self._last_emit_signature: Optional[Tuple[str, int]] = None

    def _load_panns(self) -> bool:
        if self._audio_tagging is not None:
            return True
        try:
            from panns_inference import AudioTagging, labels

            if not os.path.exists(self.LOCAL_PANNS_CKPT) or os.path.getsize(self.LOCAL_PANNS_CKPT) < 300 * 1024 * 1024:
                print(
                    "[EnvAudio] local PANNs checkpoint missing. "
                    "Please run: python3 models/download_pretrained_models.py --only panns"
                )
                return False

            self._audio_tagging = AudioTagging(device="cpu", checkpoint_path=self.LOCAL_PANNS_CKPT)
            self._labels = labels
            print("[EnvAudio] PANNs loaded")
            return True
        except Exception as e:
            print(f"[EnvAudio] PANNs unavailable, fallback to librosa: {e}")
            self._audio_tagging = None
            return False

    def _load_urbansound(self) -> bool:
        if self._sb_classifier is not None:
            return True
        if not os.path.isdir(self.LOCAL_URBAN_SOUND_MODEL):
            return False
        try:
            import torchaudio
            import huggingface_hub

            # Compatibility shim for newer torchaudio builds.
            if not hasattr(torchaudio, "list_audio_backends"):
                torchaudio.list_audio_backends = lambda: ["soundfile"]
            if not hasattr(torchaudio, "set_audio_backend"):
                torchaudio.set_audio_backend = lambda backend: None

            # Compatibility shim for SpeechBrain expecting old hf_hub_download arg.
            _orig_hf_hub_download = huggingface_hub.hf_hub_download

            def _hf_hub_download_compat(*args, **kwargs):
                if "use_auth_token" in kwargs and "token" not in kwargs:
                    kwargs["token"] = kwargs.pop("use_auth_token")
                else:
                    kwargs.pop("use_auth_token", None)
                return _orig_hf_hub_download(*args, **kwargs)

            huggingface_hub.hf_hub_download = _hf_hub_download_compat

            from speechbrain.inference.classifiers import EncoderClassifier

            self._sb_classifier = EncoderClassifier.from_hparams(
                source=self.LOCAL_URBAN_SOUND_MODEL,
                savedir=self.LOCAL_URBAN_SOUND_MODEL,
                overrides={"pretrained_path": self.LOCAL_URBAN_SOUND_MODEL},
                run_opts={"device": "cpu"},
            )
            print("[EnvAudio] UrbanSound8K model loaded")
            return True
        except Exception as e:
            print(f"[EnvAudio] UrbanSound8K unavailable: {e}")
            self._sb_classifier = None
            return False

    def _load_librosa(self) -> bool:
        if self._librosa is not None:
            return True
        try:
            import librosa

            self._librosa = librosa
            return True
        except Exception as e:
            print(f"[EnvAudio] librosa unavailable: {e}")
            return False

    @staticmethod
    def _normalize_label(label: str) -> str:
        return (label or "").strip().lower().replace(" ", "_")

    def _map_emotion(self, label: str) -> str:
        l = self._normalize_label(label)
        if l in self.NEGATIVE_SOUNDS:
            return "negative"
        if l in self.POSITIVE_SOUNDS:
            return "positive"
        return "neutral"

    def _materialize_audio_input(
        self,
        audio_input: Union[str, "numpy.ndarray"],
        sample_rate: int,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Return (audio_path, temp_path_to_cleanup)."""
        if isinstance(audio_input, str):
            return audio_input, None

        try:
            import numpy as np
        except Exception:
            return None, None

        if not isinstance(audio_input, np.ndarray):
            return None, None

        arr = audio_input
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        arr = arr.astype(np.float32)
        peak = float(np.max(np.abs(arr))) if arr.size else 0.0
        if peak > 1.0:
            arr = arr / (peak + 1e-9)
        pcm = (arr * 32767.0).astype(np.int16)

        fd, path = tempfile.mkstemp(prefix="env_audio_", suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(int(sample_rate))
            wf.writeframes(pcm.tobytes())
        return path, path

    def _db_from_signal(self, y) -> float:
        if y is None or len(y) == 0:
            return 0.0
        rms = math.sqrt(sum(float(v) * float(v) for v in y) / max(len(y), 1))
        return 20.0 * math.log10(rms + 1e-6)

    def _predict_with_panns(self, audio_path: str) -> Optional[EnvAudioResult]:
        if not self._load_panns() or not self._load_librosa():
            return None

        try:
            y, sr = self._librosa.load(audio_path, sr=32000, mono=True)
            clipwise_output, _ = self._audio_tagging.inference(y)
            scores = clipwise_output[0]
            top_idx = int(scores.argmax())
            top_conf = float(scores[top_idx])

            topk_idx = scores.argsort()[-3:][::-1]
            labels = [self._normalize_label(self._labels[int(i)]) for i in topk_idx]
            mapped = self._map_emotion(labels[0])
            db = self._db_from_signal(y)
            return EnvAudioResult(labels=labels, confidence=top_conf, mapped_emotion=mapped, db=db, backend="panns")
        except Exception as e:
            print(f"[EnvAudio] PANNs inference failed: {e}")
            return None

    def _predict_with_urbansound(self, audio_path: str) -> Optional[EnvAudioResult]:
        if not self._load_urbansound() or not self._load_librosa():
            return None

        try:
            import torch

            wav, _sr = self._librosa.load(audio_path, sr=16000, mono=True)
            wav_tensor = torch.tensor(wav, dtype=torch.float32).unsqueeze(0)
            wav_lens = torch.tensor([1.0], dtype=torch.float32)

            out_prob, score, index, text_lab = self._sb_classifier.classify_batch(wav_tensor, wav_lens)
            if isinstance(text_lab, (list, tuple)) and text_lab:
                first = text_lab[0]
                if isinstance(first, (list, tuple)) and first:
                    raw_label = str(first[0])
                else:
                    raw_label = str(first)
            else:
                raw_label = str(text_lab)

            top_label = self._normalize_label(raw_label)
            conf = float(score.item()) if hasattr(score, "item") else float(score)

            db = self._db_from_signal(wav)

            return EnvAudioResult(
                labels=[top_label],
                confidence=max(0.0, min(1.0, conf)),
                mapped_emotion=self._map_emotion(top_label),
                db=db,
                backend="urbansound8k_ecapa",
            )
        except Exception as e:
            print(f"[EnvAudio] UrbanSound8K inference failed: {e}")
            return None

    def _predict_with_librosa(self, audio_path: str) -> EnvAudioResult:
        if not self._load_librosa():
            return EnvAudioResult(
                labels=["unknown"],
                confidence=0.0,
                mapped_emotion="neutral",
                db=0.0,
                backend="none",
            )

        y, sr = self._librosa.load(audio_path, sr=16000, mono=True)
        if y.size == 0:
            return EnvAudioResult(["silence"], 0.5, "neutral", 0.0, "librosa_fallback")

        rms = float(self._librosa.feature.rms(y=y).mean())
        centroid = float(self._librosa.feature.spectral_centroid(y=y, sr=sr).mean())
        zcr = float(self._librosa.feature.zero_crossing_rate(y).mean())
        db = self._db_from_signal(y)

        # Fallback rules for coarse environment awareness.
        if rms > 0.055 and centroid > 2600:
            label, conf = "drill", 0.62
        elif rms > 0.030 and 900 < centroid < 2200 and zcr > 0.08:
            label, conf = "dog_bark", 0.60
        elif rms > 0.020 and 700 < centroid < 1800 and zcr < 0.08:
            label, conf = "music", 0.58
        elif rms < 0.008:
            label, conf = "quiet_room", 0.70
        else:
            label, conf = "ambient_noise", 0.52

        return EnvAudioResult(
            labels=[label],
            confidence=conf,
            mapped_emotion=self._map_emotion(label),
            db=db,
            backend="librosa_fallback",
        )

    def analyze(
        self,
        audio_input: Union[str, "numpy.ndarray"],
        sample_rate: int = 16000,
    ) -> EnvAudioResult:
        audio_path, temp_file = self._materialize_audio_input(audio_input, sample_rate)
        if not audio_path or not os.path.exists(audio_path):
            return EnvAudioResult(["missing_file"], 0.0, "neutral", 0.0, "none")

        try:
            result = self._predict_with_urbansound(audio_path)
            if result is not None:
                return result

            result = self._predict_with_panns(audio_path)
            if result is not None:
                return result
            return self._predict_with_librosa(audio_path)
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def emit_event(self, result: EnvAudioResult) -> bool:
        if result.confidence < self.min_confidence:
            return False

        now = time.time()
        top_label = result.labels[0] if result.labels else "unknown"
        topk = ", ".join(result.labels[:3]) if result.labels else top_label
        signature = (top_label, int(result.db // 3))
        if (
            self._last_emit_signature == signature
            and now - self._last_emit_time < self.emit_cooldown_sec
        ):
            return False

        store.add_simple(
            source="env_audio",
            content=(
                f"detected: {top_label} (top3: {topk}, "
                f"volume: {result.db:.0f}dB, backend: {result.backend})"
            ),
            emotion=result.mapped_emotion,
            confidence=result.confidence,
        )
        self._last_emit_signature = signature
        self._last_emit_time = now
        return True

    def analyze_and_store(
        self,
        audio_input: Union[str, "numpy.ndarray"],
        sample_rate: int = 16000,
    ) -> EnvAudioResult:
        result = self.analyze(audio_input, sample_rate=sample_rate)
        self.emit_event(result)
        return result


_default_detector: Optional[EnvAudioDetector] = None


def _get_default_detector() -> EnvAudioDetector:
    global _default_detector
    if _default_detector is None:
        _default_detector = EnvAudioDetector()
    return _default_detector


def analyze_env_audio(
    audio_input: Union[str, "numpy.ndarray"],
    sample_rate: int = 16000,
) -> EnvAudioResult:
    detector = _get_default_detector()
    return detector.analyze_and_store(audio_input, sample_rate=sample_rate)
