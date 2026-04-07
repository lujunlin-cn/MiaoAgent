#!/bin/bash
# ============================================================
# MiaoAgent NemoClaw 开机恢复脚本
# ============================================================
# 用途：DGX Spark 关机/重启后，NemoClaw 沙箱无法自动恢复（已知 Bug）
#       每次开机后运行此脚本即可恢复沙箱环境
#
# 已知问题参考：NemoClaw Issue #159, #716, #768, #910
#
# 路由设计：
#   Qwen3 → OpenShell 推理路由（inference.local，gateway 代理）
#   Phi-4 → 网络白名单直连（sandbox-policy.yaml 放行 :8356）
#
# 使用方式：sudo bash nemoclaw_recover.sh
# ============================================================

set -e

echo "=== MiaoAgent NemoClaw 开机恢复 ==="
echo ""

# 1. 停掉宿主机 k3s（避免 gateway 启动阶段 cgroup 冲突，Issue #431）
echo "[1/6] 停止宿主机 k3s（避免 gateway 启动阶段 cgroup 冲突）..."
sudo systemctl stop k3s 2>/dev/null || echo "  k3s 未运行，跳过"
sleep 2

# 2. 启动 Docker（如果没启动）
echo "[2/6] 确保 Docker 运行..."
sudo systemctl start docker
sleep 5

# 3. 启动 gateway 容器
echo "[3/6] 启动 OpenShell gateway..."
GATEWAY_ID=$(sudo docker ps -aq --filter name=openshell)
if [ -n "$GATEWAY_ID" ]; then
    sudo docker start "$GATEWAY_ID"
    echo "  等待 gateway 内部服务就绪（120s）..."
    sleep 120
    sudo openshell status
else
    echo "  ⚠️ 未找到 openshell 容器，可能需要重新安装 OpenShell"
    exit 1
fi

# 4. 重新注册 Qwen3 推理路由（gateway 重启后配置丢失）
#    Phi-4 走网络白名单直连，不需要注册推理路由
echo "[4/6] 注册 Qwen3 推理路由..."

sudo openshell provider create \
    --name trtllm-qwen3 \
    --type openai \
    --credential OPENAI_API_KEY=empty \
    --config OPENAI_BASE_URL=http://host.openshell.internal:8355/v1 \
    2>/dev/null && echo "  ✅ trtllm-qwen3 provider 已创建" \
    || echo "  ℹ️ trtllm-qwen3 provider 已存在"

sudo openshell inference set \
    --provider trtllm-qwen3 \
    --model qwen3-30B \
    --no-verify \
    2>/dev/null && echo "  ✅ qwen3 推理路由已注册" \
    || echo "  ℹ️ qwen3 推理路由已存在"

echo "  ℹ️ Phi-4 走网络白名单直连 :8356，无需注册推理路由"

# 5. 检查 sandbox
echo "[5/6] 检查 sandbox..."
sudo openshell sandbox list

# 6. 恢复宿主机 k3s（gateway 已启动稳定，不再有 cgroup 冲突）
echo "[6/6] 恢复宿主机 k3s..."
sudo systemctl start k3s 2>/dev/null && echo "  ✅ k3s 已恢复" \
    || echo "  ℹ️ k3s 恢复失败（不影响 MiaoAgent 运行）"

echo ""
echo "=== 恢复完成 ==="
echo ""
echo "下一步："
echo "  1. 确保 TRT-LLM 已启动："
echo "     trtllm-serve serve /path/to/qwen3 --port 8355"
echo "     trtllm-serve serve /path/to/phi4  --port 8356"
echo ""
echo "  2. 连接沙箱并启动应用："
echo "     sudo nemoclaw <sandbox名字> connect"
echo "     export MIAOAGENT_ENGINE=nemoclaw"
echo "     python3 frontend/web_ui.py"
echo ""
echo "  如果 sandbox Phase 不是 Ready，需要重建："
echo "     sudo nemoclaw onboard"
echo "     sudo nemoclaw policy apply sandbox-policy.yaml"
