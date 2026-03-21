"""
main_v2.py — MiaoAgent 主程序（事件驱动架构）

变更：
- 使用 EventStore 替代 SignalBus + mood_score
- 决策引擎改为事件驱动
- 新增 /events /force_check 等调试命令
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills.shared.event_store import store, Event
from skills.emotion_perception.perception import PerceptionEngine
from skills.proactive_engine.engine_v2 import ProactiveEngineV2
from skills.companion_persona.persona_v2 import CompanionPersonaV2


def main():
    print("=" * 50)
    print("  MiaoAgent v2 (Event-Driven Architecture)")
    print("=" * 50)

    config = {
        "ollama_url": "http://localhost:11434",
        "camera_interval": 10,
        "camera_id": 0,
        "enable_camera": False,
        "enable_microphone": False,
        "enable_env_audio": False,
    }

    perception = PerceptionEngine(config)
    proactive = ProactiveEngineV2(
        ollama_url=config["ollama_url"],
        check_interval=180
    )
    persona = CompanionPersonaV2(ollama_url=config["ollama_url"])

    perception.start()
    proactive.start()

    print()
    print("[MiaoAgent] All modules started")
    print("[MiaoAgent] Camera: OFF (use /camera on)")
    print("[MiaoAgent] Proactive: every 3 min")
    print("[MiaoAgent] Type /help for commands")
    print()

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', '/quit']:
                break

            if user_input.startswith('/'):
                handle_command(user_input, perception, proactive, persona)
                continue

            # Record user interaction
            store.mark_user_interaction()

            # Generate response
            print("[thinking...]")
            response = persona.respond(user_message=user_input)
            store.set_cat_state(response["cat_state"])
            print(f"\nMiaoJiang [{response['cat_state']}]: {response['text']}\n")

    except KeyboardInterrupt:
        print()
    finally:
        perception.stop()
        proactive.stop()
        print("[MiaoAgent] shutdown")


def handle_command(cmd, perception, proactive, persona):
    parts = cmd.strip().lower().split()
    action = parts[0]

    if action == "/help":
        print("""
Commands:
  /status          Show event store stats
  /events          Show recent events (last 30 min)
  /events 60       Show events from last 60 min
  /camera on/off   Toggle camera perception
  /inject <src> <msg>   Inject a test event
      Example: /inject camera user is frowning, looks tired
      Example: /inject env_audio loud construction noise
  /force_check     Force proactive engine to check now
  /clear           Clear all events
  /help            This help
  quit             Exit
""")

    elif action == "/status":
        s = store.stats()
        print(f"\n--- Event Store ---")
        print(f"  Total events: {s['total_events']}")
        print(f"  Sources: {s['sources']}")
        print(f"  Cat state: {s['cat_state']}")
        print(f"  Oldest event: {s['oldest_event_age_min']:.1f} min ago")
        print(f"  Last user msg: {_ago(store.get_last_user_interaction())}")
        print(f"  Last proactive: {_ago(store.get_last_proactive())}")
        print(f"--- ---\n")

    elif action == "/events":
        minutes = int(parts[1]) if len(parts) > 1 else 30
        print(f"\n{store.get_evidence_text(minutes)}\n")

    elif action == "/camera":
        if len(parts) > 1 and parts[1] == "on":
            perception.toggle_channel("camera", True)
        elif len(parts) > 1 and parts[1] == "off":
            perception.toggle_channel("camera", False)
        else:
            print("Usage: /camera on  or  /camera off")

    elif action == "/inject":
        # /inject camera user is frowning, looks tired
        if len(parts) < 3:
            print("Usage: /inject <source> <description>")
            print("Sources: camera, voice_emotion, env_audio, whisper, behavior, watch")
            return
        source = parts[1]
        content = " ".join(parts[2:])
        # Try to guess emotion from content
        emotion = "neutral"
        for word, emo in [("tired", "tired"), ("sad", "negative"),
                          ("frown", "negative"), ("happy", "positive"),
                          ("smile", "positive"), ("anxious", "anxious"),
                          ("noise", "negative"), ("cry", "negative"),
                          ("laugh", "positive"), ("sigh", "negative")]:
            if word in content.lower():
                emotion = emo
                break
        store.add_simple(source, content, emotion=emotion, confidence=0.75)
        print(f"  Injected: [{source}] {content}")

    elif action == "/force_check":
        print("\n--- Forcing proactive check ---")
        decision = proactive.force_check()
        print(f"  should_speak: {decision.get('should_speak')}")
        print(f"  reason: {decision.get('speak_reason', decision.get('reasoning', ''))}")
        if decision.get("should_speak"):
            print(f"  strategy: {decision.get('strategy')}")
            print(f"  opener: {decision.get('opener')}")
            # Actually generate the response
            response = persona.respond(
                strategy=decision.get("strategy", "empathetic_listening"),
                proactive_opener=decision.get("opener", "")
            )
            store.set_cat_state(response["cat_state"])
            print(f"\nMiaoJiang [{response['cat_state']}]: {response['text']}\n")
        else:
            print()

    elif action == "/clear":
        store.clear_all()

    else:
        print(f"Unknown: {cmd}, try /help")


def _ago(ts):
    if ts <= 0:
        return "never"
    mins = (time.time() - ts) / 60
    if mins < 1:
        return "just now"
    elif mins < 60:
        return f"{mins:.0f} min ago"
    else:
        return f"{mins/60:.1f} hours ago"


if __name__ == "__main__":
    main()
