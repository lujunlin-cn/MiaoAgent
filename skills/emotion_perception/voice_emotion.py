"""
voice_emotion.py - Voice emotion perception for v3 architecture.

Design goals:
- Prefer emotion2vec (FunASR/ModelScope) when available.
- Degrade gracefully to a lightweight librosa-based classifier on ARM64 or
  environments where emotion2vec is not installable.
- Normalize outputs to the system emotion set:
  positive / neutral / negative / tired / anxious
- Write events via EventStore using the canonical add_simple interface.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
import wave
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

from skills.shared.event_store import store


@dataclass
class VoiceEmotionResult:
    raw_emotion: str
    mapped_emotion: str
    confidence: float
    backend: str
    detail: str


class _LibrosaFallbackClassifier:
    """A tiny heuristic classifier used when emotion2vec is unavailable."""

    def __init__(self):
        self._librosa = None

    def _load(self) -> bool:
        if self._librosa is None:
            try:
                import librosa

                self._librosa = librosa
            except Exception as e:
                print(f"[VoiceEmotion] librosa unavailable: {e}")
                return False
        return True

    def predict(self, audio_path: str) -> Tuple[str, float, Dict[str, float]]:
        if not self._load():
            return "neutral", 0.5, {}

        y, sr = self._librosa.load(audio_path, sr=16000, mono=True)
        if y.size == 0:
            return "neutral", 0.5, {}

        rms = float(self._librosa.feature.rms(y=y).mean())
        zcr = float(self._librosa.feature.zero_crossing_rate(y).mean())
        centroid = float(self._librosa.feature.spectral_centroid(y=y, sr=sr).mean())

        onset_env = self._librosa.onset.onset_strength(y=y, sr=sr)
        tempo = float(self._librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]) if onset_env.size else 0.0

        feats = {
            "rms": rms,
            "zcr": zcr,
            "centroid": centroid,
            "tempo": tempo,
        }

        # Simple, explainable rules as temporary fallback.
        if rms < 0.012 and tempo < 62:
            return "tired", 0.58, feats
        if rms < 0.015 and tempo < 75:
            return "sad", 0.62, feats
        if rms > 0.040 and centroid > 2200 and tempo > 95:
            return "angry", 0.66, feats
        if rms > 0.020 and tempo > 100 and 1200 < centroid < 2600:
            return "happy", 0.61, feats

        return "neutral", 0.52, feats


class VoiceEmotionDetector:
    """Analyze voice emotion from audio files and write standardized events."""

    # Normalize raw labels into system-wide labels.
    EMOTION_MAP = {
        "happy": "positive",
        "happiness": "positive",
        "excited": "positive",
        "开心": "positive",
        "高兴": "positive",
        "愉快": "positive",
        "joy": "positive",
        "surprise": "positive",
        "惊喜": "positive",
        "neutral": "neutral",
        "平静": "neutral",
        "中性": "neutral",
        "calm": "neutral",
        "sad": "negative",
        "悲伤": "negative",
        "沮丧": "negative",
        "angry": "negative",
        "anger": "negative",
        "生气": "negative",
        "愤怒": "negative",
        "disgust": "negative",
        "fear": "anxious",
        "害怕": "anxious",
        "紧张": "anxious",
        "焦虑": "anxious",
        "anxious": "anxious",
        "nervous": "anxious",
        "tired": "tired",
        "疲惫": "tired",
        "困倦": "tired",
        "fatigue": "tired",
    }

    LOCAL_MODEL_CANDIDATES = [
        "/opt/catagent/models/emotion2vec_plus_large",
        "/opt/catagent/models/emotion2vec_base",
    ]

    def __init__(
        self,
        min_confidence: float = 0.45,
        emit_cooldown_sec: float = 8.0,
        prefer_emotion2vec: bool = True,
    ):
        self.min_confidence = min_confidence
        self.emit_cooldown_sec = emit_cooldown_sec
        self.prefer_emotion2vec = prefer_emotion2vec

        self._emo_model = None
        self._fallback = _LibrosaFallbackClassifier()
        self._last_emit_time = 0.0
        self._last_emit_signature: Optional[Tuple[str, int]] = None

    def _load_emotion2vec(self) -> bool:
        if not self.prefer_emotion2vec:
            return False

        if self._emo_model is not None:
            return True

        try:
            from funasr import AutoModel

            for model_path in self.LOCAL_MODEL_CANDIDATES:
                if os.path.isdir(model_path):
                    try:
                        self._emo_model = AutoModel(model=model_path)
                        print(f"[VoiceEmotion] emotion2vec loaded from local path: {model_path}")
                        return True
                    except Exception:
                        continue

            # Prefer larger pretrained checkpoint and fallback to lighter one.
            for model_id in ("iic/emotion2vec_plus_large", "iic/emotion2vec_base"):
                try:
                    self._emo_model = AutoModel(model=model_id)
                    print(f"[VoiceEmotion] emotion2vec loaded: {model_id}")
                    return True
                except Exception:
                    continue
            raise RuntimeError("no usable emotion2vec model id")
        except Exception as e:
            print(f"[VoiceEmotion] emotion2vec unavailable, fallback to librosa: {e}")
            self._emo_model = None
            return False

    @staticmethod
    def _normalize_label(raw_label: str) -> str:
        label = (raw_label or "").strip().lower().replace("-", "_").replace(" ", "_")
        return label

    @staticmethod
    def _split_label_candidates(raw_label: str) -> list[str]:
        text = (raw_label or "").strip()
        if not text:
            return []

        parts = re.split(r"[/|,，;；]+", text)
        candidates = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            candidates.append(part)
            normalized = part.lower().replace("-", "_").replace(" ", "_")
            if normalized != part:
                candidates.append(normalized)

        normalized_text = text.lower().replace("-", "_").replace(" ", "_")
        if normalized_text and normalized_text not in candidates:
            candidates.append(normalized_text)
        return candidates

    def _extract_label_score(self, item: dict) -> Tuple[str, float]:
        label = item.get("label") or item.get("emotion") or item.get("text") or "neutral"
        score = item.get("score")
        if score is None:
            score = item.get("confidence")
        if score is None and isinstance(item.get("scores"), (list, tuple)) and item["scores"]:
            labels = item.get("labels") or item.get("label_list") or []
            max_idx = max(range(len(item["scores"])), key=lambda i: float(item["scores"][i]))
            score = float(item["scores"][max_idx])
            if max_idx < len(labels):
                label = labels[max_idx]
        if score is None:
            score = 0.65
        return str(label), float(score)

    def _map_emotion(self, raw_label: str) -> str:
        for candidate in self._split_label_candidates(raw_label):
            mapped = self.EMOTION_MAP.get(candidate)
            if mapped:
                return mapped
            mapped = self.EMOTION_MAP.get(self._normalize_label(candidate))
            if mapped:
                return mapped
        return "neutral"

    def _run_emotion2vec(self, audio_path: str) -> Optional[Tuple[str, float]]:
        if not self._load_emotion2vec():
            return None

        try:
            # FunASR output schemas vary by version; parse defensively.
            out = self._emo_model.generate(input=audio_path)
            if not out:
                return None

            item = out[0] if isinstance(out, list) else out
            if isinstance(item, dict):
                return self._extract_label_score(item)

            if isinstance(item, list) and item and isinstance(item[0], dict):
                return self._extract_label_score(item[0])

            if isinstance(item, str):
                return item, 0.65

            return None
        except Exception as e:
            print(f"[VoiceEmotion] emotion2vec inference failed: {e}")
            return None

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

        fd, path = tempfile.mkstemp(prefix="voice_emotion_", suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(int(sample_rate))
            wf.writeframes(pcm.tobytes())
        return path, path

    def analyze(
        self,
        audio_input: Union[str, "numpy.ndarray"],
        sample_rate: int = 16000,
    ) -> VoiceEmotionResult:
        audio_path, temp_file = self._materialize_audio_input(audio_input, sample_rate)
        if not audio_path or not os.path.exists(audio_path):
            return VoiceEmotionResult(
                raw_emotion="neutral",
                mapped_emotion="neutral",
                confidence=0.0,
                backend="none",
                detail="audio file missing",
            )

        try:
            e2v = self._run_emotion2vec(audio_path)
            if e2v is not None:
                raw, conf = e2v
                mapped = self._map_emotion(raw)
                detail = f"voice sounds {raw}"
                return VoiceEmotionResult(raw, mapped, float(conf), "emotion2vec", detail)

            raw, conf, feats = self._fallback.predict(audio_path)
            mapped = self._map_emotion(raw)
            detail = (
                f"voice sounds {raw}"
                f" (tempo={feats.get('tempo', 0):.0f}, energy={feats.get('rms', 0):.3f})"
                if feats
                else f"voice sounds {raw}"
            )
            return VoiceEmotionResult(raw, mapped, float(conf), "librosa_fallback", detail)
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def emit_event(self, result: VoiceEmotionResult) -> bool:
        now = time.time()
        signature = (result.mapped_emotion, int(result.confidence * 100))

        if result.confidence < self.min_confidence:
            return False

        # De-duplicate near-identical consecutive events.
        if (
            self._last_emit_signature == signature
            and now - self._last_emit_time < self.emit_cooldown_sec
        ):
            return False

        store.add_simple(
            source="voice_emotion",
            content=f"{result.detail}, confidence {result.confidence:.2f}, backend {result.backend}",
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
    ) -> VoiceEmotionResult:
        result = self.analyze(audio_input, sample_rate=sample_rate)
        self.emit_event(result)
        return result


_default_detector: Optional[VoiceEmotionDetector] = None


def _get_default_detector() -> VoiceEmotionDetector:
    global _default_detector
    if _default_detector is None:
        _default_detector = VoiceEmotionDetector()
    return _default_detector


def analyze_voice_emotion(
    audio_input: Union[str, "numpy.ndarray"],
    sample_rate: int = 16000,
) -> VoiceEmotionResult:
    """Convenience API for one-shot analysis and event write."""
    detector = _get_default_detector()
    return detector.analyze_and_store(audio_input, sample_rate=sample_rate)
