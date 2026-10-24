"""The index of stored originals, keyed by SHA-256."""

import sqlite3
from typing import Optional

from .database import Database
from .records import LibraryStats, Outline, PhotoFilter, PhotoRecord

_COLUMNS = "sha256, rel_path, size, original_name, media_type, taken_at, received_at"


def _to_record(row: sqlite3.Row) -> PhotoRecord:
    return PhotoRecord(**dict(row))


def _where(narrow: PhotoFilter) -> tuple:
    clauses, params = [], []
    if narrow.month:
        clauses.append("substr(sort_time, 1, 7) = ?")
        params.append(narrow.month)
    if narrow.query:
        escaped = narrow.query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        clauses.append("original_name LIKE ? ESCAPE '!'")
        params.append(f"%{escaped}%")
    if narrow.kind == "video":
        clauses.append("media_type LIKE 'video/%'")
    elif narrow.kind == "photo":
        clauses.append("media_type NOT LIKE 'video/%'")
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


class Catalog:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, record: PhotoRecord) -> bool:
        """Insert ``record``; False when its hash is already catalogued. A path another record
        holds raises ``sqlite3.IntegrityError`` so the caller can pick another name."""
        with self._db.lock:
            try:
                self._db.conn.execute(
                    f"INSERT INTO photos ({_COLUMNS}, sort_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.sha256, record.rel_path, record.size, record.original_name,
                     record.media_type, record.taken_at, record.received_at, record.sort_time),
                )
            except sqlite3.IntegrityError as exc:
                if "rel_path" in str(exc):
                    raise
                return False
        return True

    def get(self, sha256: str) -> Optional[PhotoRecord]:
        with self._db.lock:
            row = self._db.conn.execute(
                f"SELECT {_COLUMNS} FROM photos WHERE sha256 = ?", (sha256,)
            ).fetchone()
        return _to_record(row) if row else None

    def page(self, offset: int, limit: int, narrow: PhotoFilter = PhotoFilter()) -> list:
        """Records newest first by taken time, falling back to received time."""
        where, params = _where(narrow)
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT {_COLUMNS} FROM photos{where} ORDER BY sort_time DESC, sha256 DESC"
                " LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_to_record(row) for row in rows]

    def outline(self) -> Outline:
        with self._db.lock:
            months = self._db.conn.execute(
                "SELECT substr(sort_time, 1, 7) AS month, COUNT(*) FROM photos"
                " GROUP BY month ORDER BY month DESC"
            ).fetchall()
            videos = self._db.conn.execute(
                "SELECT COUNT(*) FROM photos WHERE media_type LIKE 'video/%'"
            ).fetchone()[0]
        return Outline(months=tuple((row[0], row[1]) for row in months), videos=videos)

    def stats(self) -> LibraryStats:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(size), 0), MAX(received_at) FROM photos"
            ).fetchone()
        return LibraryStats(count=row[0], total_bytes=row[1], last_received=row[2])
