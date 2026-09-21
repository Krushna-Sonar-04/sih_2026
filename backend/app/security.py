"""Local authentication primitives.

Deliberately dependency-free: PBKDF2-HMAC-SHA256 password hashing and HS256
JSON Web Tokens implemented against the standard library, so the prototype
runs offline on a Windows workstation without extra native wheels.

No password is ever stored or logged in plaintext.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

PBKDF2_ROUNDS = 240_000
ROLES = ("analyst", "lead_analyst", "admin")
ROLE_RANK = {"analyst": 1, "lead_analyst": 2, "admin": 3}


# --------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_b64, digest_b64 = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(rounds)
        )
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except Exception:
        return False


# --------------------------------------------------------------------------- tokens
def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(subject: str, role: str, secret: str, expires_minutes: int = 720) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload = _b64url(
        json.dumps(
            {"sub": subject, "role": role, "iat": now, "exp": now + expires_minutes * 60},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    signature = _b64url(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token: str, secret: str) -> dict[str, Any] | None:
    """Return the claims when the signature and expiry are valid, else None."""
    try:
        header, payload, signature = token.split(".")
        expected = _b64url(
            hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, signature):
            return None
        claims = json.loads(_b64url_decode(payload))
        if int(claims.get("exp", 0)) < int(time.time()):
            return None
        return claims
    except Exception:
        return None


def role_allows(role: str, required: str) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(required, 99)


def random_secret(length: int = 48) -> str:
    return secrets.token_urlsafe(length)
