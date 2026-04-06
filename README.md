<p align="center">
  <img src="assets/cat_images/neutral_idle.png" width="120" alt="MiaoAgent"/>
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
| 情感数据上云的隐私焦虑 | 全栈端侧部署，零云依赖，沙箱网络隔离 |
| 一问一答的被动交互 | 全天候静默感知 + LLM 主动决策破冰 |
| 固定权重打分的不可解释 | LLM-as-Judge 自然语言推理，输出结构化决策理由 |

---

## 核心性能

> 以下数据由 `run_all_tests_v2.py` 自动化脚本在 DGX Spark 上实测生成

| 指标 | 实测值 | 说明 |
|------|--------|------|
| **Qwen3-30B TTFT** | **28 ms** | TRT-LLM + NVFP4，5轮均值 |
| **Qwen3-30B 吞吐** | **68.5 chars/s** | 中文字符/秒 |
| **TRT-LLM vs Ollama** | **10.2x 加速** | 同硬件对比 Gemma3-27B on Ollama |
| 双模型并发峰值内存 | 80.1 GB / 128 GB | Qwen3 + Phi-4 同时推理 |
| 语义护栏准确率 | 98.3% | 102条样本，召回率 100% |
| 语义护栏延迟 | 10.3 ms | BGE 嵌入 + 逻辑回归 |
| ChromaDB 检索延迟 | 16.3 ms | 排除首次模型加载 |
| 主动对话端到端 | ✅ 触发成功 | 事件注入 → 裁判决策 → SSE 推送 |
| 沙箱外联阻断 | ✅ 通过 | iptables + NemoClaw 双层隔离 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        DGX Spark (128GB)                        │
│                                                                 │
│  ┌─── CPU 感知层（常驻低功耗）───┐   ┌─── GPU 推理层 ──────────┐ │
│  │ DeepFace    面部情绪          │   │ Qwen3-30B-A3B  对话核心 │ │
│  │ DistilBERT  文字情感          │   │ (TRT-LLM, NVFP4)       │ │
│  │ emotion2vec 语气语调          │   │                         │ │
│  │ PANNs       环境底噪          │   │ Phi-4-multimodal 裁判   │ │
│  └──────────┬───────────────────┘   │ (TRT-LLM, NVFP4)       │ │
│             │ 结构化事件              └────────┬────────────────┘ │
│             ▼                                 │                  │
│  ┌─── EventStore 事件总线 ───┐                │                  │
│  │ 24h 自动过期 | 多源汇聚   │◄───────────────┘                  │
│  └──────────┬───────────────┘                                   │
│             │                                                    │
│  ┌─── 记忆层 ──────────────────┐  ┌─── 安全层 ────────────────┐ │
│  │ FAISS     长期语义记忆       │  │ NemoClaw   沙箱网络隔离   │ │
│  │ ChromaDB  心理学 RAG 策略库  │  │ BGE 护栏   语义注入防御   │ │
│  └─────────────────────────────┘  │ 正则兜底   变异攻击覆盖   │ │
│                                    └───────────────────────────┘ │
│  ┌─── 交互层 ──────────────────────────────────────────────────┐ │
│  │ Flask + SSE Web UI │ Piper TTS │ Whisper ASR │ 12帧猫咪动画 │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 功能特性

### 🔍 全天候静默感知 + 主动破冰

CPU 端常驻部署四路轻量化感知模型，全天候低功耗静默运行。各路感知结果统一汇入 EventStore 事件总线，由 Phi-4 融合裁判定时巡检，检测到复合情绪模式时主动发起关心。

### 🧠 LLM-as-Judge 自然语言决策

Phi-4 作为独立裁判引擎进行自然语言逻辑推理，全权决定是否开口及采用何种干预策略（共情倾听、鼓励支持、注意力转移、温柔提醒、静默陪伴），输出结构化决策理由。

### 🔒 端侧隐私验证

整个智能体部署在 NemoClaw 沙箱中，通过网络策略拦截除白名单外的一切网络请求。运行时自动启用 iptables 外联阻断，退出时自动恢复。

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
| 沙箱 | NemoClaw | 内核级网络隔离 |
| 前端 | Flask + SSE | 实时猫咪情绪动画 |

---

## 快速开始

### 环境要求

- NVIDIA DGX Spark（128GB 统一内存）
- Ubuntu 24.04, ARM64
- TensorRT-LLM 1.3.0rc09+
- Python 3.12+

### 1. 克隆仓库

```bash
git clone https://github.com/lujunlin-cn/MiaoAgent.git
cd MiaoAgent
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv frontend/.venv
source frontend/.venv/bin/activate

# 安装依赖
pip install -r requirements_v3.txt
```

### 3. 下载模型

将以下模型放置到 `models/` 目录：

```
models/
├── bge-large-zh-v1.5/           # BGE 中文嵌入模型
├── distilbert-sentiment/        # DistilBERT 情感分类
├── piper/
│   └── zh_CN-huayan-medium.onnx # Piper TTS 中文模型
├── emotion2vec_plus_large/      # emotion2vec 语气情绪
└── panns/
    └── Cnn14_mAP=0.431.pth     # PANNs 环境音分类
```

### 4. 启动 TRT-LLM 推理服务

```bash
# Qwen3-30B-A3B（端口 8355）
trtllm-serve serve /path/to/qwen3-model \
  --host 0.0.0.0 --port 8355 \
  --max_batch_size 4 --tp_size 1

# Phi-4-multimodal-instruct（端口 8356）
trtllm-serve serve /path/to/phi4-model \
  --host 0.0.0.0 --port 8356 \
  --max_batch_size 4 --tp_size 1
```

### 5. 启动 MiaoAgent

```bash
# 方式一：快速启动脚本
bash start.sh

# 方式二：手动启动 Web UI
source frontend/.venv/bin/activate
python3 frontend/web_ui_complete.py
```

访问 `http://127.0.0.1:5000` 即可看到猫咪界面。

远程访问：
```bash
ssh -L 5000:127.0.0.1:5000 user@your-dgx-spark-ip
```

### 6. 运行测试

```bash
# 全量测试（需要 sudo 权限用于沙箱网络隔离）
sudo $(which python3) run_all_tests_v2.py

# 只跑性能测试
sudo $(which python3) run_all_tests_v2.py --only perf

# 只跑护栏测试
sudo $(which python3) run_all_tests_v2.py --only guard
```

### 7. Demo 演示

```bash
# 注入压力场景，触发猫咪主动关心
python3 demo_social_messages.py --scenario stressed

# 可选场景：stressed, isolated, good_news, late_night, friend_fight
```

---

## 推理引擎切换

通过环境变量一键切换推理后端：

```bash
# TRT-LLM 直连（默认，生产用）
export MIAOAGENT_ENGINE=trtllm

# NemoClaw 沙箱模式
export MIAOAGENT_ENGINE=nemoclaw

# Ollama 调试模式
export MIAOAGENT_ENGINE=ollama
```

---

## 项目结构

```
MiaoAgent/
├── frontend/                      # Web UI
│   ├── web_ui_complete.py         # Flask + SSE 主程序
│   ├── templates/                 # HTML 模板（含 12 帧猫咪动画）
│   └── static/                    # 静态资源
├── skills/                        # 核心技能模块
│   ├── emotion_perception/        # 多模态感知（DeepFace/DistilBERT/emotion2vec/PANNs）
│   ├── proactive_engine/          # 主动对话决策引擎（LLM-as-Judge）
│   ├── companion_persona/         # 猫咪人格对话生成
│   ├── safety/                    # 语义护栏（BGE + 分类器 + 正则）
│   ├── memory/                    # FAISS 长期语义记忆
│   ├── bridge/                    # 社交消息桥接器（只读设计）
│   ├── tts/                       # Piper TTS 语音合成
│   ├── audio/                     # Whisper 语音识别
│   └── shared/                    # 共享模块（EventStore/推理配置）
├── rag/                           # 心理学 RAG 策略库
│   ├── data/                      # 心理学对话策略语料
│   ├── retriever.py               # ChromaDB 检索器
│   └── build_kb.py                # 知识库构建脚本
├── prompt/                        # Prompt 模板
│   ├── cat_persona.txt            # 猫咪人格 System Prompt
│   └── fusion_judge.txt           # 融合裁判 Prompt
├── models/                        # 本地模型（不提交到 Git）
├── run_all_tests_v2.py            # 全栈自动化验证脚本
├── demo_social_messages.py        # Demo 场景注入脚本
├── start.sh                       # 快速启动脚本
└── sandbox-policy.yaml            # NemoClaw 沙箱策略
```

---

## 团队

| 成员 | 角色 | 核心贡献 |
|------|------|----------|
| **陆俊林** | 架构师 / 队长 | 系统架构设计；TRT-LLM 集成与调优；NemoClaw 沙箱部署；EventStore 事件总线 |
| **邱靖翔** | 情感科学 + RAG | 心理学策略语料库构建；ChromaDB RAG 模块；融合裁判 Prompt 工程 |
| **李雨珍** | NLP + 前端 | Qwen3 猫咪人格 Prompt；Flask + SSE Web UI；12 帧情绪插画；TTS/ASR |
| **陈昕博** | 安全架构 + 产品 | BGE 语义护栏模块；正则安全层；FAISS 记忆模块；测试框架 |

---

## 许可证

MIT License

---

<p align="center">
  <i>MiaoAgent — 数据不出端，关怀不缺席。</i><br/>
  <i>NVIDIA DGX Spark Hackathon 2026</i>
</p>
