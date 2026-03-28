import os
import time
import numpy as np
import scipy.io.wavfile as wav

# --- [注意] 为了绕过服务器 PortAudio 驱动报错，已暂时注释本地录音库 ---
# try:
#     import sounddevice as sd
# except Exception:
#     sd = None

# 1. 核心任务：Whisper 模型加载
try:
    import whisper
    print(">>> 正在加载 Whisper 模型 (base) 到显存...")
    # 提前加载模型，避免每次对话重复加载
    model = whisper.load_model("base") 
except ImportError:
    print("警告: 未安装 openai-whisper，请执行 pip3 install openai-whisper")
    model = None

def transcribe_audio(audio_path):
    """
    调用 Whisper 将音频转为文字
    此函数直接服务于网页端的语音上传接口。
    """
    if model is None:
        return "喵... 我的耳朵（Whisper）还没准备好。"
    
    if not os.path.exists(audio_path):
        return "语音文件去哪了喵？我找不到了。"

    print(f">>> Whisper 启动识别: {audio_path}")
    start_time = time.time()
    
    # transcribe 会自动处理重采样和预处理
    # 指定 language="zh" 确保识别出来的都是可爱的中文喵
    result = model.transcribe(audio_path, language="zh") 
    
    print(f">>> 识别完成，耗时: {time.time() - start_time:.2f} 秒")
    return result["text"]

# 2. 任务交付备份：VAD 录音逻辑 (已完成开发，因驱动问题暂时注释)
# def record_until_silence(filename="/tmp/server_mic.wav", samplerate=16000, silence_threshold=0.015, silence_duration=1.5):
#     """
#     使用 sounddevice 录音并判断静音自动停止
#     """
#     print(">>> [服务器录音] 开始录音...")
#     recorded_frames = []
#     silent_frames_count = 0
#     chunk_duration = 0.5 
#     chunk_samples = int(samplerate * chunk_duration)
#     max_silence_chunks = int(silence_duration / chunk_duration)
#     
#     try:
#         import sounddevice as sd
#         with sd.InputStream(samplerate=samplerate, channels=1) as stream:
#             while True:
#                 audio_chunk, _ = stream.read(chunk_samples)
#                 recorded_frames.append(audio_chunk)
#                 rms = np.sqrt(np.mean(audio_chunk**2))
#                 if rms < silence_threshold:
#                     silent_frames_count += 1
#                 else:
#                     silent_frames_count = 0
#                 if silent_frames_count >= max_silence_chunks:
#                     break
#         audio_data = np.concatenate(recorded_frames, axis=0)
#         wav.write(filename, samplerate, (audio_data * 32767).astype(np.int16))
#         return filename
#     except Exception as e:
#         print(f"录音失败: {e}")
#         return None

if __name__ == "__main__":
    # 独立测试模式
    print("--- Whisper 识别模块测试 ---")
    # 找一个刚才上传的临时录音来测试
    test_path = "/tmp/browser_voice.wav"
    if os.path.exists(test_path):
        result_text = transcribe_audio(test_path)
        print(f"识别出的文字: {result_text}")
    else:
        print(f"请先去网页上录一段音生成 {test_path}")