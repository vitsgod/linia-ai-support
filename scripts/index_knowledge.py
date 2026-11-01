"""Embed Markdown documents and commit a replacement pgvector index."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.embeddings import embed_documents
from backend.knowledge import load_chunks
from backend.vector_store import get_vector_connection, init_store, replace_index


def main():
    chunks = load_chunks(ROOT / 'knowledge')
    vectors = []
    for start in range(0, len(chunks), 16):
        vectors.extend(embed_documents([chunk.text for chunk in chunks[start:start + 16]]))
    with get_vector_connection() as conn:
        init_store(conn)
        count = replace_index(conn, chunks, vectors)
    print(f'Committed {count} chunks with 1024-dimensional vectors to the configured pgvector database.')


if __name__ == '__main__':
    main()
