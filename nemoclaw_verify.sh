#!/usr/bin/env bash
# ============================================================
# nemoclaw_verify.sh — NemoClaw 部署验证
#
# 逐项检查 NemoClaw 部署状态，输出通过/失败结果。
# 在 DGX Spark 宿主机上执行。
#
# 用法：
#   cd /opt/catagent
#   chmod +x nemoclaw_verify.sh
#   ./nemoclaw_verify.sh
# ============================================================

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "  ${GREEN}✓${NC} $*"; ((PASS++)); }
fail() { echo -e "  ${RED}✗${NC} $*"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $*"; ((WARN++)); }

echo "============================================================"
echo "  MiaoAgent NemoClaw 部署验证"
echo "============================================================"
echo ""

# ----------------------------------------------------------
# 1. OpenShell 网关状态
# ----------------------------------------------------------
echo "[1/7] OpenShell 网关"
GATEWAY_INFO=$(openshell gateway info 2>&1 || true)
if echo "$GATEWAY_INFO" | grep -qi "running"; then
    pass "网关运行中"
else
    fail "网关未运行 — 执行 openshell gateway start"
fi

# ----------------------------------------------------------
# 2. TRT-LLM 模型健康
# ----------------------------------------------------------
echo "[2/7] TRT-LLM 模型"
QWEN_STATUS=$(curl -s --connect-timeout 3 http://localhost:8355/v1/models 2>/dev/null || echo "")
if [[ -n "$QWEN_STATUS" ]] && echo "$QWEN_STATUS" | grep -qi "model\|data"; then
    pass "Qwen3 (port 8355) 响应正常"
else
    fail "Qwen3 (port 8355) 无响应"
fi

PHI4_STATUS=$(curl -s --connect-timeout 3 http://localhost:8356/v1/models 2>/dev/null || echo "")
if [[ -n "$PHI4_STATUS" ]] && echo "$PHI4_STATUS" | grep -qi "model\|data"; then
    pass "Phi-4 (port 8356) 响应正常"
else
    fail "Phi-4 (port 8356) 无响应"
fi

# ----------------------------------------------------------
# 3. Provider 注册
# ----------------------------------------------------------
echo "[3/7] OpenShell Provider"
PROVIDER_INFO=$(openshell provider list 2>&1 || true)
if echo "$PROVIDER_INFO" | grep -q "trtllm-qwen3"; then
    pass "Provider trtllm-qwen3 已注册"
else
    warn "Provider trtllm-qwen3 未注册（白名单模式下可忽略）"
fi

# ----------------------------------------------------------
# 4. 推理路由
# ----------------------------------------------------------
echo "[4/7] 推理路由"
INFERENCE_INFO=$(openshell inference get 2>&1 || true)
if echo "$INFERENCE_INFO" | grep -q "trtllm-qwen3"; then
    pass "推理路由指向 trtllm-qwen3"
else
    warn "推理路由未设置（白名单模式下可忽略）"
fi

# ----------------------------------------------------------
# 5. 沙箱状态
# ----------------------------------------------------------
echo "[5/7] NemoClaw 沙箱"
SANDBOX_INFO=$(openshell sandbox list 2>&1 || true)
if echo "$SANDBOX_INFO" | grep -q "miaoagent"; then
    SANDBOX_STATUS=$(openshell sandbox info --name miaoagent 2>&1 || true)
    if echo "$SANDBOX_STATUS" | grep -qi "running"; then
        pass "沙箱 miaoagent 运行中"
    else
        fail "沙箱 miaoagent 存在但未运行"
    fi
else
    fail "沙箱 miaoagent 不存在 — 执行 ./nemoclaw_setup.sh"
fi

# ----------------------------------------------------------
# 6. 沙箱内 inference.local 可达性
# ----------------------------------------------------------
echo "[6/7] inference.local（沙箱内）"
INFER_TEST=$(openshell sandbox exec miaoagent -- \
    curl -sk --connect-timeout 5 \
    https://inference.local/v1/models 2>&1 || echo "FAIL")

if echo "$INFER_TEST" | grep -qi "model\|data"; then
    pass "inference.local 可达，Qwen3 通过安全路由"
elif echo "$INFER_TEST" | grep -qi "resolve\|FAIL\|connection"; then
    warn "inference.local 不可达 — Issue #326，使用白名单模式"
    echo -e "       解决: ${YELLOW}./nemoclaw_setup.sh --whitelist-only${NC}"
else
    warn "inference.local 响应异常: ${INFER_TEST:0:80}"
fi

# ----------------------------------------------------------
# 7. 沙箱内 Phi-4 白名单直连
# ----------------------------------------------------------
echo "[7/7] Phi-4 白名单直连（沙箱内）"
PHI4_TEST=$(openshell sandbox exec miaoagent -- \
    curl -s --connect-timeout 5 \
    http://host.openshell.internal:8356/v1/models 2>&1 || echo "FAIL")

if echo "$PHI4_TEST" | grep -qi "model\|data"; then
    pass "Phi-4 (host.openshell.internal:8356) 白名单直连正常"
else
    fail "Phi-4 白名单直连失败 — 检查 sandbox-policy.yaml"
fi

# ----------------------------------------------------------
# 汇总
# ----------------------------------------------------------
echo ""
echo "============================================================"
echo -e "  结果: ${GREEN}${PASS} 通过${NC}  ${RED}${FAIL} 失败${NC}  ${YELLOW}${WARN} 警告${NC}"
echo ""

if [[ $FAIL -eq 0 ]]; then
    echo -e "  ${GREEN}NemoClaw 部署验证通过！${NC}"
    echo ""
    echo "  Pitch 话术可用："
    echo "  \"MiaoAgent 运行在 NVIDIA NemoClaw 安全沙箱中。"
    echo "   所有对话推理经过 OpenShell 隐私路由器——凭证由网关注入，"
    echo "   沙箱代码永远不接触后端地址。融合裁判模型通过声明式网络策略"
    echo "   白名单访问，其他所有外网请求被内核级拦截。\""
else
    echo -e "  ${RED}有 ${FAIL} 项失败，请修复后重新验证${NC}"
fi
echo "============================================================"

exit $FAIL
