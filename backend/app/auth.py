"""
Request authentication helpers — deliberately free of FastAPI imports so the
logic is unit-testable without the web stack (main.py stays a thin adapter).

What changed versus the original login code, and why:
  * Tokens are persisted (hashed) with an expiry in db.auth_sessions instead
    of an in-process dict, so they survive restarts and a copy of the
    database is not a set of live sessions.
  * The caller's identity is ALWAYS derived server-side from the
    `Authorization: Bearer <token>` header. A user_id supplied by the client
    is never trusted; if present it must match the token's user or the
    request is refused. Previously any client could read/delete another
    user's chat history by sending a different user_id.
  * Sign-in / sign-up attempts are rate-limited (in-process; adequate for a
    single-instance deployment, and honestly labeled as such — a multi-
    instance deployment would need a shared store).
"""
import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from . import db

AUTH_MAX_ATTEMPTS = int(os.getenv("SUTRADHARA_AUTH_MAX_ATTEMPTS", "8"))
AUTH_WINDOW_SECONDS = int(os.getenv("SUTRADHARA_AUTH_WINDOW_SECONDS", "300"))


class RateLimiter:
    """Sliding-window limiter keyed by an arbitrary string (IP, email...)."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max_attempts:
            return False
        q.append(now)
        return True

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


login_limiter = RateLimiter(AUTH_MAX_ATTEMPTS, AUTH_WINDOW_SECONDS)


def parse_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def resolve_user(authorization: Optional[str]) -> Optional[dict]:
    """Authorization header -> user dict, or None (missing/invalid/expired)."""
    return db.get_user_by_token(parse_bearer(authorization))


def check_claimed_user(user: dict, claimed_user_id: Optional[int]) -> bool:
    """A client-supplied user_id is only ever cross-checked, never trusted."""
    return claimed_user_id is None or int(claimed_user_id) == int(user["id"])
