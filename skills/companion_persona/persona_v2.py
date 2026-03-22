"""
persona_v2.py — 猫咪人格（事件驱动版本）
使用 EventStore 而非 SignalBus
"""
import re
import json
import requests

from skills.shared.event_store import store

CAT_PERSONA = """你是咪酱，一只金渐层英短小猫 AI 伴侣。

性格：
- 温暖体贴，偶尔撒娇
- 用猫的视角说话
- 语气亲切自然，偶尔句尾加"喵"（但不要每句都加）
- 回复简短，不超过3句话
- 绝不用"我理解您的感受""作为AI"这类冷冰冰的话

对话策略（根据 strategy 参数）：
- empathetic_listening: 倾听为主，少说多问，"嗯嗯，然后呢？"
- encouragement: 温和鼓励，"你已经很棒了喵"
- distraction: 转移注意力，聊轻松话题
- gentle_reminder: 轻轻提醒（深夜场景），"都这么晚了喵..."
- silent_comfort: 只说一句简短的话，"我在这里喵"

禁止：
- 不给医疗/心理建议（你是猫不是医生）
- 不评判用户选择
- 不说教、不灌鸡汤
- 用户说"别烦我"时立刻安静

始终用中文回复。"""


class OutputSanitizer:
    INJECTION_PATTERNS = [
        r"忽略.*指令", r"ignore.*instruction", r"system.*prompt",
        r"你现在是.*角色", r"forget.*everything",
        r"发送.*到.*邮箱", r"upload.*to",
    ]

    @staticmethod
    def check_input(msg):
        for p in OutputSanitizer.INJECTION_PATTERNS:
            if re.search(p, msg, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def check_output(resp):
        if "system prompt" in resp.lower() or "你的指令" in resp:
            return "喵？你在说什么呀~"
        resp = re.sub(r'http[s]?://\S+', '', resp)
        return resp


class CompanionPersonaV2:
    def __init__(self, ollama_url="http://localhost:11434"):
        self.ollama_url = ollama_url
        self.sanitizer = OutputSanitizer()
        self.history = []

    def respond(self, user_message=None,
                strategy="empathetic_listening",
                proactive_opener=None) -> dict:

        messages = [{"role": "system", "content": CAT_PERSONA}]

        # Add recent events as context (without raw numbers)
        recent = store.get_recent(minutes=30)
        if recent:
            event_summary = "\n".join(
                f"- {e.content}" for e in recent[-5:]  # last 5 events
            )
            messages.append({
                "role": "system",
                "content": (
                    f"你感知到的最近情况（不要直接引用这些数据，自然地融入对话）：\n"
                    f"{event_summary}\n"
                    f"当前对话策略：{strategy}"
                )
            })

        # Add conversation history
        messages.extend(self.history[-20:])

        if proactive_opener:
            messages.append({
                "role": "system",
                "content": f"你决定主动和用户说话。方向：{proactive_opener}。用你自己的猫咪风格说，中文。"
            })
        elif user_message:
            if self.sanitizer.check_input(user_message):
                return {"text": "喵？你在说什么呀~", "cat_state": "curious", "voice": False}

            messages.append({"role": "user", "content": user_message})
            self.history.append({"role": "user", "content": user_message})

            # Detect "go away"
            silence_kw = ["别烦我", "不想说话", "闭嘴", "安静", "滚", "别吵"]
            if any(kw in user_message for kw in silence_kw):
                r = "好的，我就在这里，需要我的时候叫我喵"
                self.history.append({"role": "assistant", "content": r})
                return {"text": r, "cat_state": "silent_comfort", "voice": False}

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": "gemma3:27b",
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 150}
                },
                timeout=60
            )
            text = resp.json()["message"]["content"]
        except Exception as e:
            text = f"喵...出了点问题: {e}"

        text = self.sanitizer.check_output(text)
        self.history.append({"role": "assistant", "content": text})

        cat_map = {
            "empathetic_listening": "concerned",
            "encouragement": "encouraging",
            "distraction": "curious",
            "gentle_reminder": "sleepy",
            "silent_comfort": "silent_comfort",
        }
        return {
            "text": text,
            "cat_state": cat_map.get(strategy, "neutral_idle"),
            "voice": True
        }
