import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills.emotion_perception.perception import PerceptionEngine
from skills.proactive_engine.engine import ProactiveEngine
from skills.companion_persona.persona import CompanionPersona
from skills.shared.signal_bus import bus


def main():
    print("=" * 50)
    print("  MiaoAgent (CatAgent) starting...")
    print("=" * 50)

    config = {
        "ollama_url": "http://localhost:11434",
        "camera_interval": 10,
        "camera_id": 0,
        "enable_camera": False,   # start without camera, enable with /camera on
        "enable_microphone": False,
        "enable_env_audio": False,
    }

    perception = PerceptionEngine(config)
    proactive = ProactiveEngine(
        ollama_url=config["ollama_url"],
        check_interval=180
    )
    persona = CompanionPersona(ollama_url=config["ollama_url"])

    # Start perception and proactive engine
    perception.start()
    proactive.start()

    print()
    print("[MiaoAgent] All modules started")
    print("[MiaoAgent] Camera: OFF (use /camera on to enable)")
    print("[MiaoAgent] Proactive check: every 3 min")
    print("[MiaoAgent] Type a message to chat, /help for commands")
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
                handle_command(user_input, perception)
                continue

            # Generate cat response
            print("[thinking...]")
            response = persona.generate_response(user_message=user_input)
            bus.set_cat_state(response["cat_state"])
            print(f"\nMiaoJiang [{response['cat_state']}]: {response['text']}\n")

    except KeyboardInterrupt:
        print()
    finally:
        perception.stop()
        proactive.stop()
        print("[MiaoAgent] shutdown complete")


def handle_command(cmd, perception):
    cmd = cmd.strip().lower()

    if cmd == "/status":
        state = bus.get_state()
        print(f"\n--- Current State ---")
        print(f"  Mood score: {state.mood_score:.2f}")
        print(f"  Cat state:  {state.cat_state}")
        print(f"  Visual:     {state.visual_signal}")
        print(f"  Voice emo:  {state.voice_emotion}")
        print(f"  Env audio:  {state.env_audio}")
        print(f"  Behavior:   {state.behavior}")
        print(f"  History:    {len(state.mood_history)} entries")
        print(f"--- --- ---\n")

    elif cmd == "/camera on":
        perception.toggle_channel("camera", True)
    elif cmd == "/camera off":
        perception.toggle_channel("camera", False)

    elif cmd == "/help":
        print("\nCommands:")
        print("  /status        Show perception state")
        print("  /camera on/off Toggle camera")
        print("  /help          This help")
        print("  quit           Exit\n")

    else:
        print(f"Unknown command: {cmd}, try /help")


if __name__ == "__main__":
    main()
