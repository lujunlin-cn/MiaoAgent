#!/bin/bash
echo "==========================================="
echo "  MiaoAgent 每日启动检查 (TRT-LLM)"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="

echo -n "[1/3] Qwen3 (port 8355)... "
if curl -s http://localhost:8355/v1/models 2>/dev/null | grep -q "model"; then
    echo "✓ running"
else
    echo "starting..."
    docker start trtllm-qwen 2>/dev/null || echo "  Run: docker run --name trtllm-qwen ..."
    sleep 5
fi

echo -n "[2/3] Phi-4 (port 8356)... "
if curl -s http://localhost:8356/v1/models 2>/dev/null | grep -q "model"; then
    echo "✓ running"
else
    echo "starting..."
    docker start trtllm-phi4 2>/dev/null || echo "  Run: docker run --name trtllm-phi4 ..."
    sleep 5
fi

echo -n "[3/3] ZeroTier/Tailscale... "
if sudo zerotier-cli listnetworks 2>/dev/null | grep -q "OK"; then
    ZT_IP=$(ip addr show | grep "inet.*zt" | awk '{print $2}' | cut -d/ -f1)
    echo "✓ ($ZT_IP)"
elif sudo tailscale status 2>/dev/null; then
    echo "✓ Tailscale"
else
    echo "- offline"
fi

echo -n "[+] Camera... "
[ -e /dev/video0 ] && echo "✓" || echo "✗"

echo ""
Q=$(curl -s http://localhost:8355/v1/models 2>/dev/null | grep -c "model")
P=$(curl -s http://localhost:8356/v1/models 2>/dev/null | grep -c "model")
if [ "$Q" -gt 0 ] && [ "$P" -gt 0 ]; then
    echo "✓ Both models ready!"
elif [ "$Q" -gt 0 ]; then
    echo "△ Qwen3 ready, Phi-4 pending"
else
    echo "✗ Check: docker ps && docker logs trtllm-qwen"
fi
echo "Run: cd /opt/catagent && python3 main_v3.py"
echo "Web: python3 frontend/web_ui.py (port 5000)"
echo "==========================================="
