"""
embedder_singleton.py — BGE 嵌入模型共享单例

解决 SemanticGuard / ConversationMemory / StrategyRetriever
各自加载一份 BGE (~1.3GB) 导致浪费 ~4GB 内存的问题。
"""
import os
import threading

_lock = threading.Lock()
_instance = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BGE_MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "bge-large-zh-v1.5")


def get_shared_embedder():
    """获取全局共享的 SentenceTransformer 实例（线程安全）"""
    global _instance
    if _instance is not None:
        return _instance
    with _lock:
        if _instance is not None:
            return _instance
        from sentence_transformers import SentenceTransformer
        if os.path.exists(BGE_MODEL_DIR):
            _instance = SentenceTransformer(BGE_MODEL_DIR)
        else:
            _instance = SentenceTransformer("BAAI/bge-large-zh-v1.5")
        print("[SharedEmbedder] BGE model loaded (shared singleton)")
        return _instance
