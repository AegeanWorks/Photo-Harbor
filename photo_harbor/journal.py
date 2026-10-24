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
               detail: Optional[str] = None, profile: Optional[str] = None) -> None:
        with self._db.lock:
            self._db.conn.execute(
                "INSERT INTO events (at, kind, sha256, detail, profile) VALUES (?, ?, ?, ?, ?)",
                (at, kind, sha256, detail, profile),
            )

    def last_sync(self, profile: Optional[str] = None) -> Optional[str]:
        """The start time of the latest finished sync, for one profile or (None) anyone.
        Format-1 events carry no profile and count as the owner's."""
        query = "SELECT detail FROM events WHERE kind = ?"
        params = [SYNC_DONE]
        if profile is not None:
            query += " AND COALESCE(profile, 'main') = ?"
            params.append(profile)
        with self._db.lock:
            row = self._db.conn.execute(query + " ORDER BY id DESC LIMIT 1", params).fetchone()
        return row[0] if row else None

    def last_event(self, kind: str) -> Optional[str]:
        """When the latest event of ``kind`` was recorded."""
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT at FROM events WHERE kind = ? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
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

    def missing(self, limit: int = 200, profile: Optional[str] = None) -> list:
        """Photos a phone holds that the PC still lacks, newest report first; one person's
        reports only when ``profile`` is given."""
        mine = " AND COALESCE(profile, 'main') = ?" if profile else ""
        params = (MISSING, profile, limit) if profile else (MISSING, limit)
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT sha256, MAX(at) AS at, detail FROM events"
                f" WHERE kind = ?{mine} AND sha256 NOT IN (SELECT sha256 FROM photos)"
                " GROUP BY sha256 ORDER BY at DESC LIMIT ?", params,
            ).fetchall()
        return [{"sha256": row[0], "reported_at": row[1], "name": row[2]} for row in rows]
