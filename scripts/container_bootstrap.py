"""Prepare only the dedicated Compose database cluster; no host databases are used."""
import os
from pathlib import Path
import sys
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.vector_store import init_store


def connect(database, user, password, **kwargs):
    return psycopg.connect(host='db', port=5432, dbname=database, user=user, password=password,
                           connect_timeout=5, **kwargs)


def main():
    admin = os.environ['PGADMIN_PASSWORD']
    roles = {'provider_app': os.environ['APP_PASSWORD'], 'provider_vectors': os.environ['VECTOR_PASSWORD'],
             'knowledge_reader': os.environ['READER_PASSWORD']}
    with connect('postgres', 'postgres', admin, autocommit=True) as conn:
        for role, password in roles.items():
            if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
                conn.execute(sql.SQL('CREATE ROLE {}').format(sql.Identifier(role)))
            conn.execute(sql.SQL('ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {}')
                         .format(sql.Identifier(role), sql.Literal(password)))
        for database, owner in [('provider_support', 'provider_app'), ('provider_support_test', 'provider_app'),
                                ('provider_knowledge', 'provider_vectors')]:
            if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,)).fetchone():
                conn.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(database), sql.Identifier(owner)))
    for database in ['provider_support', 'provider_support_test']:
        with connect(database, 'provider_app', roles['provider_app']) as conn:
            for script in ['schema.sql', 'history.sql']:
                conn.execute((ROOT / 'backend' / script).read_text(encoding='utf-8'))
    with connect('provider_knowledge', 'postgres', admin) as conn:
        init_store(conn)
        conn.execute('ALTER TABLE public.knowledge_chunks OWNER TO provider_vectors')
        conn.execute('GRANT CONNECT ON DATABASE provider_knowledge TO knowledge_reader')
        conn.execute('GRANT USAGE ON SCHEMA public TO knowledge_reader')
        conn.execute('GRANT SELECT ON TABLE public.knowledge_chunks TO knowledge_reader')
    print('Compose databases, schemas and read-only knowledge role are ready.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(f'Database preparation failed: {type(exc).__name__}. Check Compose DB readiness and retained env file.') from None
