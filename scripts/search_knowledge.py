"""Educational semantic search in memory; PostgreSQL and generation are not involved."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.embeddings import EMBEDDING_MODEL, EmbeddingError, embed_documents, embed_query
from backend.knowledge import load_chunks
from backend.semantic_search import rank_chunks


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="На телефоне интернет есть, а на ноутбуке нет")
    args = parser.parse_args()
    chunks = load_chunks(ROOT / "knowledge")
    # This tiny tutorial deliberately computes vectors on every run; pgvector persistence is next.
    vectors = embed_documents([chunk.text for chunk in chunks])
    query_vector = embed_query(args.query)
    results = rank_chunks(chunks, vectors, query_vector)
    report = {
        "query": args.query, "model": EMBEDDING_MODEL,
        "chunk_count": len(chunks), "dimensions": len(query_vector),
        "query_vector_first_8": query_vector[:8],
        "storage": "in_memory_demo",
        "results": [{"score": item["score"], "chunk": asdict(item["chunk"])} for item in results],
    }
    destination = ROOT / ".local" / "semantic-search-demo.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Модель: {EMBEDDING_MODEL}. Фрагментов: {len(chunks)}. Размерность: {len(query_vector)}.")
    print(f"Вопрос: {args.query}")
    print(f"Первые 8 чисел вектора вопроса: {query_vector[:8]}")
    for item in results:
        chunk = item["chunk"]
        print(f"{item['score']:.4f} · {chunk.id} · {chunk.title} / {chunk.section}")
    print("Это близость текстов, не вероятность правильности ответа. Постоянного pgvector-хранилища пока нет.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, EmbeddingError) as exc:
        raise SystemExit(str(exc)) from None
