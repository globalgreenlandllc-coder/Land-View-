"""
db.py -- Tiny DB adapter so the same store.py code runs on:
  * PostgreSQL  when $DATABASE_URL is set (production / Vercel / any serverless),
  * SQLite      locally (no config needed).

It exposes the small slice of the sqlite3 interface store.py relies on:
    db = connect()
    db.execute("... ? ...", params).fetchone() / .fetchall() / .rowcount
    db.commit()
For Postgres, '?' placeholders are translated to '%s' and rows come back as
dicts (RealDictCursor), so row["col"] and dict(row) work the same as sqlite3.Row.
"""
from __future__ import annotations

import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL") or ""
IS_PG = DATABASE_URL.startswith("postgres")

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_store")
_SQLITE_PATH = os.path.join(_DIR, "landview.db")


class _Result:
    def __init__(self, cur):
        self._cur = cur
    def fetchone(self):
        return self._cur.fetchone()
    def fetchall(self):
        return self._cur.fetchall()
    @property
    def rowcount(self):
        return self._cur.rowcount


class _DB:
    def __init__(self):
        if IS_PG:
            import psycopg2
            import psycopg2.extras
            self._extras = psycopg2.extras
            self.conn = psycopg2.connect(DATABASE_URL)
            self.conn.autocommit = False
        else:
            os.makedirs(_DIR, exist_ok=True)
            self.conn = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        if IS_PG:
            cur = self.conn.cursor(cursor_factory=self._extras.RealDictCursor)
            cur.execute(sql.replace("?", "%s"), params)
            return _Result(cur)
        return _Result(self.conn.execute(sql, params))

    def commit(self):
        self.conn.commit()


def connect() -> _DB:
    return _DB()


def init_schema(db: _DB) -> None:
    serial = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    db.execute("""CREATE TABLE IF NOT EXISTS designs (
        id TEXT PRIMARY KEY, name TEXT, created_at TEXT, updated_at TEXT,
        json TEXT, user_id TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT,
        role TEXT NOT NULL DEFAULT 'user', status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS api_connections (
        service TEXT PRIMARY KEY, provider TEXT, endpoint TEXT,
        secret_enc TEXT, updated_at TEXT, updated_by TEXT)""")
    db.execute(f"""CREATE TABLE IF NOT EXISTS audit_log (
        id {serial}, ts TEXT, actor_id TEXT, actor_email TEXT,
        action TEXT, target TEXT, detail TEXT)""")
    # SQLite-only migration: older local DBs may lack designs.user_id.
    if not IS_PG:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(designs)").fetchall()}
        if "user_id" not in cols:
            db.execute("ALTER TABLE designs ADD COLUMN user_id TEXT")
    db.commit()
