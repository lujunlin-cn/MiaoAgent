"""
conversation_memory.py — FAISS 语义长期记忆

原理（来自 NVIDIA DLI Notebook 7）：
- 用 FAISS 向量存储保存每次对话和感知事件
- 融合裁判时不只看最近 30 分钟，还能语义检索历史相关事件
- 猫咪能"记住"几天前的对话，实现长期情感陪伴

示例效果：
- 用户说"论文的事"→ 检索到 3 天前的"论文被退回"事件
- 猫咪回复"上次你说论文被退了，后来怎么样了喵？"

全部本地 FAISS，数据不出设备。
"""
import os
import time
import json
from pathlib import Path
from typing import List, Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = _PROJECT_ROOT / "memory"
FAISS_INDEX_PATH = MEMORY_DIR / "faiss_index"
BGE_MODEL_DIR = str(_PROJECT_ROOT / "models" / "bge-large-zh-v1.5")


class ConversationMemory:
    """FAISS 向量存储长期记忆"""

    def __init__(self):
        self._embedder = None
        self._store = None
        self._ready = False
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        """加载嵌入模型和 FAISS 索引"""
        try:
            from sentence_transformers import SentenceTransformer
            if os.path.exists(BGE_MODEL_DIR):
                self._embedder = SentenceTransformer(BGE_MODEL_DIR)
            else:
                self._embedder = SentenceTransformer("BAAI/bge-large-zh-v1.5")
        except Exception as e:
            print(f"[Memory] embedder failed: {e}")
            return

        try:
            from langchain_community.vectorstores import FAISS
            from langchain_core.embeddings import Embeddings

            # 包装 SentenceTransformer 为 LangChain Embeddings 接口
            embedder = self._embedder

            class BGEEmbeddings(Embeddings):
                def embed_documents(self, texts):
                    return embedder.encode(texts, normalize_embeddings=True).tolist()
                def embed_query(self, text):
                    return embedder.encode([text], normalize_embeddings=True)[0].tolist()

            self._lc_embedder = BGEEmbeddings()

            # 尝试加载已有索引
            if FAISS_INDEX_PATH.exists() and (FAISS_INDEX_PATH / "index.faiss").exists():
                self._store = FAISS.load_local(
                    str(FAISS_INDEX_PATH),
                    self._lc_embedder,
                    allow_dangerous_deserialization=True
                )
                count = len(self._store.docstore._dict)
                print(f"[Memory] loaded {count} memories from disk")
            else:
                # 创建空索引
                self._store = FAISS.from_texts(
                    ["MiaoAgent conversation memory initialized"],
                    self._lc_embedder,
                    metadatas=[{"type": "system", "timestamp": time.time()}]
                )
                print(f"[Memory] created new memory store")

            self._ready = True

        except ImportError:
            print(f"[Memory] FAISS not available: pip3 install faiss-cpu langchain-community")
        except Exception as e:
            print(f"[Memory] init failed: {e}")

    def add_conversation(self, user_msg: str, bot_reply: str, emotion: str = "neutral"):
        """记录一轮对话"""
        if not self._ready:
            return

        timestamp = time.time()
        time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))

        # 合并用户消息和猫咪回复为一条记忆
        memory_text = f"[{time_str}] 用户说：{user_msg} | 咪酱回复：{bot_reply}"

        self._store.add_texts(
            [memory_text],
            metadatas=[{
                "type": "conversation",
                "user_msg": user_msg[:200],
                "bot_reply": bot_reply[:200],
                "emotion": emotion,
                "timestamp": timestamp,
                "time_str": time_str,
            }]
        )

    def add_event(self, source: str, content: str, emotion: str = "neutral"):
        """记录感知事件（从 EventStore 同步）"""
        if not self._ready:
            return

        timestamp = time.time()
        time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))

        self._store.add_texts(
            [f"[{time_str}] [{source}] {content}"],
            metadatas=[{
                "type": "event",
                "source": source,
                "emotion": emotion,
                "timestamp": timestamp,
                "time_str": time_str,
            }]
        )

    def recall(self, query: str, k: int = 5, days: int = 7) -> List[Dict]:
        """语义检索相关记忆

        Args:
            query: 查询文本（如用户当前消息、或场景描述）
            k: 返回条数
            days: 只检索最近 N 天的记忆

        Returns:
            [{text, type, emotion, time_str, score}, ...]
        """
        if not self._ready:
            return []

        try:
            # FAISS 检索（返回 Document + score）
            results = self._store.similarity_search_with_score(query, k=k * 2)

            cutoff = time.time() - days * 86400
            memories = []

            for doc, score in results:
                ts = doc.metadata.get("timestamp", 0)
                if ts < cutoff:
                    continue
                memories.append({
                    "text": doc.page_content,
                    "type": doc.metadata.get("type", "unknown"),
                    "emotion": doc.metadata.get("emotion", "neutral"),
                    "time_str": doc.metadata.get("time_str", ""),
                    "score": float(score),
                })

            # 按时间排序，最近的在前
            memories.sort(key=lambda x: x.get("time_str", ""), reverse=True)
            return memories[:k]

        except Exception as e:
            print(f"[Memory] recall error: {e}")
            return []

    def recall_text(self, query: str, k: int = 3, days: int = 7) -> str:
        """检索记忆并格式化为文本（直接传给 LLM）"""
        memories = self.recall(query, k=k, days=days)
        if not memories:
            return ""

        lines = ["[长期记忆] 以下是与当前话题相关的历史片段："]
        for m in memories:
            lines.append(f"  {m['text']}")
        return "\n".join(lines)

    def clear(self):
        """清空所有记忆并重建空索引"""
        if not self._ready:
            return
        try:
            self._store = self.__class__._make_empty_store(self._lc_embedder)
            self.save()
            print("[Memory] cleared all memories")
        except Exception as e:
            print(f"[Memory] clear error: {e}")

    @staticmethod
    def _make_empty_store(lc_embedder):
        from langchain_community.vectorstores import FAISS
        return FAISS.from_texts(
            ["MiaoAgent conversation memory initialized"],
            lc_embedder,
            metadatas=[{"type": "system", "timestamp": time.time()}]
        )

    def save(self):
        """保存索引到磁盘"""
        if self._ready and self._store:
            self._store.save_local(str(FAISS_INDEX_PATH))
            count = len(self._store.docstore._dict)
            print(f"[Memory] saved {count} memories to {FAISS_INDEX_PATH}")

    def stats(self) -> dict:
        """统计信息"""
        if not self._ready:
            return {"ready": False, "count": 0}
        count = len(self._store.docstore._dict) if self._store else 0
        return {"ready": True, "count": count}


# 单例
_memory_instance = None

def get_memory() -> ConversationMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ConversationMemory()
    return _memory_instance
