"""Provision a read-only knowledge login. Credentials stay in ignored .local."""
from pathlib import Path
import secrets
import sys
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.vector_store import get_vector_connection, init_store


def main():
    destination = ROOT / '.local' / 'vector-reader.env'
    password = dotenv_values(destination).get('POSTGRES_PASSWORD') or secrets.token_hex(32)
    with get_vector_connection() as conn:
        init_store(conn)
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname='knowledge_reader'").fetchone()
        if not exists:
            conn.execute('CREATE ROLE knowledge_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT')
        conn.execute(sql.SQL('ALTER ROLE knowledge_reader PASSWORD {}').format(sql.Literal(password)))
        conn.execute('GRANT CONNECT ON DATABASE provider_knowledge TO knowledge_reader')
        conn.execute('GRANT USAGE ON SCHEMA public TO knowledge_reader')
        conn.execute('GRANT SELECT ON TABLE public.knowledge_chunks TO knowledge_reader')
    destination.write_text('POSTGRES_PASSWORD=' + password + '\n', encoding='utf-8')
    print('Read-only knowledge login ready. No credentials printed.')


if __name__ == '__main__':
    main()
