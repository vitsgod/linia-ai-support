"""Add the journal table without changing tickets. Safe to run repeatedly."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database import get_connection


if __name__ == '__main__':
    with get_connection() as conn:
        conn.execute((ROOT / 'backend' / 'history.sql').read_text(encoding='utf-8'))
    print('Assistant history table ready; tickets were not modified.')
