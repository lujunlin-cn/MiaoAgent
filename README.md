<p align="center">
  <img src="/frontend/static/cat_images/neutral_idle.png" width="120" alt="MiaoAgent"/>
</p>

<h1 align="center">MiaoAgent 🐱</h1>

<p align="center">
  <b>全栈本地化多模态情感陪伴智能体</b><br/>
  Fully Local Multimodal Emotional Companion AI on NVIDIA DGX Spark
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> •
  <a href="#核心性能">核心性能</a> •
  <a href="#系统架构">系统架构</a> •
  <a href="#功能特性">功能特性</a> •
  <a href="https://github.com/lujunlin-cn/MiaoAgent/releases">📄 项目报告书</a>
</p>

---

## 项目简介

MiaoAgent 是一款运行在 **NVIDIA DGX Spark** 上的全栈本地化多模态情感陪伴智能体。它以一只像素风金渐层英短猫咪为拟人化形象，通过多路感知通道实时捕捉用户情绪状态，在 **完全不依赖任何云端服务** 的前提下，主动发起富有共情的陪伴对话。

**核心理念：数据不出端，关怀不缺席。**

### 解决什么问题？

| 痛点 | MiaoAgent 方案 |
|------|---------------|
| 情感数据上云的隐私焦虑 | 全栈端侧部署，零云依赖，NemoClaw 沙箱网络策略已配置 |
| 一问一答的被动交互 | 全天候静默感知 + LLM 主动决策破冰 |
| 固定权重打分的不可解释 | LLM-as-Judge 自然语言推理，输出结构化决策理由 |

---

## 核心性能

> 以下数据由 `run_all_tests.py` 自动化脚本在 DGX Spark 上实测生成（宿主机直连模式，iptables 模拟外联阻断）

| 指标 | 实测值 | 说明 |
|------|--------|------|
| **Qwen3-30B TTFT** | **28 ms** | TRT-LLM + NVFP4，5轮均值 |
| **Qwen3-30B 吞吐** | **68.5 chars/s** | 中文字符/秒 |
| **TRT-LLM vs Ollama** | **10.2x 加速** | 同硬件对比 Gemma3-27B on Ollama |
| 双模型并发峰值内存 | 80.1 GB / 128 GB | Qwen3 + Phi-4 同时推理 |
| 语义护栏准确率 | 98.3% | 102 条样本（57 正常 + 45 恶意） |
| 语义护栏延迟 | 10.3 ms | BGE 嵌入 + 逻辑回归 |
| ChromaDB 检索延迟 | 16.3 ms | 排除首次模型加载 |
| 主动对话端到端 | ✅ 触发成功 | 事件注入 → 裁判决策 → SSE 推送 |
| 沙箱网络策略 | ✅ 已应用 | openshell policy set 验证通过 |

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                         DGX Spark (128GB)                            │
│                                                                      │
│  ┌─── GPU 推理层（宿主机 TRT-LLM 服务）────────────────────────────┐ │
│  │ Qwen3-30B-A3B :8355  对话核心    (TRT-LLM, NVFP4)              │ │
│  │ Phi-4-multimodal :8356  融合裁判  (TRT-LLM, NVFP4)              │ │
│  └──────────┬───────────────────┬───────────────────────────────────┘ │
│             │ inference.local   │ host.openshell.internal:8356       │
│             │ (推理路由)         │ (网络白名单)                       │
│  ┌══════════╪═══════════════════╪═══ NemoClaw 沙箱 ════════════════┐ │
│  ║          ▼                   ▼                                  ║ │
│  ║  ┌─ CPU 感知层（常驻低功耗）─┐   ┌─ 决策层 ──────────────────┐  ║ │
│  ║  │ DeepFace    面部情绪      │   │ Phi-4 融合裁判（远程调用）│  ║ │
│  ║  │ DistilBERT  文字情感      │   │ LLM-as-Judge 自然语言决策 │  ║ │
│  ║  │ emotion2vec 语气语调      │   └────────────┬──────────────┘  ║ │
│  ║  │ PANNs       环境底噪      │                │                 ║ │
│  ║  └──────────┬────────────────┘                │                 ║ │
│  ║             │ 结构化事件                       │                 ║ │
│  ║             ▼                                 ▼                 ║ │
│  ║  ┌─ EventStore 事件总线 ──┐  ┌─ 记忆层 ────────────────────┐   ║ │
│  ║  │ 24h 自动过期 | 多源汇聚│  │ FAISS     长期语义记忆      │   ║ │
│  ║  └────────────────────────┘  │ ChromaDB  心理学 RAG 策略库 │   ║ │
│  ║                               └────────────────────────────┘   ║ │
│  ║  ┌─ 安全层 ────────────┐  ┌─ 交互层 ────────────────────────┐ ║ │
│  ║  │ BGE 语义护栏        │  │ Flask+SSE Web UI │ Piper TTS    │ ║ │
│  ║  │ 正则兜底            │  │ Whisper ASR      │ 13帧猫咪动画 │ ║ │
│  ║  └─────────────────────┘  └─────────────────────────────────┘ ║ │
│  ╚═══════════════════════════════════════════════════════════════╝ │
└──────────────────────────────────────────────────────────────────────┘
```

> 上图为目标架构。当前 Demo 以宿主机直连 TRT-LLM 模式运行（`ENGINE=trtllm`），NemoClaw 沙箱网络策略已通过 `openshell policy set` 配置并验证，沙箱内全量运行待 alpha 版文件挂载机制适配后完成迁移。

**推理路由设计（已完成配置验证）：**
- **Qwen3-30B**（对话核心）→ OpenShell `inference.local` 安全路由，gateway 自动代理转发到宿主机 `:8355`，沙箱代码不接触真实地址
- **Phi-4-multimodal**（裁判引擎）→ `sandbox-policy.yaml` 网络白名单，直连 `host.openshell.internal:8356`

---

## 功能特性

### 🔍 全天候静默感知 + 主动破冰

CPU 端常驻部署四路轻量化感知模型，全天候低功耗静默运行。各路感知结果统一汇入 EventStore 事件总线，由 Phi-4 融合裁判定时巡检，检测到复合情绪模式时主动发起关心。

### 🧠 LLM-as-Judge 自然语言决策

Phi-4 作为独立裁判引擎进行自然语言逻辑推理，全权决定是否开口及采用何种干预策略（共情倾听、鼓励支持、注意力转移、温柔提醒、静默陪伴），输出结构化决策理由。

### 🔒 端侧隐私架构

系统设计为在 NemoClaw 沙箱中运行，已完成以下安全配置验证：
- `sandbox-policy.yaml` 仅放行 Phi-4 裁判直连端口（`:8356`），删除了默认策略中所有外部域名白名单
- Qwen3 通过 OpenShell 推理路由代理（`openshell inference set` 已注册）
- `inference_config.py` 支持 `trtllm` / `nemoclaw` / `nemoclaw_whitelist` / `ollama` 四种引擎一键切换

当前 Demo 以宿主机直连 TRT-LLM 模式运行，NemoClaw alpha 版本的沙箱文件系统挂载方案仍在适配中。

### 💾 双轨记忆网络

短期感知记忆通过 EventStore 实现 24 小时自动过期。长期语义记忆通过 FAISS 向量库持久化关键对话。结合心理学干预 RAG 策略库，实现具备时间连贯性的陪伴成长。

### 🎭 高容错 Demo 演示

内置 5 种极端压力场景的社交消息模拟注入脚本（工作压力、社交孤立、好消息、深夜加班、朋友吵架），确保核心业务逻辑的演示万无一失。

---

## 技术栈

| 类别 | 技术 | 作用 |
|------|------|------|
| 硬件 | DGX Spark | 128GB 统一内存，承载全部推理与感知 |
| 推理引擎 | TensorRT-LLM | NVFP4 精度加速，TTFT 28ms |
| 对话模型 | Qwen3-30B-A3B | 猫咪人格拟真对话核心 |
| 裁判模型 | Phi-4-multimodal-instruct | 多模态融合裁判 |
| 向量嵌入 | BGE-large-zh-v1.5 | 语义护栏 + 长期记忆 |
| 向量检索 | FAISS + ChromaDB | 长期记忆 + RAG 策略库 |
| 语音识别 | Whisper | 语音输入转文字（本地） |
| 语音合成 | Piper TTS | 中文语音合成（本地） |
| 沙箱 | NemoClaw / OpenShell 0.1.0 | 沙箱网络策略与推理隐私路由（已完成策略配置） |
| 前端 | Flask + SSE | 实时猫咪情绪动画 |

---

## 快速开始

### 环境要求

- NVIDIA DGX Spark（128GB 统一内存）
- Ubuntu 24.04, ARM64
- Docker 28.x+（用于运行 TRT-LLM 容器）
- Python 3.12+
- OpenShell 0.1.0 + NemoClaw（可选，用于沙箱部署）

### 1. 克隆仓库

```bash
git clone https://github.com/lujunlin-cn/MiaoAgent.git
cd MiaoAgent
```

### 2. 安装 Python 依赖

```bash
python3 -m venv frontend/.venv
source frontend/.venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装系统组件

#### 3.1 Piper TTS（本地中文语音合成）

```bash
# DGX Spark 是 ARM64
cd /tmp
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
tar xzf piper_linux_aarch64.tar.gz
sudo cp piper/piper /usr/local/bin/piper
sudo cp piper/lib*.so* /usr/local/lib/
[ -d piper/lib ] && sudo cp piper/lib/lib*.so* /usr/local/lib/
sudo ldconfig
```

#### 3.2 Whisper

Whisper 通过 pip 安装（已包含在 `requirements.txt` 中），首次运行时自动下载 `base` 模型权重（~140MB）。如需离线部署，提前运行 `python3 -c "import whisper; whisper.load_model('base')"` 并拷贝 `~/.cache/whisper/`。

### 4. 下载模型

将以下模型放置到 `models/` 目录：

```
models/
├── bge-large-zh-v1.5/              # BGE 中文嵌入模型（语义护栏 + 记忆）
├── distilbert-sentiment/           # DistilBERT 中文情感分类
├── piper/
│   ├── zh_CN-huayan-medium.onnx    # Piper TTS 中文语音模型
│   └── zh_CN-huayan-medium.onnx.json
├── emotion2vec_plus_large/         # emotion2vec 语气情绪（CPU）
└── panns/
    └── Cnn14_mAP=0.431.pth        # PANNs 环境音分类（CPU）
```

### 5. 启动 TRT-LLM 推理服务

```bash
# Qwen3-30B-A3B（端口 8355）
trtllm-serve serve /path/to/qwen3-model \
  --host 0.0.0.0 --port 8355 \
  --max_batch_size 4 --tp_size 1

# Phi-4-multimodal-instruct（端口 8356）
trtllm-serve serve /path/to/phi4-model \
  --host 0.0.0.0 --port 8356 \
  --max_batch_size 4 --tp_size 1

# 验证
curl -s http://localhost:8355/v1/models | python3 -m json.tool
curl -s http://localhost:8356/v1/models | python3 -m json.tool
```

### 6. 启动 MiaoAgent

```bash
source frontend/.venv/bin/activate
python3 frontend/web_ui.py
```

访问 `http://127.0.0.1:5000` 即可看到猫咪界面。

远程访问：
```bash
ssh -L 5000:127.0.0.1:5000 user@your-dgx-spark-ip
```

### 7. 运行测试

```bash
# 全量测试
sudo $(which python3) run_all_tests.py

# 只跑性能测试
sudo $(which python3) run_all_tests.py --only perf

# 只跑护栏测试
sudo $(which python3) run_all_tests.py --only guard
```

### 8. Demo 演示

```bash
# 注入压力场景，触发猫咪主动关心（需要 Web UI 已启动）
python3 demo_social_messages.py --scenario stressed --api

# 可选场景：stressed, lonely, happy, late_night, fight
```

---

## NemoClaw 沙箱配置（可选）

MiaoAgent 的安全架构设计为在 NemoClaw 沙箱中运行。以下配置已完成验证：

**已完成：**
- `sandbox-policy.yaml` 网络策略已通过 `openshell policy set` 应用至沙箱实例
- Qwen3 推理路由已通过 `openshell provider create` + `openshell inference set` 注册
- `inference_config.py` 支持 `nemoclaw` 引擎模式一键切换
- `nemoclaw_recover.sh` 开机恢复脚本已编写

**待完成：**
- NemoClaw alpha 版本的沙箱文件系统挂载方案适配（应用代码迁入沙箱内运行）

```bash
# 沙箱网络策略配置
sudo nemoclaw onboard
sudo openshell policy set catagent --policy sandbox-policy.yaml --wait

# 注册 Qwen3 推理路由
sudo openshell provider create \
    --name trtllm-qwen3 --type openai \
    --credential OPENAI_API_KEY=empty \
    --config OPENAI_BASE_URL=http://host.openshell.internal:8355/v1
sudo openshell inference set \
    --provider trtllm-qwen3 --model qwen3 --no-verify

# 重启后恢复
sudo bash nemoclaw_recover.sh
```

---

## 推理引擎切换

通过环境变量一键切换推理后端：

```bash
# TRT-LLM 直连（默认，当前 Demo 使用）
export MIAOAGENT_ENGINE=trtllm

# NemoClaw 沙箱模式（沙箱全量部署后使用）
# Qwen3 走 inference.local 安全路由，Phi-4 走白名单直连
export MIAOAGENT_ENGINE=nemoclaw

# NemoClaw 白名单模式（Issue #326 workaround）
# 两个模型都走白名单直连 host.openshell.internal
export MIAOAGENT_ENGINE=nemoclaw_whitelist

# Ollama 调试模式
export MIAOAGENT_ENGINE=ollama
```

---

## 常见问题

### NemoClaw 重启后无法连接

DGX Spark 关机/重启后 NemoClaw 沙箱不会自动恢复（alpha 版本已知限制）：

```bash
sudo bash nemoclaw_recover.sh
```

如果 sandbox Phase 不是 Ready（SSH key 失效等），需要完全重建：

```bash
sudo nemoclaw onboard
sudo openshell policy set catagent --policy sandbox-policy.yaml --wait
```

### inference.local 不可达（Issue #326）

如果 OpenShell 推理路由 `inference.local` DNS 解析失败：

```bash
# 切换到白名单模式，两个模型都直连
export MIAOAGENT_ENGINE=nemoclaw_whitelist
```

### 验证 TRT-LLM 服务状态

```bash
curl -s http://localhost:8355/v1/models | python3 -m json.tool
curl -s http://localhost:8356/v1/models | python3 -m json.tool
```

---

## 项目结构

```
MiaoAgent/
├── frontend/                      # Web UI
│   ├── web_ui.py                  # Flask + SSE 主程序
│   └── templates/                 # HTML 模板（含 13 帧猫咪情绪动画）
├── skills/                        # 核心技能模块
│   ├── emotion_perception/        # 多模态感知（DeepFace/DistilBERT/emotion2vec/PANNs）
│   ├── proactive_engine/          # 主动对话决策引擎（LLM-as-Judge）
│   ├── companion_persona/         # 猫咪人格对话生成
│   ├── safety/                    # 语义护栏（BGE + 分类器 + 正则）
│   ├── memory/                    # FAISS 长期语义记忆
│   ├── bridge/                    # 社交消息桥接器（只读设计）
│   ├── tts/                       # Piper TTS 语音合成
│   ├── audio/                     # Whisper 语音识别
│   └── shared/                    # 共享模块（EventStore/推理配置/嵌入单例）
├── rag/                           # 心理学 RAG 策略库
│   ├── data/                      # 心理学对话策略语料
│   ├── retriever.py               # ChromaDB 检索器
│   └── build_kb.py                # 知识库构建脚本
├── prompt/                        # Prompt 模板
│   ├── cat_persona.txt            # 猫咪人格 System Prompt
│   └── fusion_judge.txt           # 融合裁判 Prompt
├── models/                        # 本地模型（不提交到 Git）
├── run_all_tests.py               # 全栈自动化验证脚本
├── demo_social_messages.py        # Demo 场景注入脚本
├── nemoclaw_recover.sh            # NemoClaw 开机恢复脚本
├── sandbox-policy.yaml            # NemoClaw 沙箱策略（仅放行 Phi-4 直连端口）
└── requirements.txt               # Python 依赖
```

---

## 团队

| 成员 | 角色 | 核心贡献 |
|------|------|----------|
| **陆俊林** | 架构师 / 队长 | 系统架构设计；TRT-LLM 集成与调优；NemoClaw 沙箱策略配置；EventStore 事件总线 |
| **邱靖翔** | 情感科学 + RAG | 心理学策略语料库构建；ChromaDB RAG 模块；融合裁判 Prompt 工程 |
| **李雨珍** | NLP + 前端 | Qwen3 猫咪人格 Prompt；Flask + SSE Web UI；13 帧情绪插画；TTS/ASR |
| **陈昕博** | 安全架构 + 产品 | BGE 语义护栏模块；正则安全层；FAISS 记忆模块；测试框架 |

---

## 许可证

MIT License

---

<p align="center">
  <i>MiaoAgent — 数据不出端，关怀不缺席。</i><br/>
  <i>NVIDIA DGX Spark Hackathon 2026</i>
</p>
