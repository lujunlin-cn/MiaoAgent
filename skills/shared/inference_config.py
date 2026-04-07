"""
inference_config.py — 推理引擎配置

集中管理所有模型 URL 和名称，切换引擎只改 ENGINE 变量。

引擎选项：
  trtllm              宿主机直连 TRT-LLM（沙箱外开发/调试用）
  nemoclaw             NemoClaw 沙箱模式（生产部署）
                       Qwen3 走 inference.local 安全路由
                       Phi-4 走白名单直连 host.openshell.internal
  nemoclaw_whitelist   两个模型都走白名单直连（Issue #326 workaround）
  ollama               Ollama 后端（调试用）

切换方式：
  方式一：直接改下面的 ENGINE 变量
  方式二：环境变量 export MIAOAGENT_ENGINE=nemoclaw
"""
import os

# ============================================================
# ▼▼▼ 切换引擎只改这一行 ▼▼▼
# ============================================================
ENGINE = os.environ.get("MIAOAGENT_ENGINE", "trtllm")
# ============================================================

# ============================================================
# 引擎配置
# ============================================================

if ENGINE == "nemoclaw":
    # ---- 生产模式：沙箱内运行 ----
    # Qwen3 走 OpenShell inference.local 安全路由
    # gateway 自动注入后端凭证，沙箱代码不接触真实地址
    CHAT_URL = "https://inference.local"
    CHAT_MODEL = "qwen3-30B"
    CHAT_API_KEY = "unused"           # OpenShell 会替换为真实凭证
    CHAT_VERIFY_SSL = False           # inference.local 使用内部证书

    # Phi-4 走网络白名单直连（sandbox-policy.yaml 放行 :8356）
    # 注意：沙箱内 localhost 指向沙箱自己，必须用 host.openshell.internal
    JUDGE_URL = "http://host.openshell.internal:8356"
    JUDGE_MODEL = "phi4mm"
    JUDGE_API_KEY = "empty"
    JUDGE_VERIFY_SSL = True

    # 绕过沙箱内部代理（10.200.0.1:3128），否则请求会被 403
    os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "") + ",localhost,inference.local,host.openshell.internal"
    os.environ["no_proxy"] = os.environ.get("no_proxy", "") + ",localhost,inference.local,host.openshell.internal"

elif ENGINE == "nemoclaw_whitelist":
    # ---- Issue #326 Workaround ----
    # inference.local DNS 不解析时，两个模型都走白名单直连
    # 安全性略降（沙箱代码知道后端地址）但仍有网络策略控制
    CHAT_URL = "http://host.openshell.internal:8355"
    CHAT_MODEL = "qwen3-30B"
    CHAT_API_KEY = "empty"
    CHAT_VERIFY_SSL = True

    JUDGE_URL = "http://host.openshell.internal:8356"
    JUDGE_MODEL = "phi4mm"
    JUDGE_API_KEY = "empty"
    JUDGE_VERIFY_SSL = True
    os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "") + ",host.openshell.internal"
    os.environ["no_proxy"] = os.environ.get("no_proxy", "") + ",host.openshell.internal"

elif ENGINE == "ollama":
    # ---- Ollama 调试 ----
    CHAT_URL = "http://localhost:11434"
    CHAT_MODEL = "gemma3:27b"
    CHAT_API_KEY = ""
    CHAT_VERIFY_SSL = True

    JUDGE_URL = "http://localhost:11434"
    JUDGE_MODEL = "gemma3:27b"
    JUDGE_API_KEY = ""
    JUDGE_VERIFY_SSL = True

else:
    # ---- 默认：TRT-LLM 宿主机直连（沙箱外开发用）----
    ENGINE = "trtllm"
    CHAT_URL = "http://localhost:8355"
    CHAT_MODEL = "qwen3-30B"
    CHAT_API_KEY = ""
    CHAT_VERIFY_SSL = True

    JUDGE_URL = "http://localhost:8356"
    JUDGE_MODEL = "phi4mm"
    JUDGE_API_KEY = ""
    JUDGE_VERIFY_SSL = True


# ============================================================
# 提示词目录（团队用的是 prompt/ 不是 prompts/）
# ============================================================
PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "prompt")

def load_prompt(name: str) -> str:
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


# ============================================================
# 统一 API 调用
# ============================================================
import requests
import json

def _build_headers(api_key: str = "") -> dict:
    """构建请求头，有 API key 时加 Authorization"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def chat_completion(messages: list, url: str = None, model: str = None,
                    temperature: float = 0.7, max_tokens: int = 150,
                    timeout: int = 60) -> str:
    """统一对话补全接口，自动适配当前引擎"""
    url = url or CHAT_URL
    model = model or CHAT_MODEL
    endpoint = f"{url}/v1/chat/completions"

    # 判断是 chat 还是 judge 调用，选择对应的 SSL 和 API key 配置
    if url == JUDGE_URL:
        api_key = JUDGE_API_KEY
        verify_ssl = JUDGE_VERIFY_SSL
    else:
        api_key = CHAT_API_KEY
        verify_ssl = CHAT_VERIFY_SSL

    try:
        resp = requests.post(
            endpoint,
            headers=_build_headers(api_key),
            json={"model": model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=timeout,
            verify=verify_ssl,
        )
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        # 打印非预期响应帮助调试
        if "error" in data:
            print(f"[Inference] API error: {data['error']}")
        return ""
    except requests.exceptions.SSLError as e:
        print(f"[Inference] SSL error on {endpoint}: {e}")
        print(f"[Inference] 如果是 inference.local 证书问题，尝试 ENGINE=nemoclaw_whitelist")
        return ""
    except requests.exceptions.ConnectionError:
        print(f"[Inference] connection failed: {endpoint}")
        if "inference.local" in endpoint:
            print(f"[Inference] inference.local 不可达，可能是 Issue #326")
            print(f"[Inference] 尝试: export MIAOAGENT_ENGINE=nemoclaw_whitelist")
        return ""
    except Exception as e:
        print(f"[Inference] error: {e}")
        return ""


def judge_completion(messages: list, temperature: float = 0.3,
                     max_tokens: int = 500, timeout: int = 60) -> str:
    """融合裁判专用接口"""
    return chat_completion(messages, url=JUDGE_URL, model=JUDGE_MODEL,
                          temperature=temperature, max_tokens=max_tokens,
                          timeout=timeout)


# ============================================================
# 启动时打印当前配置
# ============================================================
_engine_labels = {
    "trtllm": "TRT-LLM 直连（沙箱外开发）",
    "nemoclaw": "NemoClaw 沙箱（inference.local + 白名单）",
    "nemoclaw_whitelist": "NemoClaw 白名单模式 (Issue #326 workaround)",
    "ollama": "Ollama",
}
print(f"[InferenceConfig] ENGINE = {ENGINE} ({_engine_labels.get(ENGINE, '?')})")
print(f"[InferenceConfig]   Chat:  {CHAT_MODEL} @ {CHAT_URL}")
print(f"[InferenceConfig]   Judge: {JUDGE_MODEL} @ {JUDGE_URL}")
