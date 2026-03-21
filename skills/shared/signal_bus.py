import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional, List


@dataclass
class EmotionSignal:
    source: str
    emotion: str
    confidence: float
    detail: str
    timestamp: float


@dataclass
class UserState:
    mood_score: float = 0.0
    visual_signal: Optional[dict] = None
    voice_content: Optional[str] = None
    voice_emotion: Optional[dict] = None
    env_audio: Optional[dict] = None
    behavior: Optional[str] = None
    last_interaction: float = 0.0
    last_proactive: float = 0.0
    session_start: float = 0.0
    mood_history: List[float] = field(default_factory=list)
    cat_state: str = "neutral_idle"

    def to_prompt_context(self):
        lines = []
        if self.visual_signal:
            s = self.visual_signal
            lines.append(f"[visual] {s.get('detail','')} (emotion: {s.get('emotion','')}, conf: {s.get('confidence',0):.2f})")
        if self.voice_content:
            lines.append(f"[voice] user said: \"{self.voice_content}\"")
        if self.voice_emotion:
            s = self.voice_emotion
            lines.append(f"[voice_emotion] {s.get('detail','')} ({s.get('emotion','')}, conf: {s.get('confidence',0):.2f})")
        if self.env_audio:
            s = self.env_audio
            lines.append(f"[env_audio] {s.get('detail','')}")
        if self.behavior:
            lines.append(f"[behavior] {self.behavior}")
        if self.last_interaction > 0:
            mins = (time.time() - self.last_interaction) / 60
            lines.append(f"[last_user_msg] {mins:.0f} min ago")
        if self.last_proactive > 0:
            mins = (time.time() - self.last_proactive) / 60
            lines.append(f"[last_agent_proactive] {mins:.0f} min ago")
        if len(self.mood_history) >= 3:
            recent = self.mood_history[-3:]
            trend = "declining" if recent[-1] < recent[0] else "improving" if recent[-1] > recent[0] else "stable"
            lines.append(f"[mood_trend] {trend} (recent: {', '.join(f'{s:.2f}' for s in recent)})")
        return "\n".join(lines)


class SignalBus:
    def __init__(self):
        self._state = UserState(session_start=time.time())
        self._lock = threading.Lock()

    def update_signal(self, signal: EmotionSignal):
        with self._lock:
            d = {"emotion": signal.emotion, "confidence": signal.confidence, "detail": signal.detail}
            if signal.source == "camera":
                self._state.visual_signal = d
            elif signal.source == "voice_emotion":
                self._state.voice_emotion = d
            elif signal.source == "env_audio":
                self._state.env_audio = d
            self._recalc()
            self._state.mood_history.append(self._state.mood_score)
            if len(self._state.mood_history) > 100:
                self._state.mood_history = self._state.mood_history[-100:]

    def update_voice_content(self, text):
        with self._lock:
            self._state.voice_content = text
            self._state.last_interaction = time.time()

    def update_behavior(self, desc):
        with self._lock:
            self._state.behavior = desc

    def mark_proactive(self):
        with self._lock:
            self._state.last_proactive = time.time()

    def set_cat_state(self, state):
        with self._lock:
            self._state.cat_state = state

    def get_state(self):
        with self._lock:
            return UserState(
                mood_score=self._state.mood_score,
                visual_signal=self._state.visual_signal,
                voice_content=self._state.voice_content,
                voice_emotion=self._state.voice_emotion,
                env_audio=self._state.env_audio,
                behavior=self._state.behavior,
                last_interaction=self._state.last_interaction,
                last_proactive=self._state.last_proactive,
                session_start=self._state.session_start,
                mood_history=list(self._state.mood_history),
                cat_state=self._state.cat_state,
            )

    def _recalc(self):
        emap = {"positive": 0.7, "neutral": 0.0, "negative": -0.7, "tired": -0.4, "anxious": -0.6}
        scores, weights = [], []
        for sig, w in [(self._state.visual_signal, 0.3), (self._state.voice_emotion, 0.35), (self._state.env_audio, 0.15)]:
            if sig:
                s = emap.get(sig.get("emotion", ""), 0.0)
                c = sig.get("confidence", 0.5)
                scores.append(s)
                weights.append(w * c)
        if scores and sum(weights) > 0:
            self._state.mood_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)


bus = SignalBus()
