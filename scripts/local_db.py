"""Start an isolated development PostgreSQL cluster; never use the shared service."""

import argparse
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

from dotenv import dotenv_values
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DATA = LOCAL / "postgres"
ENV_FILE = ROOT / ".env"
PG_BIN = Path(os.environ.get("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))
PORT = 55432


def pg(tool: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    # A Windows daemon can inherit PIPE and keep communicate() waiting forever.
    # A file allows the launcher to exit independently of the database process.
    with tempfile.TemporaryFile(dir=LOCAL) as output:
        command = [str(PG_BIN / f"{tool}.exe"), *args]
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
        output.seek(0)
        text = output.read().decode("utf-8", errors="replace")
    if check and result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command, output=text)
    return subprocess.CompletedProcess(command, result.returncode, stdout=text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if not (PG_BIN / "pg_ctl.exe").exists():
        raise RuntimeError("PostgreSQL binaries not found. Set PG_BIN to the bin directory.")
    if args.stop:
        if DATA.exists() and pg("pg_ctl", "-D", str(DATA), "status", check=False).returncode == 0:
            pg("pg_ctl", "-D", str(DATA), "-m", "fast", "-w", "stop")
        print("Project database stopped; shared PostgreSQL service unchanged.")
        return

    LOCAL.mkdir(exist_ok=True)
    fresh = not DATA.exists()
    if fresh and ENV_FILE.exists():
        raise RuntimeError(".env already exists. Refusing to overwrite settings; see README.")
    if not fresh and not ENV_FILE.exists():
        raise RuntimeError("Partial setup detected: cluster exists without .env. No data removed.")

    admin_password = secrets.token_urlsafe(32)
    if fresh:
        password_file = LOCAL / "init-password.tmp"
        try:
            password_file.write_text(admin_password, encoding="utf-8")
            pg("initdb", "-D", str(DATA), "-U", "project_admin", "--encoding=UTF8",
               "--locale=C", "--auth=scram-sha-256", f"--pwfile={password_file}")
        finally:
            password_file.unlink(missing_ok=True)
        with (DATA / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\n")

    if pg("pg_ctl", "-D", str(DATA), "status", check=False).returncode != 0:
        pg("pg_ctl", "-D", str(DATA), "-l", str(LOCAL / "postgres.log"), "-w", "start")

    if fresh:
        app_password = secrets.token_urlsafe(32)
        with psycopg.connect(host="127.0.0.1", port=PORT, dbname="postgres",
                             user="project_admin", password=admin_password,
                             connect_timeout=3, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE ROLE provider_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Literal(app_password)))
            for database in ["provider_support", "provider_support_test"]:
                conn.execute(sql.SQL("CREATE DATABASE {} OWNER provider_app").format(sql.Identifier(database)))
        # Random token_urlsafe passwords are URL-safe; credentials are never printed.
        prefix = f"postgresql://provider_app:{app_password}@127.0.0.1:{PORT}/"
        ENV_FILE.write_text(f"DATABASE_URL={prefix}provider_support\nTEST_DATABASE_URL={prefix}provider_support_test\n", encoding="utf-8")

    values = dotenv_values(ENV_FILE)
    for key in ["DATABASE_URL", "TEST_DATABASE_URL"]:
        if not values.get(key):
            raise RuntimeError(f"Missing {key} in .env")
        with psycopg.connect(values[key], connect_timeout=3) as conn:
            conn.execute((ROOT / "backend" / "schema.sql").read_text(encoding="utf-8"))
    print(f"Project PostgreSQL ready on 127.0.0.1:{PORT}. Credentials saved locally in .env.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        # PostgreSQL command output here contains setup diagnostics, not connection strings.
        raise SystemExit(f"PostgreSQL setup failed:\n{exc.stdout}") from None
    except psycopg.Error:
        raise SystemExit("Database setup connection failed. Check .env and .local/postgres.log locally.") from None
