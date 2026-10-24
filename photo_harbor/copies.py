"""Whose folder holds which photo. One file can sit in several people's folders (hard links)."""

import sqlite3
from typing import Optional

from .database import Database
from .records import PhotoRecord


class CopyIndex:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, profile: str, photo: PhotoRecord, rel_path: str, original_name: str,
            added_at: str) -> bool:
        """Record ``profile``'s copy of ``photo``; False when that person already has it."""
        with self._db.lock:
            cursor = self._db.conn.execute(
                "INSERT OR IGNORE INTO copies (profile, sha256, rel_path, original_name, added_at,"
                " sort_time, size, is_video) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (profile, photo.sha256, rel_path, original_name, added_at, photo.sort_time,
                 photo.size, int(photo.is_video)))
        return cursor.rowcount == 1

    def path_for(self, profile: str, sha256: str) -> Optional[str]:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT rel_path FROM copies WHERE profile = ? AND sha256 = ?", (profile, sha256)
            ).fetchone()
        return row[0] if row else None

    def paths_of(self, sha256: str) -> list:
        """``[(profile, rel_path), ...]`` for every copy of one photo, oldest first."""
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT profile, rel_path FROM copies WHERE sha256 = ? ORDER BY added_at",
                (sha256,)).fetchall()
        return [(row[0], row[1]) for row in rows]

    def move(self, old: str, new: str) -> None:
        """A file moved inside the library (reorganised, renamed folder, moved in Explorer)."""
        with self._db.lock:
            self._db.conn.execute("UPDATE copies SET rel_path = ? WHERE rel_path = ?", (new, old))
            self._db.conn.execute("UPDATE photos SET rel_path = ? WHERE rel_path = ?", (new, old))

    def forget(self, profile: str, sha256: str) -> bool:
        """Drop one person's copy (they deleted the file). True when no copy is left anywhere, in
        which case the photo itself leaves the catalog; otherwise another copy becomes primary."""
        with self._db.lock:
            self._db.conn.execute("SAVEPOINT forget_copy")
            try:
                self._db.conn.execute("DELETE FROM copies WHERE profile = ? AND sha256 = ?",
                                      (profile, sha256))
                left = self._db.conn.execute(
                    "SELECT rel_path, profile FROM copies WHERE sha256 = ? ORDER BY added_at"
                    " LIMIT 1", (sha256,)).fetchone()
                if left is None:
                    self._db.conn.execute("DELETE FROM photos WHERE sha256 = ?", (sha256,))
                else:
                    self._db.conn.execute(
                        "UPDATE photos SET rel_path = ?, profile = ? WHERE sha256 = ?",
                        (left[0], left[1], sha256))
            except sqlite3.Error:
                self._db.conn.execute("ROLLBACK TO forget_copy")
                self._db.conn.execute("RELEASE forget_copy")
                raise
            self._db.conn.execute("RELEASE forget_copy")
        return left is None
