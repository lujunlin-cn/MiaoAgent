#!/bin/bash
# /opt/catagent/full_test.sh — MiaoAgent 全链路测试
# 每个测试独立执行，通过/失败一目了然
# 用法：bash full_test.sh

PASS=0
FAIL=0
SKIP=0

pass() { echo "  ✅ PASS: $1"; ((PASS++)); }
fail() { echo "  ❌ FAIL: $1"; ((FAIL++)); }
skip() { echo "  ⏭  SKIP: $1"; ((SKIP++)); }

echo "==========================================="
echo "  MiaoAgent 全链路测试"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="

# ============================================================
echo ""
echo "=== 测试 1: Ollama 服务 ==="
MODELS=$(curl -s http://localhost:11434/v1/models 2>/dev/null)
if echo "$MODELS" | grep -q "gemma3"; then
    pass "Ollama 运行中，gemma3:27b 可用"
else
    fail "Ollama 未运行或模型不可用"
    echo "  修复: sudo systemctl start ollama"
fi

# ============================================================
echo ""
echo "=== 测试 2: OpenShell 网关 ==="
if openshell gateway info 2>/dev/null | grep -q "Gateway:"; then
    pass "OpenShell 网关运行中"
else
    fail "OpenShell 网关未启动"
    echo "  修复: openshell gateway start"
fi

# ============================================================
echo ""
echo "=== 测试 3: 推理路由 ==="
if openshell inference get 2>/dev/null | grep -q "ollama"; then
    pass "推理路由已配置 (ollama → gemma3:27b)"
else
    fail "推理路由未配置"
    echo "  修复: openshell inference set --provider ollama --model gemma3:27b"
fi

# ============================================================
echo ""
echo "=== 测试 4: Gemma-3 中文对话 ==="
REPLY=$(curl -s http://localhost:11434/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"gemma3:27b","messages":[{"role":"user","content":"用一句中文说你好"}],"max_tokens":50}' \
    2>/dev/null)
if echo "$REPLY" | grep -q "content"; then
    pass "Gemma-3 中文对话正常"
else
    fail "Gemma-3 对话失败"
fi

# ============================================================
echo ""
echo "=== 测试 5: 摄像头 ==="
if [ -e /dev/video0 ]; then
    # 尝试拍照
    fswebcam -r 1280x720 --no-banner /tmp/fulltest_cam.jpg 2>/dev/null
    if [ -f /tmp/fulltest_cam.jpg ] && [ -s /tmp/fulltest_cam.jpg ]; then
        pass "摄像头拍照成功 (/tmp/fulltest_cam.jpg)"
    else
        fail "摄像头设备存在但拍照失败"
        echo "  修复: sudo chmod 666 /dev/video0"
    fi
else
    fail "未检测到摄像头 (/dev/video0 不存在)"
    echo "  修复: 检查 USB 连接"
fi

# ============================================================
echo ""
echo "=== 测试 6: Gemma-3 多模态图片理解 ==="
if [ -f /tmp/fulltest_cam.jpg ]; then
    VISION_REPLY=$(curl -s http://localhost:11434/api/chat \
        -d "{
            \"model\": \"gemma3:27b\",
            \"messages\": [{
                \"role\": \"user\",
                \"content\": \"Describe the person's emotion in this image. Reply with JSON: {\\\"emotion\\\":\\\"positive/neutral/negative/tired/anxious\\\",\\\"confidence\\\":0.0-1.0,\\\"detail\\\":\\\"description\\\"}\",
                \"images\": [\"$(base64 -w0 /tmp/fulltest_cam.jpg)\"]
            }],
            \"stream\": false,
            \"options\": {\"temperature\": 0.1}
        }" 2>/dev/null)
    if echo "$VISION_REPLY" | grep -q "emotion\|neutral\|tired\|detail"; then
        pass "Gemma-3 多模态图片理解正常"
    else
        fail "Gemma-3 图片理解失败"
    fi
else
    skip "无照片，跳过多模态测试"
fi

# ============================================================
echo ""
echo "=== 测试 7: TTS 语音合成 ==="
if command -v edge-tts &>/dev/null; then
    edge-tts --voice zh-CN-XiaoyiNeural \
        --text "你看起来有点累了喵" \
        --write-media /tmp/fulltest_tts.mp3 2>/dev/null
    if [ -f /tmp/fulltest_tts.mp3 ] && [ -s /tmp/fulltest_tts.mp3 ]; then
        SIZE=$(stat -f%z /tmp/fulltest_tts.mp3 2>/dev/null || stat -c%s /tmp/fulltest_tts.mp3 2>/dev/null)
        pass "TTS 生成成功 (${SIZE} bytes)"
    else
        fail "TTS 生成失败"
    fi
else
    skip "edge-tts 未安装"
    echo "  安装: pip3 install edge-tts --break-system-packages"
fi

# ============================================================
echo ""
echo "=== 测试 8: 音箱/音频输出 ==="
if command -v mpv &>/dev/null || command -v aplay &>/dev/null; then
    if [ -f /tmp/fulltest_tts.mp3 ]; then
        pass "音频播放器可用（手动验证音箱是否有声音）"
        echo "  手动测试: mpv /tmp/fulltest_tts.mp3"
    else
        skip "无 TTS 文件可播放"
    fi
else
    skip "mpv/aplay 未安装"
    echo "  安装: sudo apt install -y mpv"
fi

# ============================================================
echo ""
echo "=== 测试 9: 麦克风录音 ==="
if command -v arecord &>/dev/null; then
    echo "  录音 3 秒（请说话）..."
    timeout 4 arecord -d 3 -f S16_LE -r 16000 -c 1 /tmp/fulltest_mic.wav 2>/dev/null
    if [ -f /tmp/fulltest_mic.wav ] && [ -s /tmp/fulltest_mic.wav ]; then
        SIZE=$(stat -c%s /tmp/fulltest_mic.wav 2>/dev/null)
        pass "麦克风录音成功 (${SIZE} bytes)"
    else
        fail "麦克风录音失败"
        echo "  检查: arecord -l"
    fi
else
    skip "arecord 未安装"
    echo "  安装: sudo apt install -y alsa-utils"
fi

# ============================================================
echo ""
echo "=== 测试 10: Whisper 语音转文字 ==="
if python3 -c "import whisper" 2>/dev/null; then
    if [ -f /tmp/fulltest_mic.wav ]; then
        echo "  转录中（首次会下载模型，请等待）..."
        TRANSCRIPT=$(python3 -c "
import whisper
model = whisper.load_model('base')
result = model.transcribe('/tmp/fulltest_mic.wav', language='zh')
print(result['text'])
" 2>/dev/null)
        if [ -n "$TRANSCRIPT" ]; then
            pass "Whisper 转录成功: $TRANSCRIPT"
        else
            fail "Whisper 转录无输出"
        fi
    else
        skip "无录音文件"
    fi
else
    skip "whisper 未安装"
    echo "  安装: pip3 install openai-whisper --break-system-packages"
fi

# ============================================================
echo ""
echo "=== 测试 11: NemoClaw 沙箱推理 ==="
if command -v nemoclaw &>/dev/null; then
    SANDBOX_REPLY=$(openshell sandbox create -- \
        curl -s https://inference.local/v1/chat/completions \
        --json '{"messages":[{"role":"user","content":"say ok"}],"max_tokens":10}' \
        2>/dev/null)
    if echo "$SANDBOX_REPLY" | grep -q "content"; then
        pass "NemoClaw 沙箱内推理正常"
    else
        fail "沙箱推理失败"
    fi
else
    skip "nemoclaw 未安装"
fi

# ============================================================
echo ""
echo "=== 测试 12: Python 模块导入 ==="
cd /opt/catagent
IMPORT_OK=$(python3 -c "
from skills.shared.event_store import store
from skills.proactive_engine.engine_v2 import ProactiveEngineV2
from skills.companion_persona.persona_v2 import CompanionPersonaV2
from skills.emotion_perception.perception import PerceptionEngine
print('ALL_OK')
" 2>/dev/null)
if [ "$IMPORT_OK" = "ALL_OK" ]; then
    pass "所有 Python 模块导入成功"
else
    fail "Python 模块导入失败"
    echo "  调试: python3 -c 'from skills.shared.event_store import store'"
fi

# ============================================================
echo ""
echo "==========================================="
echo "  测试完成: ✅ $PASS 通过  ❌ $FAIL 失败  ⏭ $SKIP 跳过"
echo "==========================================="

if [ $FAIL -gt 0 ]; then
    echo "  请修复失败项后重新测试"
    exit 1
else
    echo "  全部核心测试通过！"
fi
