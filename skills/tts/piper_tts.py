"""
piper_tts.py — Piper TTS 本地语音合成

特点：
- 纯本地，数据不出设备（满足隐私要求）
- ARM64 原生支持（ONNX 推理）
- 毫秒级生成（比 ChatTTS 快几百倍）
- CPU 运行，不占 GPU
"""
import subprocess
import os
import time
import hashlib
import threading


class PiperTTS:
    def __init__(self, 
                 model_path=None,
                 output_dir="/tmp/miaoagent_tts",
                 auto_play=False):
        # 默认模型路径
        if model_path is None:
            _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            model_path = os.path.join(_root, "models", "piper", "zh_CN-huayan-medium.onnx")
        # 默认模型路径
        if model_path is None:
            _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            model_path = os.path.join(_root, "models", "piper", "zh_CN-huayan-medium.onnx")
        self.model_path = model_path
        self.output_dir = output_dir
        self.auto_play = auto_play
        self._enabled = True
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 检查模型文件
        if not os.path.exists(model_path):
            print(f"[PiperTTS] WARNING: model not found at {model_path}")
            print(f"[PiperTTS] TTS disabled. Download model first.")
            self._enabled = False
        else:
            print(f"[PiperTTS] ready (model: {os.path.basename(model_path)})")

    def speak(self, text: str) -> str:
        """生成语音并返回 wav 文件路径
        
        Args:
            text: 要合成的中文文本
        Returns:
            wav 文件路径，失败返回空字符串
        """
        if not self._enabled or not text.strip():
            return ""
        
        # 生成唯一文件名
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        timestamp = int(time.time())
        wav_path = os.path.join(self.output_dir, f"tts_{timestamp}_{text_hash}.wav")
        
        try:
            start = time.time()
            
            result = subprocess.run(
                ["piper",
                 "--model", self.model_path,
                 "--output_file", wav_path],
                input=text,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            elapsed = time.time() - start
            
            if result.returncode != 0:
                print(f"[PiperTTS] error: {result.stderr[:200]}")
                return ""
            
            if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                size_kb = os.path.getsize(wav_path) / 1024
                print(f"[PiperTTS] generated {size_kb:.0f}KB in {elapsed:.2f}s → {wav_path}")
                
                # 自动播放
                if self.auto_play:
                    self._play_async(wav_path)
                
                return wav_path
            else:
                print("[PiperTTS] error: output file empty")
                return ""
                
        except subprocess.TimeoutExpired:
            print("[PiperTTS] error: timeout")
            return ""
        except Exception as e:
            print(f"[PiperTTS] error: {e}")
            return ""

    def _play_async(self, wav_path: str):
        """后台播放音频，不阻塞主线程"""
        def _play():
            try:
                subprocess.run(
                    ["mpv", "--no-terminal", wav_path],
                    capture_output=True,
                    timeout=30
                )
            except Exception:
                pass
        
        t = threading.Thread(target=_play, daemon=True)
        t.start()

    def toggle(self, enabled: bool):
        """开关 TTS"""
        self._enabled = enabled
        print(f"[PiperTTS] {'ON' if enabled else 'OFF'}")

    def cleanup(self, max_files=50):
        """清理旧的 TTS 文件，只保留最近 N 个"""
        try:
            files = sorted(
                [os.path.join(self.output_dir, f) 
                 for f in os.listdir(self.output_dir) if f.endswith('.wav')],
                key=os.path.getmtime
            )
            while len(files) > max_files:
                os.remove(files.pop(0))
        except Exception:
            pass
