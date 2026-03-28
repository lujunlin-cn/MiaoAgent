from .voice_emotion import VoiceEmotionDetector, VoiceEmotionResult, analyze_voice_emotion
from .env_audio import EnvAudioDetector, EnvAudioResult, analyze_env_audio

try:
	from .perception_v2 import PerceptionEngineV2
except Exception:
	# Keep voice emotion usable even when camera deps (e.g. cv2) are missing.
	PerceptionEngineV2 = None

