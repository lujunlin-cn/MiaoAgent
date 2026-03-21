import time
import threading
import json
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from signal_bus import bus

DECISION_PROMPT = """You are the decision engine for an AI cat companion named MiaoJiang.
Based on the user's multi-modal state signals, decide whether to proactively start a conversation.

Rules:
1. Don't speak just because you detect negative emotion - sometimes people need space
2. Sustained patterns matter more than momentary signals
3. Consider environment - noisy environment might just mean annoyed by noise
4. Late night: gentle reminder only, don't lecture
5. "Not speaking" is also a form of care

Output ONLY JSON:
{"should_speak": true/false, "reason": "why", "strategy": "empathetic_listening/encouragement/distraction/gentle_reminder/silent_comfort", "opener": "suggested opening line in Chinese, cat personality", "cat_state": "concerned/sleepy/sad_empathy/curious/silent_comfort"}"""


class CooldownManager:
    def __init__(self):
        self.min_interval = 30 * 60
        self.silence_until = 0
        self.daily_limit = 10
        self.daily_count = 0
        self.last_reset_day = time.localtime().tm_yday

    def can_speak(self, state):
        now = time.time()
        today = time.localtime().tm_yday
        if today != self.last_reset_day:
            self.daily_count = 0
            self.last_reset_day = today
        if now < self.silence_until:
            return False, f"silent mode, {(self.silence_until - now)/60:.0f} min left"
        if state.last_proactive > 0 and (now - state.last_proactive) < self.min_interval:
            return False, f"cooldown, {(self.min_interval - (now - state.last_proactive))/60:.0f} min left"
        if self.daily_count >= self.daily_limit:
            return False, "daily limit reached"
        return True, "ok"

    def enter_silence(self, hours=2.0):
        self.silence_until = time.time() + hours * 3600

    def record_speak(self):
        self.daily_count += 1


class ProactiveEngine:
    def __init__(self, ollama_url="http://localhost:11434", check_interval=180):
        self.ollama_url = ollama_url
        self.check_interval = check_interval
        self.cooldown = CooldownManager()
        self._running = False
        self._last_decision = None

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        print(f"[ProactiveEngine] started, checking every {self.check_interval}s")

    def stop(self):
        self._running = False

    def get_last_decision(self):
        return self._last_decision

    def _loop(self):
        while self._running:
            time.sleep(self.check_interval)
            try:
                state = bus.get_state()
                decision = self._decide(state)
                self._last_decision = decision
                if decision.get("should_speak"):
                    bus.set_cat_state(decision.get("cat_state", "concerned"))
                    bus.mark_proactive()
                    self.cooldown.record_speak()
                    print(f"[ProactiveEngine] SPEAK: {decision.get('reason','')}")
                    print(f"[ProactiveEngine] opener: {decision.get('opener','')}")
            except Exception as e:
                print(f"[ProactiveEngine] error: {e}")

    def _decide(self, state):
        can, reason = self.cooldown.can_speak(state)
        if not can:
            return {"should_speak": False, "reason": reason}
        if state.mood_score > -0.3:
            return {"should_speak": False, "reason": f"mood {state.mood_score:.2f} is ok"}
        context = state.to_prompt_context()
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": "gemma3:27b",
                    "messages": [
                        {"role": "system", "content": DECISION_PROMPT},
                        {"role": "user", "content": f"Current user state:\n{context}\n\nMake your decision."}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3}
                },
                timeout=30
            )
            content = resp.json()["message"]["content"]
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except Exception as e:
            print(f"[ProactiveEngine] LLM error: {e}")
        return {"should_speak": False, "reason": "decision failed"}
