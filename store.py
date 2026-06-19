"""
store.py -- SQLite persistence for saved designs (no auth in this MVP; add
accounts later). A design is the full editable state: address/property, style,
vision, elements, lighting.
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
        _conn.commit()
    return _conn


def save_design(payload: dict) -> dict:
    with _lock:
        c = _db()
        did = payload.get("id") or secrets.token_urlsafe(8)
        row = c.execute("SELECT created_at FROM designs WHERE id=?", (did,)).fetchone()
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
        }
        c.execute("INSERT OR REPLACE INTO designs(id,name,created_at,updated_at,json) VALUES (?,?,?,?,?)",
                  (did, rec["name"], created, rec["updated_at"], json.dumps(rec, default=str)))
        c.commit()
        return rec


def list_designs() -> list:
    rows = _db().execute("SELECT json FROM designs ORDER BY updated_at DESC").fetchall()
    out = []
    for r in rows:
        d = json.loads(r["json"])
        out.append({"id": d["id"], "name": d["name"], "address": d.get("address", ""),
                    "style": d.get("style"), "updated_at": d["updated_at"],
                    "elements": len(d.get("elements", []))})
    return out


def get_design(did: str):
    row = _db().execute("SELECT json FROM designs WHERE id=?", (did,)).fetchone()
    return json.loads(row["json"]) if row else None


def delete_design(did: str) -> bool:
    with _lock:
        c = _db()
        cur = c.execute("DELETE FROM designs WHERE id=?", (did,))
        c.commit()
        return cur.rowcount > 0
