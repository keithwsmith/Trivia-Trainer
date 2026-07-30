"""SQLite connection helper.

Hardened slightly beyond the CLI-only version for use behind a web server
handling concurrent requests:
  - WAL journal mode lets reads proceed while a write is in progress
    (SQLite's default rollback-journal mode blocks readers during writes).
  - busy_timeout makes concurrent writers wait briefly and retry instead of
    immediately raising "database is locked".
  - check_same_thread=False because each request may be served by a
    different worker thread; a fresh connection is still opened per call
    (see get_connection() below), so no connection is ever shared across
    threads at the same time -- this just satisfies sqlite3's own check.
"""
import sqlite3
from config import Config


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.SQLITE_DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.row_factory = sqlite3.Row
    return conn


def run_schema_script(schema_path: str = "db/schema.sqlite.sql") -> None:
    """Executes schema.sqlite.sql against the configured SQLite file."""
    with open(schema_path, "r", encoding="utf-8") as f:
        script = f.read()

    conn = get_connection()
    try:
        conn.executescript(script)
        conn.commit()
        print(f"Schema applied to {Config.SQLITE_DB_PATH}.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_schema_script()
