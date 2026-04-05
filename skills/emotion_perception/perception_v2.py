"""
perception_v2.py — 轻量感知引擎（架构更新版）

核心变更（采纳陈昕博建议）：
- 摄像头表情：Gemma-3 (5-10s/帧) → DeepFace (CPU, <200ms/帧)
- 文字情感：Gemma-3 兼任 → 轻量 transformers 模型 (CPU, <10ms)
- Gemma-3 只保留：融合裁判(3min) + 猫咪对话生成

这样 Gemma-3 的调用频率从每10秒降到每3分钟，并发冲突消除
"""
import cv2
import os
import time
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import threading
import numpy as np

from skills.shared.event_store import store, Event


# ============================================================
# 模块 A: 摄像头表情感知（DeepFace，CPU，<200ms）
# ============================================================

class CameraPerceptionV2:
    """使用 DeepFace 轻量模型检测表情，不占 GPU"""

    # DeepFace 7类情绪 → 我们的 5 类映射
    EMOTION_MAP = {
        "happy": "positive",
        "surprise": "positive",
        "neutral": "neutral",
        "sad": "negative",
        "angry": "negative",
        "disgust": "negative",
        "fear": "anxious",
    }

    def __init__(self, capture_interval=10, camera_id=0):
        self.capture_interval = capture_interval
        self.camera_id = camera_id
        self._running = False
        self._deepface = None

    def _load_model(self):
        """延迟加载 DeepFace（第一次调用时才加载）"""
        if self._deepface is None:
            try:
                from deepface import DeepFace
                self._deepface = DeepFace
                print("[CameraV2] DeepFace loaded (CPU mode)")
            except ImportError:
                print("[CameraV2] ERROR: pip3 install deepface --break-system-packages")
                return False
        return True

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        print("[CameraV2] started")

    def stop(self):
        self._running = False

    def _loop(self):
        if not self._load_model():
            return

        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print("[CameraV2] ERROR: cannot open camera")
            return

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                continue

            try:
                result = self._analyze(frame)
                if result:
                    emotion, confidence, detail = result
                    store.add_simple(
                        source="camera",
                        content=detail,
                        emotion=emotion,
                        confidence=confidence
                    )
                    print(f"[CameraV2] {emotion} ({confidence:.2f}): {detail}")
            except Exception as e:
                # DeepFace 检测不到人脸时会报错，静默处理
                if "Face" not in str(e):
                    print(f"[CameraV2] error: {e}")

            del frame
            time.sleep(self.capture_interval)

        cap.release()

    def _analyze(self, frame):
        """DeepFace 分析单帧，返回 (emotion, confidence, detail)"""
        results = self._deepface.analyze(
            img_path=frame,  # 直接传 numpy array
            actions=["emotion"],
            enforce_detection=False,  # 检测不到人脸不报错
            silent=True
        )

        if not results:
            return None

        r = results[0] if isinstance(results, list) else results
        emotions = r.get("emotion", {})

        if not emotions:
            return None

        # 找最高置信度的情绪
        top_emotion = max(emotions, key=emotions.get)
        top_score = emotions[top_emotion] / 100.0  # DeepFace 输出 0-100

        # 映射到我们的 5 类
        mapped = self.EMOTION_MAP.get(top_emotion, "neutral")

        # 生成描述
        detail = f"facial expression: {top_emotion} ({top_score:.0%})"

        # 只记录有意义的事件（置信度 > 40% 且不是 neutral）
        if top_score < 0.4 and mapped == "neutral":
            return None

        return mapped, top_score, detail


# ============================================================
# 模块 B: 文字情感分析（轻量 transformers，CPU，<10ms）
# ============================================================

class TextSentimentAnalyzer:
    """轻量中文文字情感分析，不占 GPU
    
    使用 transformers pipeline 的小模型
    替代让 Gemma-3 兼任文字情感分析
    """

    def __init__(self):
        self._pipeline = None

    def _load_model(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline
                # 使用轻量中文情感模型（~100MB）
                # 备选：uer/roberta-base-finetuned-jd-binary-chinese
                self._pipeline = pipeline(
                    "sentiment-analysis",
                    model=os.path.join(PROJECT_ROOT, "models", "distilbert-sentiment"),
                    device=-1  # 强制 CPU
                )
                print("[TextSentiment] model loaded (CPU)")
            except Exception as e:
                print(f"[TextSentiment] load failed: {e}")
                print("  pip3 install transformers --break-system-packages")
                return False
        return True

    def analyze(self, text: str) -> dict:
        """分析文字情感，返回 {emotion, confidence}"""
        if not text or not self._load_model():
            return {"emotion": "neutral", "confidence": 0.5}

        try:
            result = self._pipeline(text[:512])[0]  # 截断到 512 字符
            label = result["label"].lower()
            score = result["score"]

            # 映射: positive/negative/neutral
            if label in ["positive", "pos"]:
                emotion = "positive"
            elif label in ["negative", "neg"]:
                emotion = "negative"
            else:
                emotion = "neutral"

            return {"emotion": emotion, "confidence": score}

        except Exception as e:
            print(f"[TextSentiment] error: {e}")
            return {"emotion": "neutral", "confidence": 0.5}


# ============================================================
# 模块 C: 行为模式检测（规则引擎，零资源）
# ============================================================

class BehaviorDetector:
    def __init__(self):
        self.last_motion_time = time.time()
        self.prev_gray = None

    def detect_from_frame(self, frame):
        """从摄像头帧检测行为，返回事件描述或 None"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return None

        delta = cv2.absdiff(self.prev_gray, gray)
        motion = np.mean(delta)
        self.prev_gray = gray

        if motion > 5.0:
            self.last_motion_time = time.time()

        sed_min = (time.time() - self.last_motion_time) / 60
        hour = time.localtime().tm_hour

        # 只在关键节点产生事件
        if sed_min > 120:
            return f"sedentary for {sed_min:.0f} min (over 2 hours)"
        if 1 <= hour <= 5:
            return "late night (1-5 AM), still at computer"
        if hour >= 23:
            return "near midnight, still active"

        return None

    def check_time_based(self):
        """纯时间检测，不需要摄像头"""
        hour = time.localtime().tm_hour
        if 1 <= hour <= 5:
            return "late night, still online"
        if hour == 23:
            return "approaching midnight"
        return None


# ============================================================
# 模块 D: 回复情绪判断（替代 LLM 输出标签）
# ============================================================

class ResponseEmotionDetector:
    """判断猫咪回复文字的情绪，驱动表情切换
    
    解决"格式遗忘"问题：
    旧方案：让 LLM 输出 [emotion:xxx] 标签 → 上下文长了会忘
    新方案：LLM 只输出纯文字，由这个模块判断情绪 → 格式永不出错
    """

    def __init__(self, text_analyzer: TextSentimentAnalyzer = None):
        self.analyzer = text_analyzer or TextSentimentAnalyzer()

    def detect(self, response_text: str) -> str:
        """返回猫咪表情状态"""
        result = self.analyzer.analyze(response_text)
        emotion = result["emotion"]

        # 情绪 → 猫咪表情映射
        EMOTION_TO_CAT = {
            "positive": "happy",
            "neutral": "neutral_idle",
            "negative": "concerned",
        }

        # 关键词细化
        text_lower = response_text.lower()
        if any(w in text_lower for w in ["累", "休息", "睡", "tired", "sleep"]):
            return "sleepy"
        if any(w in text_lower for w in ["加油", "棒", "厉害", "encourage"]):
            return "encouraging"
        if any(w in text_lower for w in ["在这里", "陪你", "不走", "comfort"]):
            return "silent_comfort"
        if any(w in text_lower for w in ["好奇", "什么", "怎么", "curious"]):
            return "curious"

        return EMOTION_TO_CAT.get(emotion, "neutral_idle")


# ============================================================
# 整合：感知引擎主类 V2
# ============================================================

class PerceptionEngineV2:
    """更新后的感知引擎
    
    - 摄像头用 DeepFace（CPU）
    - 文字情感用轻量 transformers（CPU）
    - Gemma-3 完全解放，只做融合裁判和对话
    """

    def __init__(self, config=None):
        config = config or {}
        self.camera = CameraPerceptionV2(
            capture_interval=config.get("camera_interval", 10),
            camera_id=config.get("camera_id", 0)
        )
        self.text_sentiment = TextSentimentAnalyzer()
        self.behavior = BehaviorDetector()
        self.response_emotion = ResponseEmotionDetector(self.text_sentiment)

        self.channels = {
            "camera": config.get("enable_camera", False),
            "microphone": config.get("enable_microphone", False),
        }

    def start(self):
        if self.channels["camera"]:
            self.camera.start()
        # 启动时间检测循环
        self._start_time_checker()
        print("[PerceptionV2] started")

    def stop(self):
        self.camera.stop()

    def toggle_channel(self, channel, enabled):
        self.channels[channel] = enabled
        if channel == "camera":
            if enabled:
                self.camera.start()
            else:
                self.camera.stop()
        print(f"[PerceptionV2] {channel} {'ON' if enabled else 'OFF'}")

    def analyze_user_text(self, text: str):
        """分析用户发来的文字的情感（替代 Gemma-3 兼任）"""
        result = self.text_sentiment.analyze(text)
        if result["emotion"] != "neutral" or result["confidence"] > 0.8:
            store.add_simple(
                source="text_sentiment",
                content=f'user said: "{text[:50]}..." → {result["emotion"]}',
                emotion=result["emotion"],
                confidence=result["confidence"]
            )

    def get_cat_state_for_response(self, response_text: str) -> str:
        """根据猫咪回复文字决定表情状态"""
        return self.response_emotion.detect(response_text)

    def _start_time_checker(self):
        """后台线程：每 10 分钟检查一次时间相关事件"""
        def _check():
            while True:
                event = self.behavior.check_time_based()
                if event:
                    store.add_simple(
                        source="behavior",
                        content=event,
                        emotion="tired",
                        confidence=0.7
                    )
                time.sleep(600)  # 10 分钟

        t = threading.Thread(target=_check, daemon=True)
        t.start()
