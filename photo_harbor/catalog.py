"""The index of stored originals: one row per distinct file, keyed by SHA-256."""

import sqlite3
from typing import Optional

from .database import Database, MAX_ROW_ID
from .records import (LibraryStats, Outline, PersonStorage, PhotoFilter, PhotoRecord,
                      StorageFile, StorageReport)

_COLUMNS = ("sha256, rel_path, size, original_name, media_type, taken_at, received_at,"
            " profile, latitude, longitude, camera, lens")
_ORDERS = {
    "newest": "{owner}.sort_time DESC, {owner}.sha256 DESC",
    "oldest": "{owner}.sort_time ASC, {owner}.sha256 ASC",
    "largest": "{owner}.size DESC, {owner}.sort_time DESC, {owner}.sha256 DESC",
    "smallest": "{owner}.size ASC, {owner}.sort_time ASC, {owner}.sha256 ASC",
}


def _to_record(row: sqlite3.Row) -> PhotoRecord:
    values = dict(row)
    if "favorite" in values:
        values["favorite"] = bool(values["favorite"])
    return PhotoRecord(**values)


def _source(narrow: PhotoFilter) -> tuple:
    """``(FROM clause, columns, alias of the owner side)``. One person's view reads their own
    copies (their file name and folder); everyone's view reads one row per distinct file."""
    if narrow.profile:
        owner = "c"
        # A name search matches few rows: scan this person's copies and sort the matches.
        copies = "copies c NOT INDEXED" if narrow.query else "copies c"
        table = f"{copies} JOIN photos p ON p.sha256 = c.sha256"
    else:
        owner = "p"
        # A name search matches few rows: scanning and sorting them beats walking the date index.
        table = "photos p NOT INDEXED" if narrow.query else "photos p"
    columns = (f"p.sha256, {owner}.rel_path, p.size, {owner}.original_name, p.media_type,"
               f" p.taken_at, p.received_at, {owner}.profile")
    return table, columns, owner


def _where(narrow: PhotoFilter, owner: str) -> tuple:
    clauses, params = [], []
    if narrow.profile:
        clauses.append("c.profile = ?")
        params.append(narrow.profile)
    if narrow.month:
        clauses.append(f"substr({owner}.sort_time, 1, 7) = ?")
        params.append(narrow.month)
    if narrow.start:
        clauses.append(f"substr({owner}.sort_time, 1, 10) >= ?")
        params.append(narrow.start)
    if narrow.end:
        clauses.append(f"substr({owner}.sort_time, 1, 10) <= ?")
        params.append(narrow.end)
    if narrow.day:
        clauses.append(f"substr({owner}.sort_time, 6, 5) = ?")
        params.append(narrow.day)
    if narrow.archived:
        clauses.append("EXISTS (SELECT 1 FROM archived ar"
                       " WHERE ar.profile = ? AND ar.sha256 = p.sha256)")
    else:
        clauses.append("NOT EXISTS (SELECT 1 FROM archived ar"
                       " WHERE ar.profile = ? AND ar.sha256 = p.sha256)")
    params.append(narrow.viewer)
    for term in narrow.query.split() if narrow.query else ():
        escaped = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        clauses.append(f"{owner}.original_name LIKE ? ESCAPE '!'")
        params.append(f"%{escaped}%")
    if narrow.kind is not None and narrow.kind not in ("video", "photo"):
        raise ValueError(f"kind must be 'photo', 'video' or None, got {narrow.kind!r}")
    if narrow.kind in ("video", "photo"):
        wanted = "=" if narrow.kind == "video" else "!="
        clauses.append(f"c.is_video {wanted} 1" if owner == "c" else
                       f"p.media_type {'' if wanted == '=' else 'NOT '}LIKE 'video/%'")
    if narrow.favorite:
        clauses.append("EXISTS (SELECT 1 FROM favorites f"
                       " WHERE f.profile = ? AND f.sha256 = p.sha256)")
        params.append(narrow.viewer)
    if narrow.album is not None:
        clauses.append("EXISTS (SELECT 1 FROM album_photos a JOIN albums al ON al.id = a.album_id"
                       " WHERE a.album_id = ? AND al.profile = ? AND a.sha256 = p.sha256)")
        params.extend((narrow.album, narrow.viewer))
    if narrow.tag is not None:
        clauses.append("EXISTS (SELECT 1 FROM photo_tags pt JOIN tags t ON t.id = pt.tag_id"
                       " WHERE pt.tag_id = ? AND t.profile = ? AND pt.sha256 = p.sha256)")
        params.extend((narrow.tag, narrow.viewer))
    if narrow.place is not None:
        clauses.append("p.latitude IS NOT NULL AND p.longitude IS NOT NULL"
                       " AND ROUND(p.latitude, 1) = ? AND ROUND(p.longitude, 1) = ?")
        params.extend(narrow.place)
    if narrow.camera:
        clauses.append("p.camera = ?")
        params.append(narrow.camera)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def _totals_source(profile: Optional[str]) -> tuple:
    if profile:
        return "copies c", " WHERE c.profile = ?", [profile]
    return "photos p", "", []


class Catalog:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, record: PhotoRecord) -> bool:
        """Insert ``record``; False when its hash is already catalogued. A path another record
        holds raises ``sqlite3.IntegrityError`` so the caller can pick another name."""
        with self._db.lock:
            self._db.conn.execute("SAVEPOINT add_photo")
            try:
                self._db.conn.execute(
                    f"INSERT INTO photos ({_COLUMNS}, sort_time)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.sha256, record.rel_path, record.size, record.original_name,
                     record.media_type, record.taken_at, record.received_at, record.profile,
                     record.latitude, record.longitude, record.camera, record.lens,
                     record.sort_time),
                )
                self._db.conn.execute(
                    "INSERT INTO copies (profile, sha256, rel_path, original_name, added_at,"
                    " sort_time, size, is_video) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.profile, record.sha256, record.rel_path, record.original_name,
                     record.received_at, record.sort_time, record.size, int(record.is_video)),
                )
            except sqlite3.Error as exc:
                self._db.conn.execute("ROLLBACK TO add_photo")
                self._db.conn.execute("RELEASE add_photo")
                if isinstance(exc, sqlite3.IntegrityError) and "photos.sha256" in str(exc):
                    return False
                raise
            self._db.conn.execute("RELEASE add_photo")
        return True

    def get(self, sha256: str) -> Optional[PhotoRecord]:
        with self._db.lock:
            row = self._db.conn.execute(
                f"SELECT {_COLUMNS} FROM photos WHERE sha256 = ?", (sha256,)
            ).fetchone()
        return _to_record(row) if row else None

    def known(self, sha256s: list) -> set:
        """The hashes in ``sha256s`` that the catalog holds, in one query."""
        if not sha256s:
            return set()
        found = set()
        with self._db.lock:
            for i in range(0, len(sha256s), 500):
                chunk = list(sha256s)[i:i + 500]
                marks = ",".join("?" for _ in chunk)
                rows = self._db.conn.execute(
                    f"SELECT sha256 FROM photos WHERE sha256 IN ({marks})", tuple(chunk)
                ).fetchall()
                found.update(row[0] for row in rows)
        return found

    def stored_hashes(self) -> set:
        """Every hash still in the catalog; the preview cache keeps only these."""
        with self._db.lock:
            return {row[0] for row in self._db.conn.execute("SELECT sha256 FROM photos")}

    def copies_of(self, profile: str, sha256s: list) -> set:
        """The hashes in ``sha256s`` that sit in ``profile``'s folder, in one query."""
        if not sha256s:
            return set()
        found = set()
        with self._db.lock:
            for i in range(0, len(sha256s), 500):
                chunk = list(sha256s)[i:i + 500]
                marks = ",".join("?" for _ in chunk)
                rows = self._db.conn.execute(
                    f"SELECT sha256 FROM copies WHERE profile = ? AND sha256 IN ({marks})",
                    (profile, *chunk)).fetchall()
                found.update(row[0] for row in rows)
        return found

    def page(self, offset: int, limit: int, narrow: PhotoFilter = PhotoFilter()) -> list:
        """Records in the requested order, newest first by default (taken time, then received)."""
        if limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit!r}")
        if offset < 0 or offset > MAX_ROW_ID:
            raise ValueError(f"offset is outside the database range, got {offset!r}")
        table, columns, owner = _source(narrow)
        where, params = _where(narrow, owner)
        order = _ORDERS.get(narrow.order, _ORDERS["newest"]).format(owner=owner)
        favorite = ("EXISTS (SELECT 1 FROM favorites f"
                    " WHERE f.profile = ? AND f.sha256 = p.sha256) AS favorite")
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT {columns}, {favorite} FROM {table}{where}"
                f" ORDER BY {order} LIMIT ? OFFSET ?",
                (narrow.viewer, *params, limit, offset),
            ).fetchall()
        return [_to_record(row) for row in rows]

    def hashes(self, narrow: PhotoFilter = PhotoFilter(), limit: int = 10_000) -> list:
        """Every matching hash in the same order as the gallery, capped by ``limit``."""
        if limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit!r}")
        if limit > MAX_ROW_ID:
            raise ValueError(f"limit is outside the database range, got {limit!r}")
        table, _, owner = _source(narrow)
        where, params = _where(narrow, owner)
        order = _ORDERS.get(narrow.order, _ORDERS["newest"]).format(owner=owner)
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT p.sha256 FROM {table}{where} ORDER BY {order} LIMIT ?",
                (*params, limit)).fetchall()
        return [row[0] for row in rows]

    def similar_status(self, profile: Optional[str] = None, viewer: str = "main") -> dict:
        """How many visible photos have a perceptual hash, a skip or no entry yet."""
        narrow = PhotoFilter(profile=profile, viewer=viewer)
        table, _, owner = _source(narrow)
        where, params = _where(narrow, owner)
        with self._db.lock:
            row = self._db.conn.execute(
                f"SELECT COUNT(*),"
                " COALESCE(SUM(CASE WHEN ph.sha256 IS NULL THEN 1 ELSE 0 END), 0),"
                " COALESCE(SUM(CASE WHEN ph.dhash = 'skip' THEN 1 ELSE 0 END), 0)"
                f" FROM {table} LEFT JOIN photo_hashes ph ON ph.sha256 = p.sha256{where}",
                params).fetchone()
        total, missing, skipped = row
        return {"total": total, "missing": missing, "skipped": skipped,
                "indexed": total - missing - skipped}

    def missing_hashes(self, profile: Optional[str] = None, viewer: str = "main",
                       limit: int = 100) -> list:
        """Visible photo hashes that have no perceptual-hash row yet, newest first."""
        if limit < 0:
            raise ValueError("limit must be >= 0")
        narrow = PhotoFilter(profile=profile, viewer=viewer)
        table, _, owner = _source(narrow)
        where, params = _where(narrow, owner)
        order = _ORDERS["newest"].format(owner=owner)
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT p.sha256 FROM {table}"
                f" LEFT JOIN photo_hashes ph ON ph.sha256 = p.sha256{where}"
                " AND ph.sha256 IS NULL"
                f" ORDER BY {order} LIMIT ?", (*params, limit)).fetchall()
        return [row[0] for row in rows]

    def set_hash(self, sha256: str, dhash: str) -> None:
        """Cache one perceptual hash or the ``skip`` marker for an unreadable file."""
        with self._db.lock:
            self._db.conn.execute(
                "INSERT INTO photo_hashes (sha256, dhash) VALUES (?, ?)"
                " ON CONFLICT(sha256) DO UPDATE SET dhash = excluded.dhash",
                (sha256, dhash))

    def similar_groups(self, profile: Optional[str] = None, viewer: str = "main",
                       limit: int = 200) -> list:
        """Read-only groups of visible photos sharing one exact perceptual hash."""
        narrow = PhotoFilter(profile=profile, viewer=viewer)
        table, columns, owner = _source(narrow)
        where, params = _where(narrow, owner)
        order = _ORDERS["newest"].format(owner=owner)
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT {columns}, ph.dhash FROM {table}"
                f" JOIN photo_hashes ph ON ph.sha256 = p.sha256{where}"
                " AND ph.dhash <> 'skip'"
                f" ORDER BY {order}", params).fetchall()
        grouped = {}
        for row in rows:
            values = dict(row)
            dhash = values.pop("dhash")
            grouped.setdefault(dhash, []).append(_to_record(values))
        groups = [(dhash, records) for dhash, records in grouped.items() if len(records) > 1]
        groups.sort(key=lambda item: (-len(item[1]), item[0]))
        return groups[:limit]

    def outline(self, profile: Optional[str] = None, viewer: str = "main") -> Outline:
        """Months and video count, for one profile or (None) everyone, plus the viewer's
        favorites. Archived photos are hidden from the timeline."""
        narrow = PhotoFilter(profile=profile, viewer=viewer)
        hidden = PhotoFilter(profile=profile, viewer=viewer, archived=True)
        table, _, owner = _source(narrow)
        where, params = _where(narrow, owner)
        hidden_where, hidden_params = _where(hidden, owner)
        video = "c.is_video = 1" if profile else "p.media_type LIKE 'video/%'"
        video_where = f"{where} AND" if where else " WHERE"
        with self._db.lock:
            months = self._db.conn.execute(
                f"SELECT substr({owner}.sort_time, 1, 7) AS month, COUNT(*) FROM {table}{where}"
                " GROUP BY month ORDER BY month DESC", params
            ).fetchall()
            videos = self._db.conn.execute(
                f"SELECT COUNT(*) FROM {table}{video_where} {video}", params
            ).fetchone()[0]
            total = self._db.conn.execute(
                f"SELECT COUNT(*) FROM {table}{where}", params).fetchone()[0]
            archived = self._db.conn.execute(
                f"SELECT COUNT(*) FROM {table}{hidden_where}", hidden_params).fetchone()[0]
            favorites = self._db.conn.execute(
                "SELECT COUNT(*) FROM favorites f JOIN photos p ON p.sha256 = f.sha256"
                " WHERE f.profile = ? AND NOT EXISTS (SELECT 1 FROM archived a"
                " WHERE a.profile = ? AND a.sha256 = p.sha256)",
                (viewer, viewer)).fetchone()[0]
            place_where = f"{where} AND p.latitude IS NOT NULL AND p.longitude IS NOT NULL"
            places = self._db.conn.execute(
                f"SELECT ROUND(p.latitude, 1) AS lat, ROUND(p.longitude, 1) AS lon, COUNT(*)"
                f" FROM {table}{place_where}"
                " GROUP BY lat, lon ORDER BY COUNT(*) DESC, lat, lon LIMIT 100",
                params).fetchall()
            camera_where = f"{where} AND p.camera IS NOT NULL"
            cameras = self._db.conn.execute(
                f"SELECT p.camera, COUNT(*) FROM {table}{camera_where}"
                " GROUP BY p.camera ORDER BY COUNT(*) DESC, p.camera LIMIT 50",
                params).fetchall()
        return Outline(months=tuple((row[0], row[1]) for row in months), videos=videos,
                       favorites=favorites, total=total, archived=archived,
                       places=tuple((row[0], row[1], row[2]) for row in places),
                       cameras=tuple((row[0], row[1]) for row in cameras))

    def stats(self, profile: Optional[str] = None) -> LibraryStats:
        table, where, params = _totals_source(profile)
        alias = "c" if profile else "p"
        latest = "c.added_at" if profile else "p.received_at"
        with self._db.lock:
            row = self._db.conn.execute(
                f"SELECT COUNT(*), COALESCE(SUM({alias}.size), 0), MAX({latest}) FROM {table}{where}",
                params,
            ).fetchone()
        return LibraryStats(count=row[0], total_bytes=row[1], last_received=row[2])

    def storage(self, profile: Optional[str] = None) -> StorageReport:
        """Disk use and the ten largest files; one person's share or the whole library."""
        with self._db.lock:
            if profile:
                row = self._db.conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(size), 0),"
                    " COALESCE(SUM(CASE WHEN is_video = 0 THEN 1 ELSE 0 END), 0),"
                    " COALESCE(SUM(CASE WHEN is_video = 1 THEN 1 ELSE 0 END), 0)"
                    " FROM copies WHERE profile = ?", (profile,)).fetchone()
                shared = self._db.conn.execute(
                    "SELECT COUNT(*) FROM copies c WHERE c.profile = ? AND EXISTS"
                    " (SELECT 1 FROM copies o WHERE o.sha256 = c.sha256 AND o.profile <> c.profile)",
                    (profile,)).fetchone()[0]
                largest = self._db.conn.execute(
                    "SELECT sha256, original_name, size, sort_time FROM copies"
                    " WHERE profile = ? ORDER BY size DESC, sha256 LIMIT 10", (profile,)).fetchall()
                people = ()
            else:
                row = self._db.conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(size), 0),"
                    " COALESCE(SUM(CASE WHEN media_type NOT LIKE 'video/%' THEN 1 ELSE 0 END), 0),"
                    " COALESCE(SUM(CASE WHEN media_type LIKE 'video/%' THEN 1 ELSE 0 END), 0)"
                    " FROM photos").fetchone()
                shared = self._db.conn.execute(
                    "SELECT COUNT(*) FROM (SELECT sha256 FROM copies GROUP BY sha256"
                    " HAVING COUNT(*) > 1)").fetchone()[0]
                largest = self._db.conn.execute(
                    "SELECT sha256, original_name, size, sort_time FROM photos"
                    " ORDER BY size DESC, sha256 LIMIT 10").fetchall()
                people = tuple(PersonStorage(row[0], row[1], row[2]) for row in
                               self._db.conn.execute(
                                   "SELECT profile, COUNT(*), COALESCE(SUM(size), 0) FROM copies"
                                   " GROUP BY profile ORDER BY SUM(size) DESC").fetchall())
        return StorageReport(count=row[0], bytes=row[1], photos=row[2], videos=row[3],
                             shared=shared,
                             largest=tuple(StorageFile(row[0], row[1], row[2], row[3])
                                           for row in largest),
                             people=people)
