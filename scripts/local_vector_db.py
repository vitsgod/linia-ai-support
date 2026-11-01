"""Start or stop the isolated knowledge database; never remove its volume."""
import argparse
from pathlib import Path
import secrets
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    executable = shutil.which('docker') or r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    env_file = ROOT / '.local' / 'vector.env'
    env_file.parent.mkdir(exist_ok=True)
    if not env_file.exists():
        if args.stop:
            raise SystemExit('Knowledge database has not been configured.')
        # A missing credential file with an existing volume must not silently reset credentials.
        check = subprocess.run([executable, 'volume', 'inspect', 'provider-support-vectors_knowledge-data'],
                               capture_output=True)
        if check.returncode == 0:
            raise SystemExit('Existing knowledge volume: restore .local/vector.env before starting.')
        env_file.write_text('POSTGRES_PASSWORD=' + secrets.token_hex(32) + '\n', encoding='utf-8')
    command = [executable, 'compose', '--env-file', str(env_file), '-f', str(ROOT / 'compose.vectors.yaml')]
    subprocess.run(command + (['stop'] if args.stop else ['up', '-d', '--wait']), check=True)
    print('Knowledge database stopped; volume retained.' if args.stop else 'Knowledge database ready at 127.0.0.1:55433.')


if __name__ == '__main__':
    main()
