"""
main_v3.py — MiaoAgent 主程序（集成 Piper TTS）

新增：
- /voice on/off  开关语音输出
- /voice test    测试 TTS
- 猫咪每次回复后自动生成并播放语音
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills.shared.event_store import store, Event
from skills.emotion_perception.perception_v2 import PerceptionEngineV2
from skills.proactive_engine.engine_v2 import ProactiveEngineV2
from skills.companion_persona.persona_v2 import CompanionPersonaV2
from skills.tts.piper_tts import PiperTTS


def main():
    print("=" * 58)
    print("  MiaoAgent v3.1 — With Local TTS")
    print("  Camera: DeepFace (CPU)  |  Text: DistilBERT (CPU)")
    print("  TTS: Piper (CPU, local) |  LLM: Gemma-3 → TRT-LLM")
    print("=" * 58)

    config = {
        "ollama_url": "http://localhost:11434",
        "camera_interval": 10,
        "camera_id": 0,
        "enable_camera": False,
        "enable_microphone": False,
    }

    # 初始化模块
    perception = PerceptionEngineV2(config)
    proactive = ProactiveEngineV2(
        ollama_url=config["ollama_url"],
        check_interval=180
    )
    persona = CompanionPersonaV2(ollama_url=config["ollama_url"])
    tts = PiperTTS(auto_play=True)  # 自动播放语音

    perception.start()
    proactive.start()

    print()
    print("[MiaoAgent] Modules:")
    print("  Camera:     DeepFace (CPU) — OFF, /camera on")
    print("  Text:       DistilBERT (CPU) — auto")
    print("  TTS:        Piper (CPU, local) — ON, /voice off to disable")
    print("  LLM:        Gemma-3 / TRT-LLM — fusion + dialogue")
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

            # 1. 记录用户交互
            store.mark_user_interaction()

            # 2. 文字情感分析（CPU，<10ms）
            perception.analyze_user_text(user_input)

            # 3. Gemma-3 / TRT-LLM 生成猫咪回复
            print("[thinking...]")
            response = persona.respond(user_message=user_input)

            # 4. 判断回复情绪 → 驱动猫咪表情
            cat_state = perception.get_cat_state_for_response(response["text"])
            store.set_cat_state(cat_state)

            # 5. 显示回复
            print(f"\nMiaoJiang [{cat_state}]: {response['text']}")

            # 6. TTS 语音输出（后台播放，不阻塞）
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
  --- 对话 ---
  直接打字          和猫咪对话（自动语音输出）

  --- 感知 ---
  /camera on/off    摄像头（DeepFace CPU）
  /events [min]     查看感知事件
  /status           系统状态

  --- 语音 ---
  /voice on         开启语音（默认开启）
  /voice off        关闭语音（只显示文字）
  /voice test       测试一句 TTS

  --- 主动对话 ---
  /inject <src> <msg>   注入测试事件
  /force_check          强制触发主动对话检查

  --- 系统 ---
  /benchmark        模型资源分配
  /clear            清空事件
  /help             帮助
  quit              退出
""")

    elif action == "/voice":
        if len(parts) < 2:
            print("Usage: /voice on|off|test")
        elif parts[1] == "on":
            tts.toggle(True)
        elif parts[1] == "off":
            tts.toggle(False)
        elif parts[1] == "test":
            print("[TTS test] generating...")
            wav = tts.speak("喵，你好呀，我是咪酱，很高兴认识你")
            if wav:
                print(f"  ✓ {wav}")
            else:
                print("  ✗ TTS failed")
        else:
            print("Usage: /voice on|off|test")

    elif action == "/status":
        s = store.stats()
        print(f"\n--- System Status ---")
        print(f"  Events: {s['total_events']} ({s['sources']})")
        print(f"  Cat state: {s['cat_state']}")
        print(f"  Last user msg: {_ago(store.get_last_user_interaction())}")
        print(f"  Last proactive: {_ago(store.get_last_proactive())}")
        print(f"  TTS: {'ON' if tts._enabled else 'OFF'}")
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
            print("Usage: /camera on | off")

    elif action == "/inject":
        if len(parts) < 3:
            print("Usage: /inject <source> <description>")
            return
        source = parts[1]
        content = " ".join(parts[2:])
        emotion = "neutral"
        for word, emo in [("tired", "tired"), ("sad", "negative"),
                          ("frown", "negative"), ("happy", "positive"),
                          ("angry", "negative"), ("anxious", "anxious"),
                          ("noise", "negative"), ("cry", "negative"),
                          ("fear", "anxious"), ("disgust", "negative"),
                          ("surprise", "positive"), ("negative", "negative"),
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
        reason = decision.get('speak_reason', decision.get('reasoning', ''))
        print(f"  reason: {reason}")
        if decision.get("should_speak"):
            print(f"  strategy: {decision.get('strategy')}")
            print(f"  opener: {decision.get('opener')}")
            response = persona.respond(
                strategy=decision.get("strategy", "empathetic_listening"),
                proactive_opener=decision.get("opener", "")
            )
            cat_state = perception.get_cat_state_for_response(response["text"])
            store.set_cat_state(cat_state)
            print(f"\nMiaoJiang [{cat_state}]: {response['text']}")
            tts.speak(response["text"])
            print()
        else:
            print()

    elif action == "/benchmark":
        print("""
--- Model Resource Allocation ---
  CPU models (always running):
    DeepFace facial emotion     ~50MB    <200ms/frame
    DistilBERT text sentiment   ~100MB   <10ms/text
    Piper TTS zh_CN-huayan      ~60MB    <500ms/sentence
    [TODO] emotion2vec voice    ~300MB   (邱靖翔)
    [TODO] PANNs env audio      ~80MB    (邱靖翔)

  GPU models (on-demand, via TRT-LLM or Ollama):
    Qwen3-30B-A3B-FP4          ~10GB    dialogue (MoE, fast)
    Phi-4-multimodal-FP4       ~8GB     fusion judge (vision+audio)
    [fallback] Gemma-3-27B     ~17GB    via Ollama if TRT-LLM down

  Total: ~20GB / 128GB available
--- ---
""")

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
        return f"{mins / 60:.1f} hours ago"


if __name__ == "__main__":
    main()
