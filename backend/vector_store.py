"""Dedicated pgvector store. The tickets database is never used here."""
import json
import os
from pathlib import Path

from dotenv import dotenv_values
import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict

from backend.embeddings import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from backend.knowledge import KnowledgeChunk
from backend.semantic_search import normalize_vector

ROOT = Path(__file__).resolve().parents[1]


def get_vector_connection():
    if dsn := os.environ.get('VECTOR_DATABASE_URL'):
        return _connect_dsn(dsn)
    password = dotenv_values(ROOT / '.local' / 'vector.env').get('POSTGRES_PASSWORD')
    if not password:
        raise RuntimeError('Run scripts/local_vector_db.py first.')
    return psycopg.connect(host='127.0.0.1', port=55433, dbname='provider_knowledge',
                           user='provider_vectors', password=password, connect_timeout=3,
                           row_factory=dict_row, options='-c statement_timeout=5000')


def get_search_connection():
    if dsn := os.environ.get('VECTOR_SEARCH_URL'):
        return _connect_dsn(dsn, read_only=True)
    password = dotenv_values(ROOT / '.local' / 'vector-reader.env').get('POSTGRES_PASSWORD')
    if not password:
        raise RuntimeError('Run scripts/prepare_rag.py first.')
    return psycopg.connect(host='127.0.0.1', port=55433, dbname='provider_knowledge',
                           user='knowledge_reader', password=password, connect_timeout=3,
                           row_factory=dict_row,
                           options='-c statement_timeout=5000 -c default_transaction_read_only=on')


def _connect_dsn(dsn: str, read_only: bool = False):
    options = conninfo_to_dict(dsn).get('options', '') + ' -c statement_timeout=5000'
    if read_only:
        options += ' -c default_transaction_read_only=on'
    return psycopg.connect(dsn, connect_timeout=3, row_factory=dict_row, options=options)


def init_store(conn):
    with conn.transaction():
        conn.execute('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public')
        conn.execute('''CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id text PRIMARY KEY, document_id text NOT NULL, title text NOT NULL,
            section text NOT NULL, source text NOT NULL, text text NOT NULL,
            model text NOT NULL, embedding vector(1024) NOT NULL
        )''')


def _literal(vector):
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError('Expected 1024 vector components')
    return json.dumps(normalize_vector(vector), allow_nan=False)


def replace_index(conn, chunks: list[KnowledgeChunk], vectors: list[list[float]]) -> int:
    if not chunks or len(chunks) != len(vectors):
        raise ValueError('Need one vector for every nonempty chunk')
    if len({chunk.id for chunk in chunks}) != len(chunks):
        raise ValueError('Chunk IDs must be unique')
    values = [(c.id, c.document_id, c.title, c.section, c.source, c.text, EMBEDDING_MODEL, _literal(v))
              for c, v in zip(chunks, vectors)]
    with conn.transaction():
        conn.execute('DELETE FROM knowledge_chunks')
        with conn.cursor() as cursor:
            cursor.executemany('''INSERT INTO knowledge_chunks
                (id, document_id, title, section, source, text, model, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector)''', values)
    return len(values)


def search_index(conn, vector: list[float], limit: int = 3) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('Limit must be between 1 and 20')
    literal = _literal(vector)
    with conn.transaction():
        return conn.execute('''SELECT id, document_id, title, section, source, text,
            1 - (embedding <=> %s::vector) AS score FROM knowledge_chunks
            WHERE model = %s ORDER BY embedding <=> %s::vector, id LIMIT %s''',
            (literal, EMBEDDING_MODEL, literal, limit)).fetchall()
