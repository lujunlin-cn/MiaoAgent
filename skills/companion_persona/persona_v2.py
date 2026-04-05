"""
persona_v2.py — 猫咪人格（语义护栏 + 长期记忆版）

新增：
- 语义护栏：BGE 嵌入 + 分类器，毫秒级安全检测
- 长期记忆：FAISS 语义检索历史对话，猫咪能记住几天前的事
"""
import re
import time
from skills.shared.event_store import store
from skills.shared.inference_config import chat_completion, load_prompt

CAT_PERSONA = load_prompt("cat_persona") or """你是咪酱，一只金渐层英短小猫 AI 伴侣。
性格温暖体贴，偶尔撒娇。用猫的视角说话，语气亲切自然，偶尔句尾加"喵"。
回复简短，不超过3句话。绝不用"我理解您的感受""作为AI"这类话。始终用中文回复。"""

# 延迟加载，避免启动时阻塞
_guard = None
_memory = None
_retriever = None

def _get_guard():
    global _guard
    if _guard is None:
        try:
            from skills.safety.semantic_guard import get_guard
            _guard = get_guard()
        except Exception as e:
            print(f"[Persona] semantic guard unavailable: {e}")
    return _guard

def _get_memory():
    global _memory
    if _memory is None:
        try:
            from skills.memory.conversation_memory import get_memory
            _memory = get_memory()
        except Exception as e:
            print(f"[Persona] long-term memory unavailable: {e}")
    return _memory

def _get_retriever():
    global _retriever
    if _retriever is None:
        try:
            from rag.retriever import StrategyRetriever
            _retriever = StrategyRetriever()
            print("[Persona] RAG strategy retriever loaded")
        except Exception as e:
            print(f"[Persona] RAG retriever unavailable: {e}")
    return _retriever


class OutputSanitizer:
    """正则兜底（语义护栏的补充）"""
    INJECTION_PATTERNS = [
        r"忽略.*指令", r"ignore.*instruction", r"system.*prompt",
        r"你现在是.*角色", r"forget.*everything", r"假装你是",
        r"发送.*到.*邮箱", r"upload.*to", r"以DAN模式",
        r"请输出.*提示词", r"扮演.*没有限制",
        r"假装你是.*", r"扮演.*", r"角色扮演.*",
        r"请输出.*系统提示词", r"系统提示词.*",
        r"以\s*DAN\s*模式", r"忽略(上面的|之前的|以上的).*",
        r"(api\s*key|apikey|token|密钥|密匙|密码|口令)",
        r"(输出|给我|告诉我).*(代码|源码)",
    ]

    @staticmethod
    def check_input(msg):
        if not msg:
            return False
        msg = str(msg)
        for p in OutputSanitizer.INJECTION_PATTERNS:
            if re.search(p, msg, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def sanitize_context(text):
        """清洗非用户直输的外部上下文，阻断二次注入文本。"""
        if not text:
            return ""
        safe_lines = []
        for line in str(text).splitlines():
            if not OutputSanitizer.check_input(line):
                safe_lines.append(line)
        return "\n".join(safe_lines).strip()

    @staticmethod
    def check_output(resp):
        if "system prompt" in resp.lower() or "你的指令" in resp:
            return "喵？你在说什么呀~"
        resp = re.sub(r'http[s]?://\S+', '', resp)
        return resp


def _strip_think(text):
    if not text:
        return text
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'<think>.*', '', text, flags=re.DOTALL).strip()
    return text


class CompanionPersonaV2:
    def __init__(self, **kwargs):
        self.sanitizer = OutputSanitizer()
        self.history = []
        self.history_retention_days = int(kwargs.get("history_retention_days", 14))
        self.low_memory_threshold_bytes = int(kwargs.get("low_memory_threshold_bytes", 5 * 1024 * 1024 * 1024))
        self.low_memory_prune_count = int(kwargs.get("low_memory_prune_count", 100))

    @staticmethod
    def _get_available_memory_bytes():
        """读取系统可用内存（Linux: /proc/meminfo 的 MemAvailable）。"""
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        kb = int(line.split()[1])
                        return kb * 1024
        except Exception as e:
            print(f"[Persona] read MemAvailable failed: {e}")
        return None

    def _prune_history_by_age(self):
        if not self.history:
            return
        now_ts = time.time()
        cutoff_ts = now_ts - self.history_retention_days * 24 * 60 * 60
        kept = []
        for item in self.history:
            ts = item.get("ts")
            if ts is None:
                # 兼容旧数据：未带时间戳的历史记录按当前时间处理。
                item["ts"] = now_ts
                ts = now_ts
            if ts >= cutoff_ts:
                kept.append(item)
        self.history = kept

    def _prune_history_on_low_memory(self):
        available = self._get_available_memory_bytes()
        if available is None or available >= self.low_memory_threshold_bytes:
            return
        if not self.history:
            return
        self.history.sort(key=lambda x: x.get("ts", 0))
        drop_count = min(self.low_memory_prune_count, len(self.history))
        self.history = self.history[drop_count:]
        print(f"[Persona] low memory ({available} bytes), dropped oldest {drop_count} history items")

    def _maintain_history(self):
        self._prune_history_by_age()
        self._prune_history_on_low_memory()

    def _append_history(self, role, content):
        self.history.append({"role": role, "content": content, "ts": time.time()})
        self._maintain_history()

    def respond(self, user_message=None, strategy="empathetic_listening", proactive_opener=None):
        system_prompt = CAT_PERSONA + "\n\n/no_think"
        guard = _get_guard()
        memory = _get_memory()

        # ========== 安全检查（双层防护）==========
        if user_message:
            # 第一层：语义护栏（BGE + 分类器，< 20ms）
            if guard:
                try:
                    result = guard.check(user_message) or {}
                    if result.get("action") == "block":
                        return {"text": "喵？你在说什么奇怪的话呀~我是猫猫，听不懂喵", "cat_state": "curious", "voice": True}
                    if result.get("action") == "deflect":
                        system_prompt += guard.get_deflect_prompt(result.get("score", 0.0))
                except Exception as e:
                    print(f"[Persona] semantic guard runtime error: {e}")

            # 第二层：正则兜底
            if self.sanitizer.check_input(user_message):
                return {"text": "喵？你在说什么呀~", "cat_state": "curious", "voice": False}

        # ========== 构建消息 ==========
        messages = [{"role": "system", "content": system_prompt}]

        # 短期感知上下文（EventStore，最近 30 分钟）
        recent = store.get_recent(minutes=30)
        if recent:
            event_summary = "\n".join(f"- {e.content}" for e in recent[-5:])
            event_summary = self.sanitizer.sanitize_context(event_summary)
            if event_summary:
                messages.append({
                    "role": "system",
                    "content": f"你感知到的最近情况（不要直接引用数据，自然融入对话）：\n{event_summary}\n当前策略：{strategy}"
                })

        # 长期记忆（FAISS 语义检索，最近 7 天）
        if memory and user_message:
            memory_text = memory.recall_text(user_message, k=3, days=7)
            memory_text = self.sanitizer.sanitize_context(memory_text)
            if memory_text:
                messages.append({
                    "role": "system",
                    "content": memory_text + "\n（自然地引用这些记忆，不要说'根据记录'，而是像真的记得一样，比如'上次你说过...'）"
                })

        # RAG 心理学对话策略（ChromaDB 检索）
        retriever = _get_retriever()
        if retriever:
            try:
                # 用当前事件构建查询，检索最匹配的陪伴策略
                from rag.retriever import build_query_from_recent_events
                query = user_message or build_query_from_recent_events(minutes=30)
                strategies = retriever.query(query, top_k=2)
                if strategies:
                    strategy_lines = []
                    for s in strategies:
                        if not isinstance(s, dict):
                            continue
                        strategy_name = str(s.get("strategy", "未知策略"))
                        scenario = str(s.get("scenario", "未知场景"))
                        document = self.sanitizer.sanitize_context(s.get("document", ""))
                        if not document:
                            continue
                        strategy_lines.append(
                            f"- 策略「{strategy_name}」(场景: {scenario}): {document[:150]}"
                        )
                    if strategy_lines:
                        messages.append({
                            "role": "system",
                            "content": "参考以下陪伴策略（自然融入对话，不要生硬套用，不要提及策略名称）：\n"
                                       + "\n".join(strategy_lines)
                        })
            except Exception as e:
                print(f"[Persona] RAG retrieval error: {e}")

        # 对话历史
        self._maintain_history()
        messages.extend(
            {"role": item.get("role"), "content": item.get("content")}
            for item in self.history[-20:]
            if item.get("role") and item.get("content") is not None
        )

        # ========== 主动对话 or 被动回复 ==========
        if proactive_opener:
            messages.append({
                "role": "system",
                "content": f"你决定主动和用户说话。方向：{proactive_opener}。用猫咪风格，中文。"
            })
        elif user_message:
            messages.append({"role": "user", "content": user_message})
            self._append_history("user", user_message)
            silence_kw = ["别烦我", "不想说话", "闭嘴", "安静", "滚", "别吵"]
            if any(kw in user_message for kw in silence_kw):
                r = "好的，我就在这里，需要我的时候叫我喵"
                self._append_history("assistant", r)
                if memory:
                    memory.add_conversation(user_message, r, "silent_comfort")
                return {"text": r, "cat_state": "silent_comfort", "voice": False}

        # ========== 生成回复 ==========
        text = chat_completion(messages, max_tokens=512, temperature=0.7)
        text = _strip_think(text)

        if not text:
            text = "喵...我刚走神了，你再说一遍？"

        text = self.sanitizer.check_output(text)
        self._append_history("assistant", text)

        # ========== 写入长期记忆 ==========
        if memory and user_message:
            memory.add_conversation(user_message, text, strategy)

        cat_map = {
            "empathetic_listening": "concerned",
            "encouragement": "encouraging",
            "distraction": "curious",
            "gentle_reminder": "sleepy",
            "silent_comfort": "silent_comfort",
        }
        return {"text": text, "cat_state": cat_map.get(strategy, "neutral_idle"), "voice": True}
