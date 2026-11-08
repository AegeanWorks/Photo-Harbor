"""Per-person archive: hide a photo from the timeline without moving or copying it."""

from datetime import datetime
from typing import Callable

from .database import Database
from .store import local_now


class ArchiveBook:
    def __init__(self, db: Database, now: Callable[[], datetime] = local_now) -> None:
        self._db = db
        self._now = now

    def set(self, profile: str, sha256: str, archived: bool) -> bool:
        return self.set_many(profile, [sha256], archived) == 1

    def set_many(self, profile: str, sha256s: list, archived: bool) -> int:
        """Archive or restore several photos in one lock; returns how many rows changed."""
        if not sha256s:
            return 0
        with self._db.lock:
            if archived:
                at = self._now().isoformat(timespec="seconds")
                cursor = self._db.conn.executemany(
                    "INSERT OR IGNORE INTO archived (profile, sha256, archived_at)"
                    " VALUES (?, ?, ?)",
                    [(profile, sha256, at) for sha256 in sha256s])
            else:
                marks = ",".join("?" for _ in sha256s)
                cursor = self._db.conn.execute(
                    f"DELETE FROM archived WHERE profile = ? AND sha256 IN ({marks})",
                    (profile, *sha256s))
        return cursor.rowcount
