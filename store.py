"""
store.py -- SQLite persistence for users and saved designs. Designs are owned by
a user (user_id) and scoped per-account. A design is the full editable state:
address/property, style, vision, elements, lighting.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone

_DIR = os.path.join(os.path.dirname(__file__), "_store")
_DB = os.path.join(_DIR, "landview.db")
_lock = threading.Lock()
_conn = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(_DIR, exist_ok=True)
        _conn = sqlite3.connect(_DB, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("""CREATE TABLE IF NOT EXISTS designs (
            id TEXT PRIMARY KEY, name TEXT, created_at TEXT, updated_at TEXT, json TEXT)""")
        _conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT,
            role TEXT NOT NULL DEFAULT 'user', status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT)""")
        _conn.execute("""CREATE TABLE IF NOT EXISTS api_connections (
            service TEXT PRIMARY KEY, provider TEXT, endpoint TEXT,
            secret_enc TEXT, updated_at TEXT, updated_by TEXT)""")
        _conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor_id TEXT,
            actor_email TEXT, action TEXT, target TEXT, detail TEXT)""")
        # Migration: older DBs have a designs table without user_id — add it once.
        cols = {r["name"] for r in _conn.execute("PRAGMA table_info(designs)").fetchall()}
        if "user_id" not in cols:
            _conn.execute("ALTER TABLE designs ADD COLUMN user_id TEXT")
        _conn.commit()
    return _conn


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def _user_public(row) -> dict:
    return {"id": row["id"], "email": row["email"], "role": row["role"],
            "status": row["status"], "created_at": row["created_at"]}


def count_users() -> int:
    return _db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def create_user(email: str, password_hash: str, role: str = "user") -> dict:
    with _lock:
        c = _db()
        uid = secrets.token_urlsafe(9)
        c.execute("INSERT INTO users(id,email,password_hash,role,status,created_at) "
                  "VALUES (?,?,?,?,?,?)",
                  (uid, email.lower().strip(), password_hash, role, "active", _now()))
        c.commit()
        return _user_public(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())


def get_user_by_email(email: str):
    return _db().execute("SELECT * FROM users WHERE email=?",
                         (email.lower().strip(),)).fetchone()


def get_user_by_id(uid: str):
    return _db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def list_users() -> list:
    rows = _db().execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [_user_public(r) for r in rows]


def set_user_status(uid: str, status: str) -> bool:
    with _lock:
        c = _db()
        cur = c.execute("UPDATE users SET status=? WHERE id=?", (status, uid))
        c.commit()
        return cur.rowcount > 0


def set_user_role(uid: str, role: str) -> bool:
    with _lock:
        c = _db()
        cur = c.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
        c.commit()
        return cur.rowcount > 0


def delete_user(uid: str) -> bool:
    with _lock:
        c = _db()
        c.execute("DELETE FROM designs WHERE user_id=?", (uid,))
        cur = c.execute("DELETE FROM users WHERE id=?", (uid,))
        c.commit()
        return cur.rowcount > 0


def save_design(payload: dict, user_id: str) -> dict:
    with _lock:
        c = _db()
        did = payload.get("id") or secrets.token_urlsafe(8)
        # Owner check: a user may only overwrite their own design (or create new).
        row = c.execute("SELECT created_at, user_id FROM designs WHERE id=?", (did,)).fetchone()
        if row is not None and row["user_id"] not in (None, user_id):
            raise PermissionError("not your design")
        created = row["created_at"] if row else _now()
        rec = {
            "id": did,
            "name": payload.get("name") or "Untitled design",
            "created_at": created, "updated_at": _now(),
            "address": payload.get("address", ""),
            "property": payload.get("property"),
            "style": payload.get("style", "modern"),
            "vision": payload.get("vision", ""),
            "elements": payload.get("elements", []),
            "time_of_day": payload.get("time_of_day", "day"),
            "view": payload.get("view", "hero"),
        }
        c.execute("INSERT OR REPLACE INTO designs(id,name,created_at,updated_at,json,user_id) "
                  "VALUES (?,?,?,?,?,?)",
                  (did, rec["name"], created, rec["updated_at"],
                   json.dumps(rec, default=str), user_id))
        c.commit()
        return rec


def list_designs(user_id: str) -> list:
    rows = _db().execute(
        "SELECT json FROM designs WHERE user_id=? ORDER BY updated_at DESC",
        (user_id,)).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["json"])
        out.append({"id": d["id"], "name": d["name"], "address": d.get("address", ""),
                    "style": d.get("style"), "updated_at": d["updated_at"],
                    "elements": len(d.get("elements", []))})
    return out


def get_design(did: str, user_id: str):
    row = _db().execute("SELECT json FROM designs WHERE id=? AND user_id=?",
                        (did, user_id)).fetchone()
    return json.loads(row["json"]) if row else None


def delete_design(did: str, user_id: str) -> bool:
    with _lock:
        c = _db()
        cur = c.execute("DELETE FROM designs WHERE id=? AND user_id=?", (did, user_id))
        c.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# API connections (encrypted secret stored as secret_enc)
# ---------------------------------------------------------------------------

def upsert_connection(service: str, provider: str, endpoint: str,
                      secret_enc: str | None, updated_by: str) -> None:
    with _lock:
        c = _db()
        # Keep the existing secret if the caller didn't supply a new one.
        if secret_enc is None:
            row = c.execute("SELECT secret_enc FROM api_connections WHERE service=?",
                            (service,)).fetchone()
            secret_enc = row["secret_enc"] if row else None
        c.execute(
            "INSERT INTO api_connections(service,provider,endpoint,secret_enc,updated_at,updated_by) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(service) DO UPDATE SET "
            "provider=excluded.provider, endpoint=excluded.endpoint, "
            "secret_enc=excluded.secret_enc, updated_at=excluded.updated_at, "
            "updated_by=excluded.updated_by",
            (service, provider, endpoint, secret_enc, _now(), updated_by))
        c.commit()


def get_connection(service: str):
    return _db().execute("SELECT * FROM api_connections WHERE service=?",
                         (service,)).fetchone()


def list_connections() -> list:
    return _db().execute("SELECT * FROM api_connections ORDER BY service").fetchall()


def delete_connection(service: str) -> bool:
    with _lock:
        c = _db()
        cur = c.execute("DELETE FROM api_connections WHERE service=?", (service,))
        c.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def add_audit(actor_id: str, actor_email: str, action: str,
              target: str = "", detail: str = "") -> None:
    with _lock:
        c = _db()
        c.execute("INSERT INTO audit_log(ts,actor_id,actor_email,action,target,detail) "
                  "VALUES (?,?,?,?,?,?)",
                  (_now(), actor_id, actor_email, action, target, detail))
        c.commit()


def list_audit(limit: int = 200) -> list:
    rows = _db().execute(
        "SELECT ts,actor_email,action,target,detail FROM audit_log "
        "ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return [dict(r) for r in rows]


def count_action(action: str) -> int:
    return _db().execute("SELECT COUNT(*) AS n FROM audit_log WHERE action=?",
                         (action,)).fetchone()["n"]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def analytics() -> dict:
    c = _db()
    users_total = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    users_active = c.execute("SELECT COUNT(*) AS n FROM users WHERE status='active'").fetchone()["n"]
    admins = c.execute("SELECT COUNT(*) AS n FROM users WHERE role='admin'").fetchone()["n"]
    designs_total = c.execute("SELECT COUNT(*) AS n FROM designs").fetchone()["n"]
    return {
        "users_total": users_total,
        "users_active": users_active,
        "users_suspended": users_total - users_active,
        "admins": admins,
        "designs_total": designs_total,
        "searches": count_action("search"),
        "renders": count_action("render"),
        "logins": count_action("login"),
    }
