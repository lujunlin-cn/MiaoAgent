"""
demo_social_messages.py — 模拟微信/QQ 社交消息注入

用途：
  黑客松 Demo 演示时，即使微信/QQ 桥接未部署（ARM64 不兼容等），
  也能向 EventStore 注入模拟的社交消息，展示"社交上下文分析"能力。

使用方式：
  方式一（CLI 独立运行）：
    python3 demo_social_messages.py --scenario stressed
    python3 demo_social_messages.py --scenario lonely
    python3 demo_social_messages.py --scenario happy

  方式二（通过 Web API 注入）：
    curl -X POST http://127.0.0.1:5000/demo/inject -H "Content-Type: application/json" \
         -d '{"source":"wechat_passive","content":"闺蜜: 你最近怎么都不回消息了","emotion":"concerned"}'

  方式三（代码内调用）：
    from demo_social_messages import inject_scenario
    inject_scenario("stressed", delay=0)
"""
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skills.shared.event_store import store


# ============================================================
# 场景数据
# ============================================================

SCENARIOS = {
    "stressed": {
        "name": "工作压力大",
        "description": "模拟用户收到工作相关的压力消息",
        "messages": [
            {
                "source": "wechat_passive",
                "content": "[微信-同事群] 领导: @全体成员 周五之前必须交方案，没有例外",
                "emotion": "negative",
                "confidence": 0.8,
            },
            {
                "source": "wechat_emotion",
                "content": "[微信情绪分析] 同事群近期消息情绪偏负面，多次提到加班、deadline",
                "emotion": "anxious",
                "confidence": 0.75,
            },
            {
                "source": "wechat_passive",
                "content": "[微信-闺蜜] 小雨: 你最近怎么都不回消息了？还好吗",
                "emotion": "concerned",
                "confidence": 0.7,
            },
            {
                "source": "qq_passive",
                "content": "[QQ-大学群] 老同学: 周末有人出来聚聚吗？好久没见了",
                "emotion": "neutral",
                "confidence": 0.6,
            },
            {
                "source": "wechat_passive",
                "content": "[微信-领导私聊] 王总: 你那个项目进度怎么样了？明天给我汇报一下",
                "emotion": "negative",
                "confidence": 0.85,
            },
        ],
    },
    "lonely": {
        "name": "社交孤立",
        "description": "模拟用户长时间没有社交互动",
        "messages": [
            {
                "source": "wechat_passive",
                "content": "[微信-消息统计] 过去 24 小时仅收到 2 条消息（均为群通知）",
                "emotion": "neutral",
                "confidence": 0.9,
            },
            {
                "source": "wechat_emotion",
                "content": "[微信情绪分析] 用户近 3 天未主动发送任何消息，社交活跃度极低",
                "emotion": "negative",
                "confidence": 0.7,
            },
            {
                "source": "qq_passive",
                "content": "[QQ-系统通知] 你有 15 条未读消息（全部来自群聊）",
                "emotion": "neutral",
                "confidence": 0.5,
            },
        ],
    },
    "happy": {
        "name": "好消息",
        "description": "模拟用户收到好消息",
        "messages": [
            {
                "source": "wechat_passive",
                "content": "[微信-妈妈] 妈妈: 宝贝周末回来吃饭吗？给你炖了排骨汤",
                "emotion": "positive",
                "confidence": 0.9,
            },
            {
                "source": "wechat_passive",
                "content": "[微信-闺蜜] 小雨: 姐妹！！我考上研了！！！太开心了",
                "emotion": "positive",
                "confidence": 0.95,
            },
            {
                "source": "wechat_emotion",
                "content": "[微信情绪分析] 好友圈近期消息情绪积极，多条祝贺和分享好消息",
                "emotion": "positive",
                "confidence": 0.85,
            },
            {
                "source": "qq_passive",
                "content": "[QQ-大学群] 班长: 毕业十年聚会定了，暑假见！大家报名",
                "emotion": "positive",
                "confidence": 0.7,
            },
        ],
    },
    "late_night": {
        "name": "深夜加班",
        "description": "模拟深夜收到的消息 + 摄像头检测到疲态",
        "messages": [
            {
                "source": "camera",
                "content": "检测到用户面部表情: tired/exhausted, 眼睛半闭, 频繁揉眼",
                "emotion": "tired",
                "confidence": 0.88,
            },
            {
                "source": "wechat_passive",
                "content": "[微信-男朋友] 阿杰: 都一点了还不睡？明天不是还要早起吗",
                "emotion": "concerned",
                "confidence": 0.75,
            },
            {
                "source": "wechat_passive",
                "content": "[微信-同事] 小李: 姐你也还没睡啊...我这bug改不完了",
                "emotion": "negative",
                "confidence": 0.7,
            },
            {
                "source": "env_audio",
                "content": "环境音: 安静，偶尔键盘敲击声，无背景音乐",
                "emotion": "neutral",
                "confidence": 0.6,
            },
        ],
    },
    "fight": {
        "name": "和朋友吵架",
        "description": "模拟社交冲突场景",
        "messages": [
            {
                "source": "wechat_passive",
                "content": "[微信-好友] 小美: 你要这么想那我也没办法，随便你吧",
                "emotion": "negative",
                "confidence": 0.9,
            },
            {
                "source": "wechat_emotion",
                "content": "[微信情绪分析] 与好友「小美」的对话情绪急剧转负面，出现冲突关键词",
                "emotion": "negative",
                "confidence": 0.88,
            },
            {
                "source": "camera",
                "content": "检测到用户面部表情: sad/frustrated, 嘴角下垂, 眉头紧锁",
                "emotion": "negative",
                "confidence": 0.82,
            },
        ],
    },
}


def inject_scenario(scenario_name: str, delay: float = 2.0):
    """注入一个完整场景的所有消息到 EventStore

    Args:
        scenario_name: 场景名（stressed/lonely/happy/late_night/fight）
        delay: 每条消息之间的间隔秒数，0 表示立即全部注入
    """
    if scenario_name not in SCENARIOS:
        print(f"[Demo] 未知场景: {scenario_name}")
        print(f"[Demo] 可用场景: {', '.join(SCENARIOS.keys())}")
        return False

    scenario = SCENARIOS[scenario_name]
    print(f"\n[Demo] 注入场景「{scenario['name']}」— {scenario['description']}")
    print(f"[Demo] 共 {len(scenario['messages'])} 条消息\n")

    for i, msg in enumerate(scenario["messages"], 1):
        store.add_simple(
            source=msg["source"],
            content=msg["content"],
            emotion=msg.get("emotion", "neutral"),
            confidence=msg.get("confidence", 0.5),
        )
        print(f"  [{i}/{len(scenario['messages'])}] {msg['source']}: {msg['content'][:60]}...")

        if delay > 0 and i < len(scenario["messages"]):
            time.sleep(delay)

    print(f"\n[Demo] 场景「{scenario['name']}」注入完成")
    print(f"[Demo] 现在可以用 /force_check 或 POST /demo/force_check 触发主动对话\n")
    return True


def inject_via_api(scenario_name: str, host: str = "127.0.0.1", port: int = 5000):
    """通过 Web API 注入（Web UI 已启动时使用）"""
    import requests

    if scenario_name not in SCENARIOS:
        print(f"[Demo] 未知场景: {scenario_name}")
        return False

    scenario = SCENARIOS[scenario_name]
    base_url = f"http://{host}:{port}"
    print(f"\n[Demo] 通过 API 注入场景「{scenario['name']}」到 {base_url}\n")

    for i, msg in enumerate(scenario["messages"], 1):
        try:
            resp = requests.post(
                f"{base_url}/demo/inject",
                json=msg,
                timeout=5,
            )
            status = "ok" if resp.status_code == 200 else f"err {resp.status_code}"
            print(f"  [{i}] {status} — {msg['content'][:50]}...")
        except Exception as e:
            print(f"  [{i}] failed — {e}")
        time.sleep(0.5)

    # 注入完成后触发主动检查
    print(f"\n[Demo] 触发主动对话检查...")
    try:
        resp = requests.post(f"{base_url}/demo/force_check", timeout=30)
        data = resp.json()
        if data.get("should_speak"):
            print(f"  咪酱说: {data.get('reply', '')[:80]}...")
        else:
            print(f"  未触发主动对话: {data.get('speak_reason', '')}")
    except Exception as e:
        print(f"  force_check failed: {e}")

    return True


def list_scenarios():
    """列出所有可用场景"""
    print("\n可用 Demo 场景:\n")
    for key, val in SCENARIOS.items():
        print(f"  {key:12s} — {val['name']} ({len(val['messages'])} 条消息)")
        print(f"  {'':12s}   {val['description']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="MiaoAgent Demo 社交消息注入")
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIOS.keys()),
        help="注入的场景名称",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有可用场景",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float, default=2.0,
        help="每条消息之间的间隔秒数 (默认 2.0, 设 0 立即注入)",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="通过 Web API 注入（需要 Web UI 已启动）",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Web UI 地址 (默认 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=5000,
        help="Web UI 端口 (默认 5000)",
    )
    args = parser.parse_args()

    if args.list:
        list_scenarios()
        return

    if not args.scenario:
        parser.print_help()
        print()
        list_scenarios()
        return

    if args.api:
        inject_via_api(args.scenario, args.host, args.port)
    else:
        inject_scenario(args.scenario, delay=args.delay)


if __name__ == "__main__":
    main()
