#!/usr/bin/env bash
# ============================================================
# nemoclaw_setup.sh — NemoClaw 一键部署
#
# 在 DGX Spark 宿主机上执行。完成后 MiaoAgent 将在沙箱内运行，
# Qwen3 对话经过 OpenShell 隐私路由，Phi-4 经过网络策略白名单。
#
# 用法：
#   cd /opt/catagent
#   chmod +x nemoclaw_setup.sh
#   sudo ./nemoclaw_setup.sh
#
# 如果 inference.local 不可达 (Issue #326)：
#   sudo ./nemoclaw_setup.sh --whitelist-only
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[Setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[Warn]${NC} $*"; }
err()  { echo -e "${RED}[Error]${NC} $*"; }

WHITELIST_ONLY=false
if [[ "${1:-}" == "--whitelist-only" ]]; then
    WHITELIST_ONLY=true
    warn "白名单模式：跳过 inference.local 注册，两个模型都走白名单直连"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POLICY_FILE="${SCRIPT_DIR}/sandbox-policy.yaml"

# ============================================================
# Step 0: 前置检查
# ============================================================
log "Step 0: 前置检查..."

if ! command -v openshell &>/dev/null; then
    err "openshell 命令不存在，请确认 NemoClaw/OpenShell 已安装"
    exit 1
fi

if ! command -v docker &>/dev/null; then
    err "docker 命令不存在"
    exit 1
fi

if [[ ! -f "$POLICY_FILE" ]]; then
    err "sandbox-policy.yaml 不存在于 ${SCRIPT_DIR}"
    exit 1
fi

# 检查 TRT-LLM 是否在运行
if ! curl -s --connect-timeout 3 http://localhost:8355/v1/models >/dev/null 2>&1; then
    warn "Qwen3 TRT-LLM (port 8355) 未响应，请确认已启动"
fi
if ! curl -s --connect-timeout 3 http://localhost:8356/v1/models >/dev/null 2>&1; then
    warn "Phi-4 TRT-LLM (port 8356) 未响应，请确认已启动"
fi

log "  ✓ 前置检查完成"

# ============================================================
# Step 1: 启动 OpenShell 网关
# ============================================================
log "Step 1: 启动 OpenShell 网关..."

GATEWAY_STATUS=$(openshell gateway info 2>&1 || true)
if echo "$GATEWAY_STATUS" | grep -qi "running"; then
    log "  ✓ 网关已在运行"
else
    warn "  网关未运行，尝试启动..."

    # 清理可能残留的旧容器
    docker stop openshell-cluster-nemoclaw 2>/dev/null || true
    docker rm openshell-cluster-nemoclaw 2>/dev/null || true

    openshell gateway start
    sleep 3

    # 验证
    GATEWAY_STATUS=$(openshell gateway info 2>&1 || true)
    if echo "$GATEWAY_STATUS" | grep -qi "running"; then
        log "  ✓ 网关启动成功"
    else
        err "  网关启动失败"
        echo "$GATEWAY_STATUS"
        exit 1
    fi
fi

# ============================================================
# Step 2: 注册 TRT-LLM 为 OpenShell Provider
# ============================================================
if [[ "$WHITELIST_ONLY" == false ]]; then
    log "Step 2: 注册 Qwen3 TRT-LLM Provider..."

    # 删除已存在的同名 provider（幂等）
    openshell provider delete --name trtllm-qwen3 2>/dev/null || true

    openshell provider create \
        --name trtllm-qwen3 \
        --type openai \
        --credential OPENAI_API_KEY=empty \
        --config OPENAI_BASE_URL=http://host.openshell.internal:8355/v1

    log "  ✓ Provider trtllm-qwen3 已注册"

    # --------------------------------------------------------
    # Step 3: 设置推理路由
    # --------------------------------------------------------
    log "Step 3: 设置推理路由 → trtllm-qwen3 / Qwen3-30B-A3B-FP4..."

    openshell inference set \
        --provider trtllm-qwen3 \
        --model Qwen3-30B-A3B-FP4

    # 验证
    INFERENCE_INFO=$(openshell inference get 2>&1)
    log "  当前推理配置:"
    echo "$INFERENCE_INFO" | sed 's/^/    /'

    if echo "$INFERENCE_INFO" | grep -q "trtllm-qwen3"; then
        log "  ✓ 推理路由设置成功"
    else
        warn "  推理路由可能未正确设置，请检查上方输出"
    fi
else
    log "Step 2-3: 跳过（白名单模式）"
fi

# ============================================================
# Step 4: 启用白名单（Issue #326 workaround）
# ============================================================
if [[ "$WHITELIST_ONLY" == true ]]; then
    log "Step 4: 启用 Qwen3 白名单直连..."

    # 取消 sandbox-policy.yaml 中 Qwen3 白名单的注释
    if grep -q "# - name: allow-qwen3-whitelist" "$POLICY_FILE"; then
        sed -i 's/^  # - name: allow-qwen3-whitelist/  - name: allow-qwen3-whitelist/' "$POLICY_FILE"
        sed -i 's/^  #   egress:/    egress:/' "$POLICY_FILE"
        sed -i 's/^  #     - to:/      - to:/' "$POLICY_FILE"
        sed -i 's/^  #         - host: "host.openshell.internal"/          - host: "host.openshell.internal"/' "$POLICY_FILE"
        sed -i 's/^  #           port: 8355/            port: 8355/' "$POLICY_FILE"
        sed -i 's/^  #       protocols:/        protocols:/' "$POLICY_FILE"
        sed -i 's/^  #         - TCP/          - TCP/' "$POLICY_FILE"
        log "  ✓ sandbox-policy.yaml 已更新（Qwen3 白名单已启用）"
    else
        log "  sandbox-policy.yaml 中 Qwen3 白名单已是启用状态"
    fi
fi

# ============================================================
# Step 5: 清理旧沙箱（如果存在）
# ============================================================
log "Step 5: 清理旧沙箱..."
openshell sandbox delete --name miaoagent 2>/dev/null && log "  已删除旧沙箱 miaoagent" || log "  无旧沙箱需要清理"

# ============================================================
# Step 6: 创建沙箱并启动 MiaoAgent
# ============================================================
log "Step 6: 创建 NemoClaw 沙箱..."

# 设置引擎环境变量
if [[ "$WHITELIST_ONLY" == true ]]; then
    SANDBOX_ENGINE="nemoclaw_whitelist"
else
    SANDBOX_ENGINE="nemoclaw"
fi

openshell sandbox create \
    --name miaoagent \
    --policy "$POLICY_FILE" \
    --gpu \
    --mount /opt/catagent:/sandbox/catagent \
    --env MIAOAGENT_ENGINE="$SANDBOX_ENGINE" \
    -- python3 /sandbox/catagent/frontend/web_ui_complete.py

log "  ✓ 沙箱 miaoagent 已创建"

# ============================================================
# Step 7: 验证
# ============================================================
log "Step 7: 等待 5 秒后验证..."
sleep 5

echo ""
echo "============================================================"
echo "  NemoClaw 部署完成！"
echo ""
echo "  引擎模式:  $SANDBOX_ENGINE"
if [[ "$WHITELIST_ONLY" == false ]]; then
    echo "  Qwen3:     inference.local (安全路由)"
else
    echo "  Qwen3:     host.openshell.internal:8355 (白名单直连)"
fi
echo "  Phi-4:     host.openshell.internal:8356 (白名单直连)"
echo "  Web UI:    http://127.0.0.1:5000"
echo ""
echo "  验证命令:"
echo "    ./nemoclaw_verify.sh"
echo ""
echo "  查看沙箱日志:"
echo "    openshell sandbox logs miaoagent"
echo ""
echo "  进入沙箱 shell:"
echo "    openshell sandbox exec miaoagent -- /bin/bash"
echo "============================================================"
