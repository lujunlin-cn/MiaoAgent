#!/bin/bash
# /opt/catagent/start.sh — MiaoAgent 每日启动脚本
# 用法：/opt/catagent/start.sh

echo "==========================================="
echo "  MiaoAgent 每日启动检查"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="
echo ""

FAIL=0

# 1. Ollama
echo -n "[1/3] Ollama 模型服务... "
if curl -s http://localhost:11434/v1/models 2>/dev/null | grep -q gemma3; then
    echo "✓ 已运行 (gemma3:27b)"
else
    echo "启动中..."
    sudo systemctl start ollama
    sleep 15
    if curl -s http://localhost:11434/v1/models 2>/dev/null | grep -q gemma3; then
        echo "  ✓ 启动成功"
    else
        echo "  ✗ 启动失败！执行：sudo journalctl -u ollama --no-pager | tail -20"
        FAIL=1
    fi
fi

# 2. OpenShell Gateway
echo -n "[2/3] OpenShell 网关... "
if openshell gateway info 2>/dev/null | grep -q "Gateway:"; then
    GW_NAME=$(openshell gateway info 2>/dev/null | grep "Gateway:" | awk '{print $2}')
    echo "✓ 已运行 ($GW_NAME)"
else
    echo "启动中..."
    openshell gateway start 2>/dev/null
    sleep 5
    if openshell gateway info 2>/dev/null | grep -q "Gateway:"; then
        echo "  ✓ 启动成功"
    else
        echo "  ✗ 启动失败！可能端口被占，执行："
        echo "    docker stop openshell-cluster-nemoclaw"
        echo "    openshell gateway start"
        FAIL=1
    fi
fi

# 3. Inference Route
echo -n "[3/3] 推理路由... "
if openshell inference get 2>/dev/null | grep -q "ollama"; then
    echo "✓ 已配置 (ollama → gemma3:27b)"
else
    echo "配置中..."
    openshell provider create --name ollama --type openai \
        --credential OPENAI_API_KEY=empty \
        --config OPENAI_BASE_URL=http://host.openshell.internal:11434/v1 2>/dev/null
    openshell inference set --provider ollama --model gemma3:27b 2>/dev/null
    if openshell inference get 2>/dev/null | grep -q "ollama"; then
        echo "  ✓ 配置成功"
    else
        echo "  ✗ 配置失败"
        FAIL=1
    fi
fi

echo ""
# 4. 摄像头检测
echo -n "[附加] 摄像头... "
if [ -e /dev/video0 ]; then
    echo "✓ /dev/video0"
else
    echo "✗ 未检测到（USB 没插？）"
fi

# 5. 音频设备检测
echo -n "[附加] 麦克风... "
if arecord -l 2>/dev/null | grep -q "card"; then
    echo "✓ 检测到音频设备"
else
    echo "- 未检测到（可能用摄像头内置麦克风）"
fi

echo ""
if [ $FAIL -eq 0 ]; then
    echo "==========================================="
    echo "  ✓ 全部就绪！启动 MiaoAgent："
    echo "    cd /opt/catagent && python3 main_v2.py"
    echo "==========================================="
else
    echo "==========================================="
    echo "  ✗ 有服务启动失败，请检查上面的错误信息"
    echo "==========================================="
    exit 1
fi
