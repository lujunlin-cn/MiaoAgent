# MiaoAgent — 情感陪伴智能体

基于 NVIDIA DGX Spark + NemoClaw + OpenClaw 的本地 AI 情感伴侣。

## 团队
- 陆俊林 (hajimi2025) — 架构师
- 邱靖翔 (jingxiang) — 情感科学 + RAG
- 李雨珍 (yuzhen) — NLP + 前端
- 陈昕博 (xinbo) — 安全架构 + 产品

## 目录结构
```
/opt/miaoagent/
├── skills/                    # OpenClaw Skills（核心代码）
│   ├── emotion_perception/    # Skill 1: 情感感知（摄像头+麦克风+环境音）
│   ├── proactive_engine/      # Skill 2: 主动对话引擎
│   └── companion_persona/     # Skill 3: 陪伴人格+TTS
├── rag/                       # RAG 知识库
│   └── data/                  # 心理学对话策略语料
├── frontend/                  # 猫咪界面 + 情绪 dashboard
├── assets/                    # 静态资源
│   └── cat_images/            # 12 张猫咪情绪插画
├── docs/                      # 文档
└── backups/                   # 自动备份（gitignored）
```

## 基础设施（仅 hajimi2025 管理）
- NemoClaw 沙箱：catbox
- 推理：Ollama + Gemma-3-27B（本地）
- OpenShell 网关：nemoclaw (port 8080)
