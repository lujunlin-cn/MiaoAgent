"""
engine_v2.py — 事件驱动主动对话决策引擎（语义记忆版）

新增：融合裁判时也检索长期记忆，发现历史模式
"""
import time
import threading
import json
import re

from skills.shared.event_store import store
from skills.shared.inference_config import judge_completion, load_prompt

FUSION_JUDGE_PROMPT = load_prompt("fusion_judge") or """You are an emotion analysis engine for an AI cat companion.
Based on perception signals, decide if the cat should speak. When in doubt, lean towards speaking.
Output ONLY JSON: {"reasoning":"...","emotion":"...","confidence":0.0-1.0,"should_speak":true/false,
"speak_reason":"...","strategy":"empathetic_listening/encouragement/distraction/gentle_reminder/silent_comfort",
"opener":"...","cat_state":"neutral_idle/concerned/sleepy/sad_empathy/curious/encouraging/silent_comfort"}"""

_memory = None

def _get_memory():
    global _memory
    if _memory is None:
        try:
            from skills.memory.conversation_memory import get_memory
            _memory = get_memory()
        except Exception:
            pass
    return _memory


def _strip_think(text):
    if not text:
        return text
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'<think>.*', '', text, flags=re.DOTALL).strip()
    return text


class CooldownManager:
    def __init__(self):
        self.min_interval = 30 * 60
        self.silence_until = 0
        self.daily_limit = 10
        self.daily_count = 0
        self.last_reset_day = time.localtime().tm_yday

    def can_speak(self):
        now = time.time()
        today = time.localtime().tm_yday
        if today != self.last_reset_day:
            self.daily_count = 0
            self.last_reset_day = today
        if now < self.silence_until:
            return False, f"silent mode, {(self.silence_until - now)/60:.0f} min left"
        last_p = store.get_last_proactive()
        if last_p > 0 and (now - last_p) < self.min_interval:
            return False, f"cooldown, {(self.min_interval - (now - last_p))/60:.0f} min left"
        if self.daily_count >= self.daily_limit:
            return False, "daily limit reached"
        return True, "ok"

    def enter_silence(self, hours=2.0):
        self.silence_until = time.time() + hours * 3600

    def record_speak(self):
        self.daily_count += 1


class ProactiveEngineV2:
    def __init__(self, **kwargs):
        self.check_interval = kwargs.get("check_interval", 180)
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
        # 关闭时保存记忆
        memory = _get_memory()
        if memory:
            memory.save()

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
                    print(f"  reasoning: {decision.get('reasoning', '')}")
                    print(f"  opener:    {decision.get('opener', '')}\n")
            except Exception as e:
                print(f"[ProactiveEngine] error: {e}")

    def _decide(self, force=False):
        if not force:
            can, reason = self.cooldown.can_speak()
            if not can:
                return {"should_speak": False, "speak_reason": reason}

            if not store.has_multi_source_events(minutes=30, min_sources=1):
                return {"should_speak": False, "speak_reason": "no events"}

        evidence = store.get_evidence_text(minutes=30)

        # force 模式下如果没有事件，直接用注入的数据
        if not evidence or len(evidence.strip()) < 10:
            if force:
                evidence = store.get_evidence_text(minutes=1440)  # 扩大到24小时
            if not evidence or len(evidence.strip()) < 10:
                return {"should_speak": False, "speak_reason": "no evidence text"}

        # 检索长期记忆中与当前事件相关的历史
        memory = _get_memory()
        memory_context = ""
        if memory:
            memory_context = memory.recall_text(evidence[:200], k=3, days=7)

        prompt_parts = [FUSION_JUDGE_PROMPT, "\n\n/no_think"]
        messages = [
            {"role": "system", "content": "".join(prompt_parts)},
            {"role": "user", "content": f"Recent events:\n{evidence}\n\n{memory_context}\n\nMake your decision."}
        ]

        content = judge_completion(messages, temperature=0.3, max_tokens=500)
        content = _strip_think(content)

        if not content:
            return {"should_speak": False, "speak_reason": "judge unavailable"}

        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except (json.JSONDecodeError, ValueError):
            if "true" in content.lower()[:100]:
                return {"should_speak": True, "speak_reason": "fallback parse",
                        "strategy": "empathetic_listening", "opener": "喵...你还好吗？",
                        "cat_state": "concerned"}
        return {"should_speak": False, "speak_reason": "parse failed"}

    def force_check(self):
        """强制检查，绕过冷却和事件源数量限制（用于测试）"""
        print("[ProactiveEngine] force checking (bypass cooldown & event gate)...")
        return self._decide(force=True)