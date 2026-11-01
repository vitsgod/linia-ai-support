import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from backend.schemas import TicketInput

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_connection() -> psycopg.Connection:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise psycopg.OperationalError("Database is not configured")
    options = conninfo_to_dict(dsn).get("options", "")
    return psycopg.connect(
        dsn, connect_timeout=3, row_factory=dict_row,
        options=f"{options} -c statement_timeout=5000",
    )


def create_ticket(ticket: TicketInput) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """INSERT INTO tickets (name, subject, description)
               VALUES (%s, %s, %s)
               RETURNING id, name, subject, description, status, created_at""",
            (ticket.name, ticket.subject, ticket.description),
        ).fetchone()
        # Normal exit from this block commits; an exception rolls back.
    # Return only after the transaction has committed successfully.
    return row


def list_tickets() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, name, subject, description, status, created_at
               FROM tickets ORDER BY created_at DESC, id DESC"""
        ).fetchall()
    return rows
