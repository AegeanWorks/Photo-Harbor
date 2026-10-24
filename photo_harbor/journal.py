"""What the phone did and when: uploads, finished syncs and photos the PC lacked at cleanup."""

from typing import Optional

from .database import Database

STORED = "stored"
DUPLICATE = "duplicate"
REJECTED = "rejected"
SYNC_DONE = "sync_done"
MISSING = "missing"


class SyncJournal:
    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, at: str, kind: str, sha256: Optional[str] = None,
               detail: Optional[str] = None) -> None:
        with self._db.lock:
            self._db.conn.execute(
                "INSERT INTO events (at, kind, sha256, detail) VALUES (?, ?, ?, ?)",
                (at, kind, sha256, detail),
            )

    def last_sync(self) -> Optional[str]:
        """The phone-reported start time of the latest sync that finished."""
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT detail FROM events WHERE kind = ? ORDER BY id DESC LIMIT 1", (SYNC_DONE,)
            ).fetchone()
        return row[0] if row else None

    def counts_since(self, since: str) -> dict:
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT kind, COUNT(*) FROM events WHERE at >= ? AND kind IN (?, ?, ?)"
                " GROUP BY kind",
                (since, STORED, DUPLICATE, REJECTED),
            ).fetchall()
        counts = {STORED: 0, DUPLICATE: 0, REJECTED: 0}
        counts.update({row[0]: row[1] for row in rows})
        return counts

    def missing(self, limit: int = 200) -> list:
        """Photos the phone holds that the PC still lacks, newest report first."""
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT sha256, MAX(at) AS at, detail FROM events"
                " WHERE kind = ? AND sha256 NOT IN (SELECT sha256 FROM photos)"
                " GROUP BY sha256 ORDER BY at DESC LIMIT ?",
                (MISSING, limit),
            ).fetchall()
        return [{"sha256": row[0], "reported_at": row[1], "name": row[2]} for row in rows]
