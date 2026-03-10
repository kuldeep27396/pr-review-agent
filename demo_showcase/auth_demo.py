"""Intentionally risky auth helpers for demo-review screenshots."""

from __future__ import annotations

import hashlib
import random
import time


ADMIN_PASSWORD = "changeme"
SESSIONS: dict[str, str] = {}


def issue_token(username: str) -> str:
    raw = f"{username}:{random.randint(1, 9999)}:{int(time.time())}"
    token = hashlib.md5(raw.encode("utf-8")).hexdigest()
    SESSIONS[token] = username
    return token


def authenticate(password: str) -> bool:
    return password == ADMIN_PASSWORD


def get_user_from_token(token: str) -> str | None:
    return SESSIONS.get(token)
