"""
engine_v2.py — 事件驱动的主动对话决策引擎

核心变更：
- 不再依赖 mood_score 阈值
- 从 EventStore 读取事件，检查是否满足触发条件
- 把事件证据打包给 Gemma-3 做自然语言推理
"""
import time
import threading
import json
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from skills.shared.event_store import store


FUSION_JUDGE_PROMPT = """You are an emotion analysis engine for an AI cat companion.
You will receive independent outputs from multiple perception models.
They may contradict each other — that's expected.

Your task:
1. Consider ALL evidence and reason about the user's REAL emotional state
2. More recent signals are more important than older ones
3. When multiple sources agree, confidence is higher
4. Consider environment (noise might just mean annoyed, not sad)
5. Consider if the user WANTS to be approached right now

Output ONLY JSON:
{
    "reasoning": "Your reasoning in 2-3 sentences, in Chinese",
    "emotion": "happy/neutral/sad/tired/anxious/frustrated",
    "confidence": 0.0-1.0,
    "should_speak": true/false,
    "speak_reason": "Why you decided to speak or not, in Chinese",
    "strategy": "empathetic_listening/encouragement/distraction/gentle_reminder/silent_comfort",
    "opener": "Suggested opening line in Chinese, cat personality",
    "cat_state": "neutral_idle/concerned/sleepy/sad_empathy/curious/encouraging/silent_comfort"
}"""


class CooldownManager:
    def __init__(self):
        self.min_interval = 30 * 60  # 30 min between proactive messages
        self.silence_until = 0
        self.daily_limit = 10
        self.daily_count = 0
        self.last_reset_day = time.localtime().tm_yday

    def can_speak(self) -> tuple:
        now = time.time()
        today = time.localtime().tm_yday
        if today != self.last_reset_day:
            self.daily_count = 0
            self.last_reset_day = today

        if now < self.silence_until:
            left = (self.silence_until - now) / 60
            return False, f"silent mode, {left:.0f} min left"

        last_p = store.get_last_proactive()
        if last_p > 0 and (now - last_p) < self.min_interval:
            left = (self.min_interval - (now - last_p)) / 60
            return False, f"cooldown, {left:.0f} min left"

        if self.daily_count >= self.daily_limit:
            return False, "daily limit reached"

        return True, "ok"

    def enter_silence(self, hours=2.0):
        self.silence_until = time.time() + hours * 3600
        print(f"[Cooldown] entering silence for {hours}h")

    def record_speak(self):
        self.daily_count += 1


class ProactiveEngineV2:
    def __init__(self, ollama_url="http://localhost:11434",
                 check_interval=180):
        self.ollama_url = ollama_url
        self.check_interval = check_interval
        self.cooldown = CooldownManager()
        self._running = False
        self.last_decision = None

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        print(f"[ProactiveEngine] started, check every {self.check_interval}s")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            time.sleep(self.check_interval)
            try:
                decision = self._decide()
                self.last_decision = decision
                if decision.get("should_speak"):
                    store.set_cat_state(decision.get("cat_state", "concerned"))
                    store.mark_proactive()
                    self.cooldown.record_speak()
                    print(f"\n[ProactiveEngine] TRIGGERED!")
                    print(f"  reasoning: {decision.get('reasoning','')}")
                    print(f"  strategy:  {decision.get('strategy','')}")
                    print(f"  opener:    {decision.get('opener','')}\n")
            except Exception as e:
                print(f"[ProactiveEngine] error: {e}")

    def _decide(self) -> dict:
        # Gate 1: cooldown
        can, reason = self.cooldown.can_speak()
        if not can:
            return {"should_speak": False, "speak_reason": reason}

        # Gate 2: need at least 2 independent signal sources
        if not store.has_multi_source_events(minutes=30, min_sources=2):
            src_count = store.get_source_count(minutes=30)
            return {
                "should_speak": False,
                "speak_reason": f"only {src_count} source(s), need >= 2"
            }

        # Gate 3: ask Gemma-3 to judge
        evidence = store.get_evidence_text(minutes=30)

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": "gemma3:27b",
                    "messages": [
                        {"role": "system", "content": FUSION_JUDGE_PROMPT},
                        {"role": "user", "content": (
                            f"Recent perception events:\n{evidence}\n\n"
                            "Based on these signals, make your decision."
                        )}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3}
                },
                timeout=60
            )
            content = resp.json()["message"]["content"]
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except Exception as e:
            print(f"[ProactiveEngine] LLM error: {e}")

        return {"should_speak": False, "speak_reason": "decision failed"}

    def force_check(self) -> dict:
        """Manual trigger for testing"""
        print("[ProactiveEngine] force checking...")
        decision = self._decide()
        self.last_decision = decision
        return decision
