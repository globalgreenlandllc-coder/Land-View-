"""
crypto.py -- Authenticated encryption for secrets at rest (stdlib only).

The platform stores third-party API keys in the DB; they must not be readable from
a database dump. With no `cryptography` package available we use a correct
encrypt-then-MAC construction built on HMAC-SHA256:

  * A 32-byte master key is derived from a persisted secret (or $LANDVIEW_SECRET).
  * Two subkeys (encrypt, mac) are derived from it via HKDF-SHA256.
  * Keystream = HMAC-SHA256(enc_key, nonce || counter) blocks, XORed with plaintext
    (CTR-style stream cipher using HMAC as the PRF).
  * tag = HMAC-SHA256(mac_key, nonce || ciphertext); verified in constant time on
    decrypt BEFORE the ciphertext is used (encrypt-then-MAC).

Token format (urlsafe-b64):  v1 . nonce . ciphertext . tag
This is not a substitute for a KMS in production, but it keeps keys unreadable at
rest with no external dependency and a clean upgrade path.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

_SECRET_FILE = os.path.join(os.path.dirname(__file__), "_store", ".enc_secret")
_VERSION = "v1"


def _master() -> bytes:
    env = os.environ.get("LANDVIEW_SECRET")
    if env:
        return hashlib.sha256(env.encode()).digest()
    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE, "rb") as fh:
            return fh.read().strip()
    os.makedirs(os.path.dirname(_SECRET_FILE), exist_ok=True)
    key = secrets.token_bytes(32)
    fd = os.open(_SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def _hkdf(master: bytes, info: bytes, length: int = 32) -> bytes:
    # HKDF-Expand (SHA256) with a fixed all-zero salt extract; enough to split keys.
    prk = hmac.new(b"\x00" * 32, master, hashlib.sha256).digest()
    out, t, counter = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


def _keystream(enc_key: bytes, nonce: bytes, n: int) -> bytes:
    out, counter = b"", 0
    while len(out) < n:
        block = hmac.new(enc_key, nonce + counter.to_bytes(8, "big"),
                         hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:n]


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encrypt(plaintext: str) -> str:
    master = _master()
    enc_key = _hkdf(master, b"landview-enc")
    mac_key = _hkdf(master, b"landview-mac")
    nonce = secrets.token_bytes(16)
    data = plaintext.encode()
    ct = bytes(a ^ b for a, b in zip(data, _keystream(enc_key, nonce, len(data))))
    tag = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    return ".".join([_VERSION, _b64u(nonce), _b64u(ct), _b64u(tag)])


def decrypt(token: str) -> str:
    master = _master()
    enc_key = _hkdf(master, b"landview-enc")
    mac_key = _hkdf(master, b"landview-mac")
    ver, nonce_b, ct_b, tag_b = token.split(".")
    if ver != _VERSION:
        raise ValueError("unknown ciphertext version")
    nonce, ct, tag = _b64u_dec(nonce_b), _b64u_dec(ct_b), _b64u_dec(tag_b)
    expected = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("authentication failed (tampered or wrong key)")
    pt = bytes(a ^ b for a, b in zip(ct, _keystream(enc_key, nonce, len(ct))))
    return pt.decode()
