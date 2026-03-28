import sys
import os
sys.path.append("/opt/catagent")

try:
    import sounddevice as sd
except OSError:
    # 如果系统没装 PortAudio，我们只打印警告，不让整个程序崩溃
    print("提示: 服务器本地音频驱动未就绪，但不影响网页录音功能。")
    sd = None
from flask import Flask, render_template, request, jsonify
from skills.tts.piper_tts import PiperTTS
from skills.audio.realtime_asr import transcribe_audio

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path='/static')
tts_engine = PiperTTS(auto_play=True)

@app.route('/')
def index():
    return render_template('index.html')

# 文本聊天接口（模拟 Qwen）
@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '')
    bot_reply = f"喵！虽然队长还在修我的 Qwen 大脑，但我听到你说：{user_input}"
    
    # 模拟情绪切换（你可以多加几个词测试图片）
    current_emotion = "happy"
    if "累" in user_input: current_emotion = "sleepy"
    elif "抱" in user_input: current_emotion = "seeking_attention"
    
    tts_engine.speak(bot_reply)
    return jsonify({"reply": bot_reply, "emotion": current_emotion})

# 语音上传接口（浏览器录音传过来）
@app.route('/upload_voice', methods=['POST'])
def upload_voice():
    if 'voice' not in request.files:
        return jsonify({"reply": "没收到声音喵", "emotion": "curious"})
    
    # 1. 保存浏览器发来的录音
    voice_file = request.files['voice']
    save_path = "/tmp/browser_voice.wav"
    voice_file.save(save_path)
    
    # 2. 模拟 Whisper 识别（等队长部署好 Whisper，这里换成真实调用）
    recognized_text = transcribe_audio(save_path)
    bot_reply = f"喵！我听懂了你的录音，你说：{recognized_text}"
    
    tts_engine.speak(bot_reply)
    return jsonify({"reply": bot_reply, "emotion": "alert"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)