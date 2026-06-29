"""
auth.py -- Authentication for Land-View, stdlib-only (no extra packages).

  * Passwords hashed with scrypt (salted, constant-time verify).
  * JWT (HS256) access + refresh tokens, signed with a server secret.
  * Flask guards: @require_auth and @require_admin set flask.g.user.

The signing secret comes from $JWT_SECRET; if unset, a random secret is generated
once and persisted to _store/.jwt_secret so tokens survive restarts in dev.
Set JWT_SECRET in the environment (or admin panel later) for production.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from functools import wraps

from flask import g, jsonify, request

import store

ACCESS_TTL = 30 * 60            # 30 minutes
REFRESH_TTL = 30 * 24 * 60 * 60  # 30 days

_SECRET_FILE = os.path.join(os.path.dirname(__file__), "_store", ".jwt_secret")
_cached_secret = None


def _secret() -> bytes:
    """Signing key: $JWT_SECRET first (required on serverless), else a local file.
    File I/O is best-effort so a read-only filesystem never crashes auth; set
    JWT_SECRET in production so tokens stay valid across restarts/instances."""
    global _cached_secret
    env = os.environ.get("JWT_SECRET")
    if env:
        return env.encode()
    if _cached_secret:
        return _cached_secret
    try:
        if os.path.exists(_SECRET_FILE):
            with open(_SECRET_FILE, "rb") as fh:
                _cached_secret = fh.read().strip()
                return _cached_secret
    except OSError:
        pass
    s = secrets.token_urlsafe(48).encode()
    try:
        os.makedirs(os.path.dirname(_SECRET_FILE), exist_ok=True)
        fd = os.open(_SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(s)
    except OSError:
        pass  # read-only FS (serverless) — use the in-process value
    _cached_secret = s
    return _cached_secret


# ---------------------------------------------------------------------------
# base64url helpers
# ---------------------------------------------------------------------------

def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------------------------------------------------------------------------
# Passwords (scrypt)
# ---------------------------------------------------------------------------

_PBKDF2_ITERS = 240_000  # OWASP-recommended floor for PBKDF2-HMAC-SHA256


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, _PBKDF2_ITERS, dklen=32)
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${_b64u(salt)}${_b64u(dk)}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_b, dk_b = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt, dk = _b64u_dec(salt_b), _b64u_dec(dk_b)
        test = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, int(iters_s), dklen=len(dk))
        return hmac.compare_digest(test, dk)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT (HS256)
# ---------------------------------------------------------------------------

def _make_token(sub: str, role: str, kind: str, ttl: int) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": sub, "role": role, "kind": kind, "iat": now, "exp": now + ttl}
    seg = (_b64u(json.dumps(header, separators=(",", ":")).encode()) + "." +
           _b64u(json.dumps(payload, separators=(",", ":")).encode()))
    sig = hmac.new(_secret(), seg.encode(), hashlib.sha256).digest()
    return seg + "." + _b64u(sig)


def verify_token(tok: str, kind: str | None = None):
    try:
        seg, sig_b = tok.rsplit(".", 1)
        expected = hmac.new(_secret(), seg.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64u_dec(sig_b), expected):
            return None
        payload = json.loads(_b64u_dec(seg.split(".", 1)[1]))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if kind and payload.get("kind") != kind:
            return None
        return payload
    except Exception:
        return None


def issue_tokens(user_id: str, role: str) -> dict:
    return {
        "access_token": _make_token(user_id, role, "access", ACCESS_TTL),
        "refresh_token": _make_token(user_id, role, "refresh", REFRESH_TTL),
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL,
    }


# ---------------------------------------------------------------------------
# Flask guards
# ---------------------------------------------------------------------------

def _current_user():
    auth = request.headers.get("Authorization", "")
    tok = auth[7:].strip() if auth.startswith("Bearer ") else ""
    payload = verify_token(tok, kind="access")
    if not payload:
        return None
    row = store.get_user_by_id(payload["sub"])
    if row is None or row["status"] != "active":
        return None
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401
        g.user = user
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401
        if user["role"] != "admin":
            return jsonify({"error": "forbidden"}), 403
        g.user = user
        return fn(*args, **kwargs)
    return wrapper
