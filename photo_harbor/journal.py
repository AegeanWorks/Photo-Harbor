"""What the phone did and when: uploads, finished syncs and photos the PC lacked at cleanup."""

import re
from typing import Optional

from .database import Database

STORED = "stored"
DUPLICATE = "duplicate"
REJECTED = "rejected"
SYNC_DONE = "sync_done"
MISSING = "missing"
CHECKED = "checked"
DAMAGED = "damaged"
DAMAGE_LIMIT = 200


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

    def recent(self, limit: int = 100, profile: Optional[str] = None) -> list:
        """Newest journal events, for everyone or one person; old profile-less events are main."""
        mine = " WHERE COALESCE(profile, 'main') = ?" if profile else ""
        params = (profile, limit) if profile else (limit,)
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT at, kind, sha256, detail, COALESCE(profile, 'main')"
                f" FROM events{mine} ORDER BY id DESC LIMIT ?", params).fetchall()
        return [{"at": row[0], "kind": row[1], "sha256": row[2], "detail": row[3],
                 "profile": row[4]} for row in rows]

    def counts_since(self, since: str, profile: Optional[str] = None) -> dict:
        query = "SELECT kind, COUNT(*) FROM events WHERE at >= ? AND kind IN (?, ?, ?)"
        params = [since, STORED, DUPLICATE, REJECTED]
        if profile is not None:
            query += " AND COALESCE(profile, 'main') = ?"
            params.append(profile)
        with self._db.lock:
            rows = self._db.conn.execute(query + " GROUP BY kind", params).fetchall()
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

    def last_check(self) -> Optional[dict]:
        """The latest full file check summary, or None before the first real check."""
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT at, detail FROM events WHERE kind = ?"
                " AND detail LIKE '% checked, % damaged' ORDER BY id DESC LIMIT 1",
                (CHECKED,)).fetchone()
        if row is None:
            return None
        match = re.search(r"(\d+) checked, (\d+) damaged", row[1] or "")
        if match is None:
            return None
        return {"at": row[0], "checked": int(match.group(1)),
                "damaged": int(match.group(2))}

    def damaged(self, limit: int = DAMAGE_LIMIT) -> list:
        """Latest outstanding damage per path, newest first.

        Damage is outstanding only until the photo is stored again: a re-upload or a
        repaired copy records ``stored``/``duplicate`` after the damage event.
        """
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT d.detail, MAX(d.at) AS at, d.sha256 FROM events d"
                " WHERE d.kind = ? AND d.detail IS NOT NULL"
                " AND d.sha256 IN (SELECT sha256 FROM photos)"
                " AND NOT EXISTS (SELECT 1 FROM events r WHERE r.sha256 = d.sha256"
                " AND r.kind IN (?, ?) AND r.id > d.id)"
                " GROUP BY d.detail ORDER BY at DESC LIMIT ?",
                (DAMAGED, STORED, DUPLICATE, limit)).fetchall()
        return [{"path": row[0], "at": row[1], "sha256": row[2]} for row in rows]
