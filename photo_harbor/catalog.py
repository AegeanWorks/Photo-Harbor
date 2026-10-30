"""The index of stored originals: one row per distinct file, keyed by SHA-256."""

import sqlite3
from typing import Optional

from .database import Database
from .records import (LibraryStats, Outline, PersonStorage, PhotoFilter, PhotoRecord,
                      StorageFile, StorageReport)

_COLUMNS = "sha256, rel_path, size, original_name, media_type, taken_at, received_at, profile"
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
    for term in narrow.query.split()[:8] if narrow.query else ():
        escaped = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        clauses.append(f"{owner}.original_name LIKE ? ESCAPE '!'")
        params.append(f"%{escaped}%")
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
                    f"INSERT INTO photos ({_COLUMNS}, sort_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.sha256, record.rel_path, record.size, record.original_name,
                     record.media_type, record.taken_at, record.received_at, record.profile,
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
                if not isinstance(exc, sqlite3.IntegrityError) or "rel_path" in str(exc):
                    raise
                return False
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
        marks = ",".join("?" for _ in sha256s)
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT sha256 FROM photos WHERE sha256 IN ({marks})", tuple(sha256s)
            ).fetchall()
        return {row[0] for row in rows}

    def copies_of(self, profile: str, sha256s: list) -> set:
        """The hashes in ``sha256s`` that sit in ``profile``'s folder, in one query."""
        if not sha256s:
            return set()
        marks = ",".join("?" for _ in sha256s)
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT sha256 FROM copies WHERE profile = ? AND sha256 IN ({marks})",
                (profile, *sha256s)).fetchall()
        return {row[0] for row in rows}

    def page(self, offset: int, limit: int, narrow: PhotoFilter = PhotoFilter()) -> list:
        """Records in the requested order, newest first by default (taken time, then received)."""
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
        table, _, owner = _source(narrow)
        where, params = _where(narrow, owner)
        order = _ORDERS.get(narrow.order, _ORDERS["newest"]).format(owner=owner)
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT p.sha256 FROM {table}{where} ORDER BY {order} LIMIT ?",
                (*params, limit)).fetchall()
        return [row[0] for row in rows]

    def outline(self, profile: Optional[str] = None, viewer: str = "main") -> Outline:
        """Months and video count, for one profile or (None) everyone, plus the viewer's
        favorites."""
        # One person's totals come from their copies alone; no join needed.
        table, where, params = _totals_source(profile)
        alias = "c" if profile else "p"
        video = "c.is_video = 1" if profile else "p.media_type LIKE 'video/%'"
        with self._db.lock:
            months = self._db.conn.execute(
                f"SELECT substr({alias}.sort_time, 1, 7) AS month, COUNT(*) FROM {table}{where}"
                " GROUP BY month ORDER BY month DESC", params
            ).fetchall()
            video_where = f"{where} AND" if where else " WHERE"
            videos = self._db.conn.execute(
                f"SELECT COUNT(*) FROM {table}{video_where} {video}", params
            ).fetchone()[0]
            favorites = self._db.conn.execute(
                "SELECT COUNT(*) FROM favorites f JOIN photos p ON p.sha256 = f.sha256"
                " WHERE f.profile = ?", (viewer,)).fetchone()[0]
        return Outline(months=tuple((row[0], row[1]) for row in months), videos=videos,
                       favorites=favorites)

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
