"""
retriever.py - Retrieve dialogue strategies from ChromaDB.

Usage:
    python3 -m rag.retriever "用户很累，很晚还在工作"
  python3 rag/retriever.py "用户很累，很晚还在工作"
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

try:
    import chromadb
except Exception:
    chromadb = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

from skills.shared.event_store import store


DB_PATH = ROOT / "db"
COLLECTION_NAME = "dialogue_strategies_v1"
LOCAL_BGE_DIR = ROOT.parent / "models" / "bge-large-zh-v1.5"


def _load_embedding_model(preferred_model: str) -> SentenceTransformer:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed")
    local_candidate = str(LOCAL_BGE_DIR)
    candidates = [
        local_candidate,
        preferred_model,
        "BAAI/bge-base-zh-v1.5",
        "shibing624/text2vec-base-chinese",
        "paraphrase-multilingual-MiniLM-L12-v2",
    ]
    last_error = None
    for name in candidates:
        try:
            return SentenceTransformer(name)
        except Exception as e:
            last_error = e
            print(f"[RAG] retriever model load failed: {name}, err={e}")
    raise RuntimeError(f"failed to load embedding model for retriever: {last_error}")


class StrategyRetriever:
    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5"):
        if chromadb is None:
            raise RuntimeError("chromadb is not installed, please pip install chromadb")
        self.model_name = model_name
        self._model = None
        self._client = chromadb.PersistentClient(path=str(DB_PATH))
        self._collection = self._client.get_or_create_collection(name=COLLECTION_NAME)

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = _load_embedding_model(self.model_name)
        return self._model

    def query(self, scene_desc: str, top_k: int = 3) -> List[Dict]:
        if not scene_desc.strip():
            return []

        emb = self._get_model().encode([scene_desc], normalize_embeddings=True).tolist()[0]
        # Pull extra rows first, then de-duplicate to return cleaner top-k results.
        query_size = max(1, top_k * 4)
        result = self._collection.query(
            query_embeddings=[emb],
            n_results=query_size,
            include=["distances", "documents", "metadatas"],
        )

        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]

        rows = []
        seen = set()
        for i in range(len(docs)):
            score = 1.0 - float(dists[i]) if i < len(dists) else 0.0
            strategy = (metas[i] or {}).get("strategy", "unknown")
            scenario = (metas[i] or {}).get("scenario", "")
            dedupe_key = (strategy, scenario)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "score": round(score, 4),
                    "strategy": strategy,
                    "scenario": scenario,
                    "document": docs[i],
                }
            )
            if len(rows) >= top_k:
                break
        return rows


def build_query_from_recent_events(minutes: int = 30) -> str:
    events = store.get_recent(minutes=minutes)
    if not events:
        return "用户状态未知，需要中性关怀"

    latest = events[-12:]
    emotions = []
    sources = []
    contexts = []
    for e in latest:
        raw = e.raw_label or {}
        emo = raw.get("emotion")
        if emo:
            emotions.append(str(emo))
        if e.source:
            sources.append(str(e.source))
        contexts.append(f"[{e.source}] {e.content}")

    emo_text = ", ".join(emotions[-4:]) if emotions else "neutral"
    src_text = ", ".join(sorted(set(sources[-6:]))) if sources else "unknown"
    ctx_text = " ; ".join(contexts[-5:])
    return (
        f"最近情绪: {emo_text}。"
        f"事件来源: {src_text}。"
        f"最近事件: {ctx_text}。"
        "请给出最适合的陪伴策略和一句示例回复。"
    )


def retrieve_for_current_context(top_k: int = 3, minutes: int = 30) -> List[Dict]:
    query = build_query_from_recent_events(minutes=minutes)
    retriever = StrategyRetriever()
    return retriever.query(query, top_k=top_k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query strategy KB")
    parser.add_argument("query", nargs="?", default="用户深夜加班且明显疲惫", help="scene description")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    r = StrategyRetriever()
    rows = r.query(args.query, top_k=args.top_k)
    print(f"query: {args.query}")
    if not rows:
        print("no results")
        return

    for i, item in enumerate(rows, 1):
        print(f"\n[{i}] score={item['score']}")
        print(f"strategy: {item['strategy']}")
        print(f"scenario: {item['scenario']}")
        print(item["document"])


if __name__ == "__main__":
    main()
