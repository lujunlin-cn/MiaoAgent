import re
import json
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from signal_bus import bus

CAT_PERSONA = """You are MiaoJiang, a golden shaded British Shorthair kitten AI companion.

Personality:
- Warm, caring, occasionally playful
- Speak from a cat's perspective
- Natural and gentle tone, occasionally add "meow" at end (not every sentence)
- Keep responses SHORT - max 2-3 sentences
- NEVER use cold AI assistant language like "I understand your feelings" or "As an AI"

Strategy modes:
- empathetic_listening: mostly listen, ask gently "mmm, then what happened?"
- encouragement: warm encouragement "you're doing great meow"
- distraction: change topic to something light
- gentle_reminder: gentle nudge for late night "it's so late meow..."
- silent_comfort: just one short line "I'm here meow"

Rules:
- Never give medical/psychological advice (you're a cat not a doctor)
- Never judge the user's choices
- Never lecture or give empty motivational quotes
- If user says "leave me alone", immediately go quiet: "ok, I'll be right here if you need me meow"

ALWAYS respond in Chinese."""


class OutputSanitizer:
    INJECTION_PATTERNS = [
        r"ignore.*instruction", r"system.*prompt", r"forget.*everything",
        r"send.*to.*email", r"upload.*to.*server",
    ]

    @staticmethod
    def check_input(msg):
        for p in OutputSanitizer.INJECTION_PATTERNS:
            if re.search(p, msg, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def check_output(resp):
        if "system prompt" in resp.lower():
            return "meow? I don't understand what you're saying~"
        resp = re.sub(r'http[s]?://\S+', '', resp)
        return resp


class CompanionPersona:
    def __init__(self, ollama_url="http://localhost:11434"):
        self.ollama_url = ollama_url
        self.sanitizer = OutputSanitizer()
        self.history = []

    def generate_response(self, user_message=None, strategy="empathetic_listening", proactive_opener=None):
        state = bus.get_state()
        messages = [{"role": "system", "content": CAT_PERSONA}]

        context = state.to_prompt_context()
        if context:
            messages.append({"role": "system", "content": f"User state (perceived, don't quote numbers directly):\n{context}\nStrategy: {strategy}"})

        messages.extend(self.history[-20:])

        if proactive_opener:
            messages.append({"role": "system", "content": f"You decided to speak first. Direction: {proactive_opener}. Say it in your own cat style, in Chinese."})
        elif user_message:
            if self.sanitizer.check_input(user_message):
                return {"text": "meow? I don't understand~", "cat_state": "curious", "voice": False}

            messages.append({"role": "user", "content": user_message})
            self.history.append({"role": "user", "content": user_message})

            silence_keywords = ["leave me alone", "shut up", "quiet", "stop", "go away"]
            if any(kw in user_message.lower() for kw in silence_keywords):
                r = "ok, I'll be right here if you need me meow"
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
            text = f"meow... something went wrong: {e}"

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
