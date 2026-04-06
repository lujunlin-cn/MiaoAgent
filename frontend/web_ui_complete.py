"""
web_ui.py — MiaoAgent 完全体（Web 版）

这是提交评审的主程序。包含所有功能：
- 真实 Qwen3 对话（TRT-LLM 加速）
- 语义护栏（BGE + 分类器）
- FAISS 长期记忆（跨会话）
- 主动对话引擎（SSE 推送到前端）
- 摄像头 DeepFace 表情检测
- DistilBERT 文字情感 + 表情驱动
- Piper TTS 本地语音
- Whisper 语音识别
- 感知事件注入（Demo 演示用）

启动：python3 frontend/web_ui.py
访问：http://127.0.0.1:5000
"""
import sys
import os
import time
import json
import queue
import threading

# 动态计算项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

try:
    import sounddevice as sd
except (OSError, ImportError, ModuleNotFoundError):
    sd = None

from flask import Flask, render_template, request, jsonify, send_file, Response
from skills.tts.piper_tts import PiperTTS
from skills.audio.realtime_asr import transcribe_audio
from skills.companion_persona.persona_v2 import CompanionPersonaV2
from skills.emotion_perception.perception_v2 import PerceptionEngineV2
from skills.proactive_engine.engine_v2 import ProactiveEngineV2
from skills.shared.event_store import store
from skills.shared.inference_config import ENGINE, CHAT_MODEL, CHAT_URL, JUDGE_MODEL, JUDGE_URL

# 社交消息桥接器（只读）
SOCIAL_BRIDGE_MODE = os.environ.get("MIAOAGENT_SOCIAL_BRIDGE", "demo")  # weclaw | ipad | clawbot | demo | off
_social_bridge = None

def _get_bridge():
    global _social_bridge
    if _social_bridge is None and SOCIAL_BRIDGE_MODE != "off":
        try:
            from skills.bridge.social_bridge import SocialBridge
            kwargs = {}
            if SOCIAL_BRIDGE_MODE == "demo":
                kwargs["interval"] = 60  # demo 模式每分钟一条
            _social_bridge = SocialBridge(mode=SOCIAL_BRIDGE_MODE, **kwargs)
        except Exception as e:
            print(f"[WebUI] social bridge unavailable: {e}")
    return _social_bridge

# ============================================================
# 初始化所有模块
# ============================================================

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path='/static')

tts_engine = PiperTTS(auto_play=False)
persona = CompanionPersonaV2()
perception = PerceptionEngineV2({
    "camera_interval": 10,
    "camera_id": 0,
    "enable_camera": False,
})
proactive = ProactiveEngineV2(check_interval=180)

# SSE 推送队列（线程安全）
_sse_lock = threading.Lock()
sse_clients = []

def broadcast_sse(data: dict):
    """向所有连接的前端推送消息（线程安全）"""
    msg = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    with _sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)

# ============================================================
# 主动对话后台线程
# ============================================================

def proactive_watcher():
    """每 3 分钟检查一次，有主动对话则推送到前端(为了方便演示此处修改为30秒)"""
    while True:
        time.sleep(30)
        try:
            decision = proactive.force_check()
            if decision.get("should_speak"):
                store.mark_proactive()
                proactive.cooldown.record_speak()
                response = persona.respond(
                    strategy=decision.get("strategy", "empathetic_listening"),
                    proactive_opener=decision.get("opener", "")
                )
                bot_reply = response["text"]
                emotion = perception.get_cat_state_for_response(bot_reply)
                store.set_cat_state(emotion)
                wav_path = tts_engine.speak(bot_reply)

                broadcast_sse({
                    "type": "proactive",
                    "reply": bot_reply,
                    "emotion": emotion,
                    "audio": wav_path or "",
                    "reasoning": decision.get("reasoning", ""),
                    "strategy": decision.get("strategy", ""),
                })
                print(f"[Proactive → Web] {bot_reply[:50]}...")
        except Exception as e:
            print(f"[Proactive] error: {e}")

# ============================================================
# 页面路由
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')

# ============================================================
# 核心对话接口
# ============================================================

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '')

    store.mark_user_interaction()
    perception.analyze_user_text(user_input)

    response = persona.respond(user_message=user_input)
    bot_reply = response["text"]

    emotion = perception.get_cat_state_for_response(bot_reply)
    store.set_cat_state(emotion)

    wav_path = tts_engine.speak(bot_reply)

    return jsonify({
        "reply": bot_reply,
        "emotion": emotion,
        "audio": wav_path if wav_path else ""
    })

# ============================================================
# 语音上传接口
# ============================================================

@app.route('/upload_voice', methods=['POST'])
def upload_voice():
    if 'voice' not in request.files:
        return jsonify({"reply": "没收到声音喵", "emotion": "curious"})

    voice_file = request.files['voice']
    save_path = "/tmp/browser_voice.wav"
    voice_file.save(save_path)

    recognized_text = transcribe_audio(save_path)

    store.mark_user_interaction()
    perception.analyze_user_text(recognized_text)

    response = persona.respond(user_message=recognized_text)
    bot_reply = response["text"]

    emotion = perception.get_cat_state_for_response(bot_reply)
    store.set_cat_state(emotion)

    wav_path = tts_engine.speak(bot_reply)

    return jsonify({
        "reply": bot_reply,
        "emotion": emotion,
        "recognized_text": recognized_text,
        "audio": wav_path if wav_path else ""
    })

# ============================================================
# SSE 推送（主动对话 + 感知事件）
# ============================================================

@app.route('/events/stream')
def event_stream():
    q = queue.Queue()
    with _sse_lock:
        sse_clients.append(q)
    def generate():
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except GeneratorExit:
            with _sse_lock:
                if q in sse_clients:
                    sse_clients.remove(q)
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

# ============================================================
# TTS 音频服务
# ============================================================

@app.route('/tts/<path:filename>')
def serve_tts(filename):
    return send_file(f"/tmp/miaoagent_tts/{filename}", mimetype="audio/wav")

# ============================================================
# 系统状态接口
# ============================================================

@app.route('/status')
def status():
    s = store.stats()
    memory_stats = {"ready": False, "count": 0}
    try:
        from skills.memory.conversation_memory import get_memory
        memory_stats = get_memory().stats()
    except Exception:
        pass

    return jsonify({
        "cat_state": s["cat_state"],
        "total_events": s["total_events"],
        "sources": s["sources"],
        "last_user": store.get_last_user_interaction(),
        "last_proactive": store.get_last_proactive(),
        "memory_count": memory_stats.get("count", 0),
        "camera": perception.channels.get("camera", False),
        "social_bridge": _social_bridge.stats() if _social_bridge else {"mode": "off"},
    })

# ============================================================
# 社交消息桥接状态
# ============================================================

@app.route('/social/status')
def social_status():
    """社交消息桥接器状态"""
    bridge = _get_bridge()
    if not bridge:
        return jsonify({"mode": "off", "running": False})
    return jsonify(bridge.stats())

@app.route('/social/messages')
def social_messages():
    """最近的社交消息事件（用于前端展示）"""
    minutes = request.args.get('minutes', 60, type=int)
    events = store.get_recent(minutes=minutes)
    social_events = [
        {
            "time": time.strftime("%H:%M", time.localtime(e.time)),
            "source": e.source,
            "content": e.content,
            "emotion": e.raw_label.get("emotion", "neutral"),
        }
        for e in events
        if e.source in ("wechat_passive", "wechat_emotion", "wechat_trend",
                         "qq_passive", "qq_emotion", "qq_trend")
    ]
    return jsonify({"messages": social_events, "count": len(social_events)})

# ============================================================
# 摄像头控制
# ============================================================

@app.route('/camera/toggle', methods=['POST'])
def toggle_camera():
    action = request.json.get('action', 'toggle')
    if action == 'on':
        perception.toggle_channel("camera", True)
        enabled = True
    elif action == 'off':
        perception.toggle_channel("camera", False)
        enabled = False
    else:
        current = perception.channels.get("camera", False)
        perception.toggle_channel("camera", not current)
        enabled = not current
    return jsonify({"camera": "on" if enabled else "off"})

# ============================================================
# 感知事件查看
# ============================================================

@app.route('/events/list')
def events_list():
    minutes = request.args.get('minutes', 30, type=int)
    text = store.get_evidence_text(minutes)
    return jsonify({"events": text, "minutes": minutes})

# ============================================================
# 记忆管理接口
# ============================================================

@app.route('/memory/clear', methods=['POST'])
def memory_clear():
    """清空 EventStore 短期事件 + FAISS 长期记忆"""
    target = request.json.get('target', 'all') if request.is_json else 'all'

    result = {}

    if target in ('all', 'events'):
        store.clear_all()
        result['events'] = 'cleared'

    if target in ('all', 'memory'):
        try:
            from skills.memory.conversation_memory import get_memory
            mem = get_memory()
            mem.clear()
            result['memory'] = 'cleared'
        except Exception as e:
            result['memory'] = f'error: {e}'

    if target in ('all', 'history'):
        persona.history.clear()
        result['history'] = 'cleared'

    print(f"[WebUI] memory clear: target={target}, result={result}")
    return jsonify({"status": "ok", **result})

# ============================================================
# Demo 演示接口（注入事件 + 强制检查）
# ============================================================

@app.route('/demo/inject', methods=['POST'])
def demo_inject():
    """注入测试事件，Demo 演示用"""
    source = request.json.get('source', 'camera')
    content = request.json.get('content', '')
    emotion = request.json.get('emotion', 'neutral')
    confidence = request.json.get('confidence', 0.75)

    store.add_simple(source, content, emotion=emotion, confidence=confidence)

    # 同时推送到前端
    broadcast_sse({
        "type": "event",
        "source": source,
        "content": content,
        "emotion": emotion,
    })

    return jsonify({"status": "ok", "source": source, "content": content})

@app.route('/demo/force_check', methods=['POST'])
def demo_force_check():
    """强制触发主动对话检查，Demo 演示用"""
    decision = proactive.force_check()

    if decision.get("should_speak"):
        store.mark_proactive()
        response = persona.respond(
            strategy=decision.get("strategy", "empathetic_listening"),
            proactive_opener=decision.get("opener", "")
        )
        bot_reply = response["text"]
        emotion = perception.get_cat_state_for_response(bot_reply)
        store.set_cat_state(emotion)
        wav_path = tts_engine.speak(bot_reply)

        broadcast_sse({
            "type": "proactive",
            "reply": bot_reply,
            "emotion": emotion,
            "audio": wav_path or "",
            "reasoning": decision.get("reasoning", ""),
        })

        decision["reply"] = bot_reply
        decision["emotion"] = emotion
        decision["audio"] = wav_path or ""

    return jsonify(decision)

# ============================================================
# 启动
# ============================================================


# ============================================================
# 优雅退出：保存记忆
# ============================================================
import atexit
import signal

def _shutdown_cleanup():
    """进程退出时保存 FAISS 记忆到磁盘"""
    try:
        from skills.memory.conversation_memory import get_memory
        mem = get_memory()
        if mem:
            mem.save()
            print("[WebUI] memory saved on shutdown")
    except Exception as e:
        print(f"[WebUI] shutdown save error: {e}")

atexit.register(_shutdown_cleanup)

def _signal_handler(sig, frame):
    print("\n[WebUI] Ctrl+C received, saving and exiting...")
    _shutdown_cleanup()
    raise SystemExit(0)

signal.signal(signal.SIGINT, _signal_handler)

if __name__ == '__main__':
    print("=" * 60)
    print(f"  MiaoAgent Web UI — Engine: {ENGINE}")
    print(f"  Chat:  {CHAT_MODEL} @ {CHAT_URL}")
    print(f"  Judge: {JUDGE_MODEL} @ {JUDGE_URL}")
    print("  TTS:   Piper (local)  |  Guard: Semantic + Regex")
    print("  Memory: FAISS long-term")
    print(f"  Social: {SOCIAL_BRIDGE_MODE}")
    print("=" * 60)

    # 启动感知引擎
    perception.start()
    print("[WebUI] Perception started")

    # 启动主动对话引擎（后台线程，含 SSE 推送）
    # 注意：不调 proactive.start()，因为 proactive_watcher 已经每 180s
    # 调用 force_check() 并处理 SSE 推送，再 start() 会导致双重检查
    threading.Thread(target=proactive_watcher, daemon=True).start()
    print("[WebUI] Proactive engine started (SSE push enabled)")

    # 启动社交消息桥接器（只读）
    bridge = _get_bridge()
    if bridge:
        bridge.start()
        print(f"[WebUI] Social bridge started (mode={SOCIAL_BRIDGE_MODE})")
    else:
        print(f"[WebUI] Social bridge: off")

    print()
    print("[WebUI] Access: http://127.0.0.1:5000")
    print("[WebUI] Remote:  ssh -L 5000:127.0.0.1:5000 user@spark")
    print()
    print("[WebUI] Demo APIs:")
    print("  POST /demo/inject       注入测试事件")
    print("  POST /demo/force_check  强制主动对话")
    print("  POST /memory/clear      清空记忆（events/memory/history/all）")
    print("  GET  /events/list       查看感知事件")
    print("  GET  /status            系统状态")
    print("  POST /camera/toggle     摄像头开关")
    print("  GET  /social/status     社交桥接状态")
    print("  GET  /social/messages   社交消息列表")
    print()

    app.run(host='0.0.0.0', port=5000, threaded=True)
