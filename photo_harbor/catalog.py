"""The index of stored originals: one row per distinct file, keyed by SHA-256."""

import sqlite3
from typing import Optional

from .database import Database
from .records import LibraryStats, Outline, PhotoFilter, PhotoRecord

_COLUMNS = "sha256, rel_path, size, original_name, media_type, taken_at, received_at, profile"


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
    if narrow.query:
        escaped = narrow.query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
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

    def has_copy(self, profile: str, sha256: str) -> bool:
        """Whether ``profile``'s folder holds this photo, so it is theirs to see."""
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT 1 FROM copies WHERE profile = ? AND sha256 = ?", (profile, sha256)
            ).fetchone()
        return row is not None

    def page(self, offset: int, limit: int, narrow: PhotoFilter = PhotoFilter()) -> list:
        """Records newest first by taken time, falling back to received time."""
        table, columns, owner = _source(narrow)
        where, params = _where(narrow, owner)
        favorite = ("EXISTS (SELECT 1 FROM favorites f"
                    " WHERE f.profile = ? AND f.sha256 = p.sha256) AS favorite")
        with self._db.lock:
            rows = self._db.conn.execute(
                f"SELECT {columns}, {favorite} FROM {table}{where}"
                f" ORDER BY {owner}.sort_time DESC, {owner}.sha256 DESC"
                " LIMIT ? OFFSET ?",
                (narrow.viewer, *params, limit, offset),
            ).fetchall()
        return [_to_record(row) for row in rows]

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
