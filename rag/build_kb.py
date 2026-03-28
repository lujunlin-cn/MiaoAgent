"""
build_kb.py - Build dialogue-strategy knowledge base with ChromaDB.

Usage:
  python3 rag/build_kb.py
  python3 rag/build_kb.py --reset
  python3 rag/build_kb.py --model BAAI/bge-large-zh-v1.5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

try:
    import chromadb
except Exception:
    chromadb = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "strategies.json"
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
            print(f"[RAG] loading embedding model: {name}")
            return SentenceTransformer(name)
        except Exception as e:
            last_error = e
            print(f"[RAG] model load failed: {name}, err={e}")
    raise RuntimeError(f"failed to load any embedding model: {last_error}")


def _load_strategies(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"strategies file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("strategies.json must be a JSON list")
    for i, item in enumerate(data):
        for k in ("id", "scenario", "strategy", "example_reply"):
            if k not in item:
                raise ValueError(f"item[{i}] missing key: {k}")
    return data


def _build_document(item: Dict) -> str:
    trigger_emotion = ", ".join(item.get("trigger_emotion", []))
    trigger_env = ", ".join(item.get("trigger_env", []))
    tags = ", ".join(item.get("tags", []))
    return (
        f"场景: {item['scenario']}\n"
        f"触发情绪: {trigger_emotion}\n"
        f"触发环境: {trigger_env}\n"
        f"策略: {item['strategy']}\n"
        f"示例回复: {item['example_reply']}\n"
        f"标签: {tags}"
    )


def build_kb(reset: bool = False, model_name: str = "BAAI/bge-large-zh-v1.5") -> None:
    if chromadb is None:
        raise RuntimeError("chromadb is not installed")
    strategies = _load_strategies(DATA_PATH)

    DB_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_PATH))

    if reset:
        try:
            client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Cat companion dialogue strategies"},
    )

    model = _load_embedding_model(model_name)

    ids = []
    docs = []
    metas = []
    for item in strategies:
        ids.append(str(item["id"]))
        docs.append(_build_document(item))
        metas.append(
            {
                "strategy": item["strategy"],
                "scenario": item["scenario"],
                "source": "strategies.json",
            }
        )

    embeddings = model.encode(docs, normalize_embeddings=True).tolist()

    collection.upsert(
        ids=ids,
        documents=docs,
        metadatas=metas,
        embeddings=embeddings,
    )

    print(f"[RAG] collection: {COLLECTION_NAME}")
    print(f"[RAG] records: {collection.count()}")
    print(f"[RAG] model: {model_name} (or fallback)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ChromaDB strategy KB")
    parser.add_argument("--reset", action="store_true", help="drop old collection before build")
    parser.add_argument("--model", default="BAAI/bge-large-zh-v1.5", help="sentence-transformers model")
    args = parser.parse_args()

    build_kb(reset=args.reset, model_name=args.model)


if __name__ == "__main__":
    main()
