"""
social_bridge.py — 社交消息桥接器（只读）

统一接口，支持多种后端：
  - weclaw:    fastclaw-ai/weclaw HTTP API（推荐，有 ARM64 支持）
  - ipad:      laolin5564/openclaw-wechat iPad 协议服务
  - clawbot:   腾讯官方 WeChat ClawBot（通过 OpenClaw gateway websocket）
  - demo:      模拟数据（兜底方案）

核心原则：
  ⚠️ 这个类没有任何 send/reply 方法 — 从设计上杜绝发送消息
  所有消息只读取，通过 EventStore 注入感知事件供融合裁判分析

用法：
  bridge = SocialBridge(mode="weclaw")
  bridge.start()   # 后台线程轮询
  bridge.stop()
"""
import time
import json
import threading
import os
from typing import Optional, Callable

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from skills.shared.event_store import store


# ============================================================
# 情绪关键词映射（中文消息快速情绪判断）
# ============================================================
EMOTION_KEYWORDS = {
    "positive": [
        "开心", "高兴", "太好了", "哈哈", "恭喜", "棒", "赞", "好消息",
        "通过了", "录取", "升职", "加薪", "结婚", "生日快乐", "谢谢",
        "爱你", "想你", "期待", "兴奋", "终于", "成功",
    ],
    "negative": [
        "难过", "伤心", "崩溃", "烦死", "焦虑", "压力大", "加班",
        "失眠", "吵架", "分手", "被骂", "生气", "烦躁", "累死",
        "不想", "受不了", "绝望", "孤独", "委屈", "无语", "气死",
        "deadline", "ddl", "挂科", "被退", "被拒",
    ],
    "concerned": [
        "你还好吗", "怎么了", "还好吗", "没事吧", "注意身体",
        "早点睡", "别太累", "担心你", "照顾好自己",
    ],
}


def _quick_emotion(text: str) -> str:
    """快速情绪判断（关键词匹配，DistilBERT 的补充）"""
    text_lower = text.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return emotion
    return "neutral"


def _analyze_emotion_deep(text: str) -> dict:
    """深度情绪分析（使用 DistilBERT，如果可用）"""
    try:
        from skills.emotion_perception.perception_v2 import TextSentimentAnalyzer
        _cached = getattr(_analyze_emotion_deep, "_analyzer", None)
        if _cached is None:
            _cached = TextSentimentAnalyzer()
            _analyze_emotion_deep._analyzer = _cached
        return _cached.analyze(text)
    except Exception:
        emotion = _quick_emotion(text)
        return {"emotion": emotion, "confidence": 0.6}


# ============================================================
# 消息处理核心（所有后端共用）
# ============================================================
class MessageProcessor:
    """处理收到的消息，注入 EventStore"""

    def __init__(self, source_prefix: str = "wechat"):
        self.source_prefix = source_prefix
        self.message_count = 0
        self._last_emotions = []

    def process(self, msg: dict):
        """处理一条消息

        msg 格式（各后端适配后统一为此格式）：
        {
            "sender": "小雨",
            "content": "你最近怎么都不回消息了",
            "type": "text",           # text / image / voice / system
            "is_group": False,
            "group_name": "",         # 群聊时有值
            "timestamp": 1774944000,
        }
        """
        content = msg.get("content", "")
        sender = msg.get("sender", "unknown")
        msg_type = msg.get("type", "text")
        is_group = msg.get("is_group", False)
        group_name = msg.get("group_name", "")

        if not content or msg_type != "text":
            return

        # 构建事件描述
        if is_group and group_name:
            location = f"[{self.source_prefix}-{group_name}]"
        else:
            location = f"[{self.source_prefix}-私聊]"

        event_content = f"{location} {sender}: {content[:100]}"

        # 注入原始消息事件
        store.add_simple(
            source=f"{self.source_prefix}_passive",
            content=event_content,
            emotion=_quick_emotion(content),
            confidence=0.6,
        )

        # 文字消息做深度情绪分析
        emotion_result = _analyze_emotion_deep(content)
        if emotion_result.get("emotion") != "neutral":
            store.add_simple(
                source=f"{self.source_prefix}_emotion",
                content=f"[情绪分析] {sender}的消息情绪: {emotion_result['emotion']}",
                emotion=emotion_result.get("emotion", "neutral"),
                confidence=emotion_result.get("confidence", 0.5),
            )
            self._last_emotions.append(emotion_result["emotion"])

        self.message_count += 1

        # 每 10 条消息做一次情绪趋势汇总
        if len(self._last_emotions) >= 10:
            neg_count = sum(1 for e in self._last_emotions if e == "negative")
            pos_count = sum(1 for e in self._last_emotions if e == "positive")
            if neg_count > 6:
                store.add_simple(
                    source=f"{self.source_prefix}_trend",
                    content=f"[社交趋势] 近期{self.source_prefix}消息情绪明显偏负面 ({neg_count}/10条)",
                    emotion="negative",
                    confidence=0.8,
                )
            elif pos_count > 6:
                store.add_simple(
                    source=f"{self.source_prefix}_trend",
                    content=f"[社交趋势] 近期{self.source_prefix}消息情绪积极 ({pos_count}/10条)",
                    emotion="positive",
                    confidence=0.8,
                )
            self._last_emotions = self._last_emotions[-5:]  # 保留最近 5 条


# ============================================================
# 后端适配器
# ============================================================

class WeclawBackend:
    """weclaw (fastclaw-ai) HTTP API 后端

    weclaw 暴露 HTTP API，我们轮询获取新消息。
    weclaw 本身支持 ACP/CLI/HTTP agent 模式，
    我们只用它的消息接收能力，不接 agent。

    需要 weclaw 以 HTTP agent 模式启动：
      weclaw start --agent-type http --agent-url http://127.0.0.1:9099/webhook
    我们在 9099 端口接收 webhook。
    """

    def __init__(self, webhook_port: int = 9099):
        self.webhook_port = webhook_port
        self._server = None
        self._messages = []
        self._lock = threading.Lock()

    def start(self, callback: Callable):
        """启动 webhook 接收服务器"""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        messages = self._messages
        lock = self._lock
        cb = callback

        class WebhookHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    # weclaw webhook 格式适配
                    msg = {
                        "sender": data.get("from", {}).get("name", "unknown"),
                        "content": data.get("message", {}).get("text", ""),
                        "type": "text" if data.get("message", {}).get("type") == "text" else "other",
                        "is_group": data.get("chat", {}).get("type") == "group",
                        "group_name": data.get("chat", {}).get("name", ""),
                        "timestamp": time.time(),
                    }
                    cb(msg)
                except Exception as e:
                    print(f"[WeclawBackend] parse error: {e}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')

            def log_message(self, format, *args):
                pass  # 静默日志

        self._server = HTTPServer(("0.0.0.0", self.webhook_port), WebhookHandler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        print(f"[WeclawBackend] webhook server listening on :{self.webhook_port}")

    def stop(self):
        if self._server:
            self._server.shutdown()


class IPadProtocolBackend:
    """laolin5564/openclaw-wechat iPad 协议后端

    通过 HTTP 轮询 wechat-service (port 8099) 获取消息。
    """

    def __init__(self, service_url: str = "http://127.0.0.1:8099"):
        self.service_url = service_url
        self._running = False

    def start(self, callback: Callable):
        self._running = True

        def poll_loop():
            import requests
            while self._running:
                try:
                    resp = requests.get(
                        f"{self.service_url}/api/messages/poll",
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        for raw_msg in resp.json():
                            msg = {
                                "sender": raw_msg.get("from", "unknown"),
                                "content": raw_msg.get("content", ""),
                                "type": raw_msg.get("type", "text"),
                                "is_group": raw_msg.get("room") is not None,
                                "group_name": raw_msg.get("room", ""),
                                "timestamp": raw_msg.get("timestamp", time.time()),
                            }
                            callback(msg)
                except Exception as e:
                    if self._running:
                        print(f"[IPadBackend] poll error: {e}")
                    time.sleep(5)

        threading.Thread(target=poll_loop, daemon=True).start()
        print(f"[IPadBackend] polling {self.service_url}")

    def stop(self):
        self._running = False


class ClawBotBackend:
    """腾讯官方 WeChat ClawBot 后端

    通过 OpenClaw gateway WebSocket 获取消息。
    局限：只能收到发给 bot 的消息，不能被动读取其他消息。
    """

    def __init__(self, gateway_url: str = "ws://127.0.0.1:18789"):
        self.gateway_url = gateway_url
        self._running = False

    def start(self, callback: Callable):
        self._running = True

        def ws_loop():
            try:
                import websockets
                import asyncio

                async def listen():
                    async with websockets.connect(self.gateway_url) as ws:
                        async for raw in ws:
                            if not self._running:
                                break
                            try:
                                event = json.loads(raw)
                                if event.get("type") == "message":
                                    msg = {
                                        "sender": event.get("from", {}).get("name", "unknown"),
                                        "content": event.get("text", ""),
                                        "type": "text",
                                        "is_group": False,
                                        "group_name": "",
                                        "timestamp": time.time(),
                                    }
                                    callback(msg)
                            except json.JSONDecodeError:
                                pass

                asyncio.new_event_loop().run_until_complete(listen())
            except ImportError:
                print("[ClawBotBackend] websockets not installed: pip install websockets")
            except Exception as e:
                print(f"[ClawBotBackend] error: {e}")

        threading.Thread(target=ws_loop, daemon=True).start()
        print(f"[ClawBotBackend] connecting to {self.gateway_url}")

    def stop(self):
        self._running = False


class DemoBackend:
    """模拟数据后端（兜底）

    从 demo_social_messages.py 的场景中随机选择并注入，
    模拟真实的社交消息流。
    """

    def __init__(self, interval: float = 30.0):
        self.interval = interval
        self._running = False

    def start(self, callback: Callable):
        self._running = True

        demo_messages = [
            {"sender": "小雨", "content": "你最近怎么都不回消息了？还好吗", "is_group": False},
            {"sender": "领导-王总", "content": "你那个项目进度怎么样了？明天给我汇报一下", "is_group": False},
            {"sender": "同事群", "content": "周五之前必须交方案，没有例外", "is_group": True, "group_name": "工作群"},
            {"sender": "妈妈", "content": "宝贝周末回来吃饭吗？给你炖了排骨汤", "is_group": False},
            {"sender": "老同学", "content": "周末有人出来聚聚吗？好久没见了", "is_group": True, "group_name": "大学群"},
            {"sender": "小美", "content": "你要这么想那我也没办法，随便你吧", "is_group": False},
            {"sender": "男朋友", "content": "都一点了还不睡？明天不是还要早起吗", "is_group": False},
            {"sender": "闺蜜", "content": "姐妹！！我考上研了！！！太开心了", "is_group": False},
            {"sender": "同事-小李", "content": "姐你也还没睡啊...我这bug改不完了", "is_group": False},
            {"sender": "班长", "content": "毕业十年聚会定了，暑假见！大家报名", "is_group": True, "group_name": "大学群"},
        ]

        def loop():
            import random
            idx = 0
            while self._running:
                time.sleep(self.interval)
                if not self._running:
                    break
                msg = demo_messages[idx % len(demo_messages)].copy()
                msg["type"] = "text"
                msg["timestamp"] = time.time()
                if "group_name" not in msg:
                    msg["group_name"] = ""
                callback(msg)
                idx += 1

        threading.Thread(target=loop, daemon=True).start()
        print(f"[DemoBackend] started, interval={self.interval}s")

    def stop(self):
        self._running = False


# ============================================================
# 统一桥接器
# ============================================================

BACKENDS = {
    "weclaw": WeclawBackend,
    "ipad": IPadProtocolBackend,
    "clawbot": ClawBotBackend,
    "demo": DemoBackend,
}


class SocialBridge:
    """社交消息桥接器 — 只读，没有任何发送方法

    用法：
        bridge = SocialBridge(mode="demo")
        bridge.start()
        # ... 消息会自动注入 EventStore
        bridge.stop()
    """

    def __init__(self, mode: str = "demo", **kwargs):
        """
        Args:
            mode: "weclaw" | "ipad" | "clawbot" | "demo"
            **kwargs: 传给对应后端的参数
        """
        self.mode = mode

        if mode not in BACKENDS:
            print(f"[SocialBridge] unknown mode '{mode}', falling back to demo")
            mode = "demo"

        self.backend = BACKENDS[mode](**kwargs)
        self.wechat_processor = MessageProcessor(source_prefix="wechat")
        self._running = False

    def start(self):
        """启动桥接（后台线程）"""
        self._running = True
        self.backend.start(callback=self._on_message)
        print(f"[SocialBridge] started (mode={self.mode})")

    def stop(self):
        """停止桥接"""
        self._running = False
        self.backend.stop()
        print(f"[SocialBridge] stopped")

    def _on_message(self, msg: dict):
        """收到消息的回调 — 只读处理，不发送"""
        if not self._running:
            return
        try:
            self.wechat_processor.process(msg)
        except Exception as e:
            print(f"[SocialBridge] process error: {e}")

    def stats(self) -> dict:
        return {
            "mode": self.mode,
            "running": self._running,
            "wechat_messages": self.wechat_processor.message_count,
        }

    # ⚠️ 这个类没有 send / reply / post 方法 — 从设计上杜绝发送


# ============================================================
# CLI 入口
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MiaoAgent 社交消息桥接器")
    parser.add_argument("--mode", "-m", default="demo",
                        choices=list(BACKENDS.keys()),
                        help="后端模式 (default: demo)")
    parser.add_argument("--interval", "-i", type=float, default=15,
                        help="Demo 模式消息间隔秒数 (default: 15)")
    args = parser.parse_args()

    kwargs = {}
    if args.mode == "demo":
        kwargs["interval"] = args.interval

    bridge = SocialBridge(mode=args.mode, **kwargs)
    bridge.start()

    print(f"\n[SocialBridge] 运行中 (mode={args.mode})，Ctrl+C 停止\n")
    try:
        while True:
            time.sleep(10)
            s = bridge.stats()
            print(f"  messages: {s['wechat_messages']}")
    except KeyboardInterrupt:
        bridge.stop()
        print("\n[SocialBridge] 已停止")
