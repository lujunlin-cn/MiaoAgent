"""
event_store.py — 事件驱动架构，替代旧的 mood_score 加权平均

核心思想：
- 各感知模型独立检测"事件"，不融合成分数
- 事件存入本地存储，24 小时自动过期
- 决策引擎从存储中读取事件，打包给 Gemma-3 做自然语言推理
"""
import time
import threading
from typing import List, Optional


class Event:
    def __init__(self, source: str, content: str,
                 raw_label: dict = None, ttl: int = 86400):
        self.id = f"{source}_{int(time.time() * 1000)}"
        self.time = time.time()
        self.source = source
        self.content = content
        self.raw_label = raw_label or {}
        self.ttl = ttl

    def is_expired(self):
        return time.time() - self.time > self.ttl

    def to_evidence_line(self):
        t = time.strftime("%H:%M", time.localtime(self.time))
        conf = self.raw_label.get("confidence", None)
        conf_str = f" (conf: {conf:.0%})" if isinstance(conf, (int, float)) else ""
        return f"[{t}] [{self.source}] {self.content}{conf_str}"

    def __repr__(self):
        return f"Event({self.source}, {self.content[:30]}...)"


class EventStore:
    def __init__(self):
        self._events: List[Event] = []
        self._lock = threading.Lock()
        self._cat_state = "neutral_idle"
        self._last_user_interaction = 0.0
        self._last_proactive = 0.0

    # ---- 写入 ----

    def add(self, event: Event):
        with self._lock:
            self._events.append(event)
            self._cleanup()
        print(f"[EventStore] +{event.source}: {event.content[:50]}")

    def add_simple(self, source: str, content: str,
                   emotion: str = "", confidence: float = 0.0):
        e = Event(
            source=source,
            content=content,
            raw_label={"emotion": emotion, "confidence": confidence}
        )
        self.add(e)

    # ---- 读取 ----

    def get_recent(self, minutes: int = 30) -> List[Event]:
        cutoff = time.time() - minutes * 60
        with self._lock:
            self._cleanup()
            return [e for e in self._events if e.time >= cutoff]

    def get_evidence_text(self, minutes: int = 30) -> str:
        events = self.get_recent(minutes)
        if not events:
            return f"(no events in the last {minutes} minutes)"

        lines = [e.to_evidence_line() for e in events]
        sources = set(e.source for e in events)
        header = (f"{len(events)} events from {len(sources)} "
                  f"source(s) in the last {minutes} min:")
        return header + "\n" + "\n".join(lines)

    def has_multi_source_events(self, minutes: int = 30,
                                 min_sources: int = 2) -> bool:
        events = self.get_recent(minutes)
        sources = set(e.source for e in events)
        return len(sources) >= min_sources

    def get_source_count(self, minutes: int = 30) -> int:
        events = self.get_recent(minutes)
        return len(set(e.source for e in events))

    # ---- 状态管理 ----

    def set_cat_state(self, state: str):
        with self._lock:
            self._cat_state = state

    def get_cat_state(self) -> str:
        with self._lock:
            return self._cat_state

    def mark_user_interaction(self):
        with self._lock:
            self._last_user_interaction = time.time()

    def mark_proactive(self):
        with self._lock:
            self._last_proactive = time.time()

    def get_last_user_interaction(self) -> float:
        with self._lock:
            return self._last_user_interaction

    def get_last_proactive(self) -> float:
        with self._lock:
            return self._last_proactive

    # ---- 清理 ----

    def _cleanup(self):
        self._events = [e for e in self._events if not e.is_expired()]

    def clear_all(self):
        with self._lock:
            self._events.clear()
        print("[EventStore] cleared all events")

    def stats(self) -> dict:
        with self._lock:
            self._cleanup()
            sources = {}
            for e in self._events:
                sources[e.source] = sources.get(e.source, 0) + 1
            return {
                "total_events": len(self._events),
                "sources": sources,
                "cat_state": self._cat_state,
                "oldest_event_age_min": (
                    (time.time() - self._events[0].time) / 60
                    if self._events else 0
                ),
            }


# Global singleton
store = EventStore()
