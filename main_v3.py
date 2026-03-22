"""
main_v3.py — MiaoAgent 主程序（架构更新版）

核心变更（采纳陈昕博建议）：
1. 摄像头：DeepFace (CPU, <200ms) 替代 Gemma-3 (GPU, 5-10s)
2. 文字情感：轻量 DistilBERT (CPU, <10ms) 替代 Gemma-3 兼任
3. 猫咪表情：独立模型判断回复情绪，替代 LLM 输出标签
4. Gemma-3 只负责：融合裁判 (3min) + 猫咪对话生成
5. TTS：标记为本地部署（陈昕博负责 ChatTTS）

算力分配：
  CPU: DeepFace 摄像头 + DistilBERT 文字 + emotion2vec 语音 + PANNs 环境音
  GPU: Gemma-3 仅用于融合裁判和对话生成（低频调用）
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills.shared.event_store import store, Event
from skills.emotion_perception.perception_v2 import PerceptionEngineV2
from skills.proactive_engine.engine_v2 import ProactiveEngineV2
from skills.companion_persona.persona_v2 import CompanionPersonaV2


def main():
    print("=" * 55)
    print("  MiaoAgent v3 — Updated Architecture")
    print("  Camera: DeepFace (CPU)  |  Text: DistilBERT (CPU)")
    print("  Gemma-3: fusion judge + dialogue only")
    print("=" * 55)

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

    perception.start()
    proactive.start()

    print()
    print("[MiaoAgent] Modules:")
    print("  Camera perception: DeepFace (CPU) — OFF, use /camera on")
    print("  Text sentiment:    DistilBERT (CPU) — auto on user messages")
    print("  Fusion judge:      Gemma-3 (GPU) — every 3 min")
    print("  Dialogue:          Gemma-3 (GPU) — on user message")
    print("  TTS:               pending ChatTTS (陈昕博)")
    print()
    print("  Type /help for commands")
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

            # 1. 记录用户交互
            store.mark_user_interaction()

            # 2. 文字情感分析（CPU，<10ms，不占 GPU）
            perception.analyze_user_text(user_input)

            # 3. Gemma-3 生成猫咪回复（这是 Gemma-3 唯一被调用的地方之一）
            print("[Gemma-3 generating...]")
            response = persona.respond(user_message=user_input)

            # 4. 用独立模型判断回复的情绪 → 驱动猫咪表情
            #    （不依赖 LLM 输出标签，永不格式遗忘）
            cat_state = perception.get_cat_state_for_response(response["text"])
            store.set_cat_state(cat_state)

            print(f"\nMiaoJiang [{cat_state}]: {response['text']}\n")

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
  /status          Event store stats
  /events [min]    Show recent events (default 30 min)
  /camera on/off   Toggle camera (DeepFace, CPU)
  /inject <src> <msg>   Inject test event
      Example: /inject camera facial expression: sad (85%)
      Example: /inject voice_emotion voice low and slow
      Example: /inject text_sentiment user said: "好累" → negative
      Example: /inject behavior sedentary for 150 min
  /force_check     Force proactive engine decision
  /benchmark       Show model resource usage
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
            # Generate actual response
            response = persona.respond(
                strategy=decision.get("strategy", "empathetic_listening"),
                proactive_opener=decision.get("opener", "")
            )
            cat_state = perception.get_cat_state_for_response(response["text"])
            store.set_cat_state(cat_state)
            print(f"\nMiaoJiang [{cat_state}]: {response['text']}\n")
        else:
            print()

    elif action == "/benchmark":
        print("""
--- Model Resource Allocation ---
  CPU models (always running):
    DeepFace facial emotion     ~50MB   <200ms/frame
    DistilBERT text sentiment   ~100MB  <10ms/text
    [TODO] emotion2vec voice    ~300MB  <100ms/chunk  (邱靖翔)
    [TODO] PANNs env audio      ~80MB   <100ms/chunk  (邱靖翔)

  GPU models (on-demand):
    Gemma-3-27B dialogue        ~17GB   called only for:
      - fusion judge (every 3 min)
      - user chat response
    [TODO] ChatTTS              ~2GB    (陈昕博)

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
