"""Search saved vectors: only the question is embedded on each run."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.embeddings import embed_query
from backend.vector_store import get_vector_connection, search_index


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='На телефоне интернет есть, а на ноутбуке нет')
    args = parser.parse_args()
    vector = embed_query(args.query)
    with get_vector_connection() as conn:
        results = search_index(conn, vector)
    print(json.dumps({'query': args.query, 'storage': 'pgvector', 'results': results}, ensure_ascii=False, indent=2))
    if not results:
        print('Нет фрагментов текущей модели. Запустите scripts/index_knowledge.py.')
    print('Близость не доказывает релевантность. Генерация ответа пока не подключена.')


if __name__ == '__main__':
    main()
