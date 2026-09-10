"""
Password hashing and JWT issuing / verification.

Uses the `bcrypt` library directly rather than passlib: passlib 1.7.x trips over
bcrypt >= 4 (it reads the removed `bcrypt.__about__`), and we only need two
functions, so the extra abstraction buys nothing.
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _prehash(password: str) -> bytes:
    """
    bcrypt silently truncates anything past 72 bytes. Pre-hashing with SHA-256 and
    base64-encoding keeps the full entropy of long passphrases inside the limit.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: str, expires: timedelta, claims: Optional[Dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.resolved_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str, full_name: str = "") -> str:
    return _create_token(
        subject,
        TOKEN_TYPE_ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        {"role": role, "name": full_name},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject,
        TOKEN_TYPE_REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str = TOKEN_TYPE_ACCESS) -> Optional[Dict[str, Any]]:
    """Returns the claims, or None if the token is invalid, expired or the wrong type."""
    try:
        payload = jwt.decode(token, settings.resolved_jwt_secret(), algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload
