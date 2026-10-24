"""Signing in with a name and a password: password hashes, sessions, and a brake on guessing."""

import base64
import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from .database import Database
from .errors import HarborError

ITERATIONS = 240_000
MIN_PASSWORD = 6
MAX_PASSWORD = 200
SESSION_DAYS = 365
MAX_FAILURES = 5
LOCKOUT_SECONDS = 300


def hash_password(password: str, iterations: int = ITERATIONS, salt: Optional[bytes] = None) -> str:
    """``pbkdf2_sha256$<iterations>$<salt>$<hash>``: the password itself is never stored."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    encode = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"pbkdf2_sha256${iterations}${encode(salt)}${encode(digest)}"


def password_matches(password: str, stored: Optional[str]) -> bool:
    try:
        scheme, iterations, salt, expected = (stored or "").split("$")
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    candidate = hash_password(password, int(iterations), base64.b64decode(salt))
    return hmac.compare_digest(candidate.split("$")[3], expected)


def check_new_password(password: str) -> str:
    if not isinstance(password, str) or not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise HarborError("that password is too short" if isinstance(password, str)
                          and len(password) < MIN_PASSWORD else "that password is not usable",
                          f"passwords are {MIN_PASSWORD} to {MAX_PASSWORD} characters",
                          f"choose one of at least {MIN_PASSWORD} characters")
    return password


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class Passwords:
    def __init__(self, db: Database, iterations: int = ITERATIONS) -> None:
        self._db = db
        self._iterations = iterations

    def has_password(self, profile: str) -> bool:
        with self._db.lock:
            row = self._db.conn.execute("SELECT password_hash FROM profiles WHERE id = ?",
                                        (profile,)).fetchone()
        return bool(row and row[0])

    def set(self, profile: str, password: str) -> None:
        stored = hash_password(check_new_password(password), self._iterations)
        with self._db.lock:
            self._db.conn.execute("UPDATE profiles SET password_hash = ? WHERE id = ?",
                                  (stored, profile))

    def matches(self, profile: str, password: str) -> bool:
        with self._db.lock:
            row = self._db.conn.execute("SELECT password_hash FROM profiles WHERE id = ?",
                                        (profile,)).fetchone()
        return bool(row) and password_matches(password, row[0])


class Sessions:
    """A signed-in browser holds a random token; only its SHA-256 is stored."""

    def __init__(self, db: Database,
                 now: Callable[[], datetime] = lambda: datetime.now().astimezone()) -> None:
        self._db = db
        self._now = now

    def start(self, profile: str) -> str:
        token = secrets.token_urlsafe(32)  # aikit:allow-secret generated at runtime
        now = self._now()
        with self._db.lock:
            self._db.conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_stamp(now),))
            self._db.conn.execute(
                "INSERT INTO sessions (token_hash, profile, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (_token_hash(token), profile, _stamp(now), _stamp(now + timedelta(days=SESSION_DAYS))))
        return token

    def find(self, token: str) -> Optional[str]:
        if not token:
            return None
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT profile FROM sessions WHERE token_hash = ? AND expires_at > ?",
                (_token_hash(token), _stamp(self._now()))).fetchone()
        return row[0] if row else None

    def close(self, token: Optional[str] = None, profile: Optional[str] = None,
              keep: Optional[str] = None) -> None:
        """End one session (``token``), or all of ``profile``'s except ``keep``."""
        with self._db.lock:
            if token:
                self._db.conn.execute("DELETE FROM sessions WHERE token_hash = ?",
                                      (_token_hash(token),))
            if profile:
                self._db.conn.execute(
                    "DELETE FROM sessions WHERE profile = ? AND token_hash != ?",
                    (profile, _token_hash(keep) if keep else ""))


class LoginBrake:
    """After 5 wrong passwords from one address, that address waits 5 minutes."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures: dict = {}
        self._lock = threading.Lock()

    def check(self, address: str) -> None:
        with self._lock:
            count, since = self._failures.get(address, (0, 0.0))
            if count >= MAX_FAILURES and self._clock() - since < LOCKOUT_SECONDS:
                wait = int(LOCKOUT_SECONDS - (self._clock() - since)) + 1
                raise HarborError("too many wrong passwords", f"try again in {wait} seconds",
                                  "wait, or ask the main profile to set a new password", status=429)
            if count >= MAX_FAILURES:
                self._failures.pop(address, None)

    def failed(self, address: str) -> None:
        with self._lock:
            count, _ = self._failures.get(address, (0, 0.0))
            self._failures[address] = (count + 1, self._clock())

    def passed(self, address: str) -> None:
        with self._lock:
            self._failures.pop(address, None)
