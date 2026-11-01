"""Generate local Compose secrets once, using only the Python standard library."""
import argparse
from pathlib import Path
import secrets

KEYS = ['STACK_DB_PASSWORD', 'STACK_APP_PASSWORD', 'STACK_VECTOR_PASSWORD', 'STACK_READER_PASSWORD']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    output = parser.parse_args().output
    if output.exists():
        configured = {line.split('=', 1)[0] for line in output.read_text(encoding='utf-8').splitlines() if '=' in line}
        if not set(KEYS).issubset(configured):
            raise SystemExit('Existing Compose env file is incomplete; restore it rather than resetting database credentials.')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(key + '=' + secrets.token_hex(32) + '\n' for key in KEYS), encoding='utf-8')
    print('Compose environment ready. Keep this file with its database volume; do not commit it.')
