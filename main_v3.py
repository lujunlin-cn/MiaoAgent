"""
main_v3.py — MiaoAgent 主程序（TRT-LLM + 全模块集成）

推理引擎：
  对话: Qwen3-30B-A3B-FP4 via TRT-LLM (port 8355)
  裁判: Phi-4-multimodal-FP4 via TRT-LLM (port 8356)
  切换: 编辑 skills/shared/inference_config.py

感知层（CPU）：DeepFace + DistilBERT + emotion2vec + env_audio
输出层：Piper TTS + Web UI (port 5000)
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills.shared.event_store import store
from skills.shared.inference_config import CHAT_URL, CHAT_MODEL, JUDGE_URL, JUDGE_MODEL, ENGINE
from skills.emotion_perception.perception_v2 import PerceptionEngineV2
from skills.proactive_engine.engine_v2 import ProactiveEngineV2
from skills.companion_persona.persona_v2 import CompanionPersonaV2
from skills.tts.piper_tts import PiperTTS


def main():
    print("=" * 60)
    print(f"  MiaoAgent v3.2 — Engine: {ENGINE}")
    print(f"  Chat:  {CHAT_MODEL} @ {CHAT_URL}")
    print(f"  Judge: {JUDGE_MODEL} @ {JUDGE_URL}")
    print("  TTS:   Piper (local)  |  Web UI: port 5000")
    print("=" * 60)

    config = {
        "camera_interval": 10,
        "camera_id": 0,
        "enable_camera": False,
        "enable_microphone": False,
    }

    perception = PerceptionEngineV2(config)
    proactive = ProactiveEngineV2(check_interval=180)
    persona = CompanionPersonaV2()
    tts = PiperTTS(auto_play=True)

    perception.start()
    proactive.start()

    print()
    print("[MiaoAgent] Modules:")
    print(f"  Chat:     {CHAT_MODEL} (TRT-LLM)")
    print(f"  Judge:    {JUDGE_MODEL} (TRT-LLM, multimodal)")
    print("  Camera:   DeepFace (CPU) — /camera on")
    print("  Text:     DistilBERT (CPU) — auto")
    print("  TTS:      Piper zh_CN — /voice off to disable")
    print("  Web UI:   python3 frontend/web_ui.py (port 5000)")
    print()
    print("  /help for commands")
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
                handle_command(user_input, perception, proactive, persona, tts)
                continue

            store.mark_user_interaction()
            perception.analyze_user_text(user_input)

            print("[thinking...]")
            response = persona.respond(user_message=user_input)

            cat_state = perception.get_cat_state_for_response(response["text"])
            store.set_cat_state(cat_state)

            print(f"\nMiaoJiang [{cat_state}]: {response['text']}")
            tts.speak(response["text"])
            print()

    except KeyboardInterrupt:
        print()
    finally:
        perception.stop()
        proactive.stop()
        tts.cleanup()
        print("[MiaoAgent] shutdown")


def handle_command(cmd, perception, proactive, persona, tts):
    parts = cmd.strip().lower().split()
    action = parts[0]

    if action == "/help":
        print("""
Commands:
  (just type)         Talk to MiaoJiang
  /camera on/off      Toggle camera (DeepFace CPU)
  /events [min]       Show recent events
  /status             System status
  /voice on/off/test  Toggle or test TTS
  /inject <src> <msg> Inject test event
  /force_check        Force proactive check
  /engine             Show inference engine info
  /benchmark          Model allocation
  /clear              Clear events
  /help               Help
  quit                Exit
""")

    elif action == "/voice":
        if len(parts) < 2:
            print("Usage: /voice on|off|test")
        elif parts[1] == "on":
            tts.toggle(True)
        elif parts[1] == "off":
            tts.toggle(False)
        elif parts[1] == "test":
            wav = tts.speak("喵，你好呀，我是咪酱")
            print(f"  {'✓ ' + wav if wav else '✗ failed'}")

    elif action == "/engine":
        print(f"\n  Chat:  {CHAT_MODEL} @ {CHAT_URL}")
        print(f"  Judge: {JUDGE_MODEL} @ {JUDGE_URL}")
        print(f"  Edit:  skills/shared/inference_config.py\n")

    elif action == "/status":
        s = store.stats()
        print(f"\n  Events: {s['total_events']} ({s['sources']})")
        print(f"  Cat: {s['cat_state']}  TTS: {'ON' if tts._enabled else 'OFF'}")
        print(f"  Last user: {_ago(store.get_last_user_interaction())}")
        print(f"  Last proactive: {_ago(store.get_last_proactive())}\n")

    elif action == "/events":
        minutes = int(parts[1]) if len(parts) > 1 else 30
        print(f"\n{store.get_evidence_text(minutes)}\n")

    elif action == "/camera":
        if len(parts) > 1:
            perception.toggle_channel("camera", parts[1] == "on")

    elif action == "/inject":
        if len(parts) < 3:
            print("Usage: /inject <source> <msg>")
            return
        source = parts[1]
        content = " ".join(parts[2:])
        emotion = "neutral"
        for word, emo in [("tired", "tired"), ("sad", "negative"),
                          ("frown", "negative"), ("happy", "positive"),
                          ("angry", "negative"), ("anxious", "anxious"),
                          ("noise", "negative"), ("negative", "negative"),
                          ("positive", "positive")]:
            if word in content.lower():
                emotion = emo
                break
        store.add_simple(source, content, emotion=emotion, confidence=0.75)
        print(f"  Injected: [{source}] {content}")

    elif action == "/force_check":
        print("\n--- Force proactive check ---")
        decision = proactive.force_check()
        print(f"  should_speak: {decision.get('should_speak')}")
        print(f"  reason: {decision.get('speak_reason', decision.get('reasoning', ''))}")
        if decision.get("should_speak"):
            response = persona.respond(
                strategy=decision.get("strategy", "empathetic_listening"),
                proactive_opener=decision.get("opener", ""))
            cat_state = perception.get_cat_state_for_response(response["text"])
            store.set_cat_state(cat_state)
            print(f"\nMiaoJiang [{cat_state}]: {response['text']}")
            tts.speak(response["text"])
        print()

    elif action == "/benchmark":
        print(f"""
  GPU (TRT-LLM):
    Qwen3-30B-A3B-FP4    ~10GB   dialogue
    Phi-4-multimodal-FP4  ~8GB    fusion judge
  CPU:
    DeepFace ~50MB  |  DistilBERT ~100MB  |  Piper ~60MB
    emotion2vec ~300MB  |  urbansound8k ~80MB
  Total: ~19GB / 128GB
""")

    elif action == "/clear":
        store.clear_all()
    else:
        print(f"Unknown: {cmd}, try /help")


def _ago(ts):
    if ts <= 0:
        return "never"
    mins = (time.time() - ts) / 60
    return "just now" if mins < 1 else f"{mins:.0f} min ago" if mins < 60 else f"{mins/60:.1f}h ago"


if __name__ == "__main__":
    main()
