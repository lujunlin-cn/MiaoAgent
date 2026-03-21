from skills.shared.signal_bus import EmotionSignal
import cv2
import time
import threading
import base64
import json
import numpy as np
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from skills.shared.event_store import store


class CameraPerception:
    def __init__(self, ollama_url="http://localhost:11434", capture_interval=10, camera_id=0):
        self.ollama_url = ollama_url
        self.capture_interval = capture_interval
        self.camera_id = camera_id
        self._running = False

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        print("[CameraPerception] started")

    def stop(self):
        self._running = False

    def _loop(self):
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print("[CameraPerception] ERROR: cannot open camera")
            return
        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                continue
            try:
                sig = self._analyze_frame(frame)
                if sig:
                    store.add_simple("camera", sig.detail, emotion=sig.emotion, confidence=sig.confidence)
                    print(f"[CameraPerception] {sig.emotion} ({sig.confidence:.2f}): {sig.detail}")
            except Exception as e:
                print(f"[CameraPerception] error: {e}")
            del frame
            time.sleep(self.capture_interval)
        cap.release()

    def _analyze_frame(self, frame):
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        img_b64 = base64.b64encode(buf).decode('utf-8')
        resp = requests.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": "gemma3:27b",
                "messages": [{"role": "user", "content": 'Analyze the emotion of the person in this image. Output ONLY JSON: {"emotion":"positive/neutral/negative/tired/anxious","confidence":0.0-1.0,"detail":"description"}', "images": [img_b64]}],
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=60
        )
        content = resp.json()["message"]["content"]
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            return EmotionSignal(
                source="camera",
                emotion=data.get("emotion", "neutral"),
                confidence=data.get("confidence", 0.5),
                detail=data.get("detail", ""),
                timestamp=time.time()
            )
        return None


class BehaviorDetector:
    def __init__(self):
        self.last_motion_time = time.time()
        self.prev_gray = None

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self.prev_gray is None:
            self.prev_gray = gray
            return "just started"
        delta = cv2.absdiff(self.prev_gray, gray)
        motion = np.mean(delta)
        self.prev_gray = gray
        if motion > 5.0:
            self.last_motion_time = time.time()
        sed_min = (time.time() - self.last_motion_time) / 60
        hour = time.localtime().tm_hour
        parts = []
        if sed_min > 120:
            parts.append(f"sedentary for {sed_min:.0f} min")
        elif sed_min > 60:
            parts.append(f"sedentary for ~{sed_min:.0f} min")
        if 1 <= hour <= 5:
            parts.append("late night, still at computer")
        elif hour >= 23:
            parts.append("near midnight, not resting")
        return "; ".join(parts) if parts else "activity normal"


class PerceptionEngine:
    def __init__(self, config=None):
        config = config or {}
        self.camera = CameraPerception(
            ollama_url=config.get("ollama_url", "http://localhost:11434"),
            capture_interval=config.get("camera_interval", 10),
            camera_id=config.get("camera_id", 0)
        )
        self.channels = {
            "camera": config.get("enable_camera", True),
            "microphone": config.get("enable_microphone", True),
            "env_audio": config.get("enable_env_audio", True),
        }

    def start(self):
        if self.channels["camera"]:
            self.camera.start()
        print("[PerceptionEngine] started")

    def stop(self):
        self.camera.stop()
        print("[PerceptionEngine] stopped")

    def toggle_channel(self, channel, enabled):
        self.channels[channel] = enabled
        if channel == "camera":
            if enabled:
                self.camera.start()
            else:
                self.camera.stop()
        print(f"[PerceptionEngine] {channel} {'ON' if enabled else 'OFF'}")
