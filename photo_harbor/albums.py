"""Personal albums and favorites: named collections that never move or copy a file."""

import sqlite3
from datetime import datetime
from typing import Callable

from .database import Database
from .errors import HarborError
from .records import Album
from .store import local_now

MAX_NAME = 60


def _clean_name(value) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        raise HarborError("an album needs a name", "the name was empty",
                          "type a name such as \u201cSummer 2026\u201d", status=400)
    if len(name) > MAX_NAME:
        raise HarborError("that album name is too long", f"names are at most {MAX_NAME} characters",
                          "choose a shorter name", status=400)
    return name


def _album_id(value) -> int:
    try:
        ident = int(value)
    except (TypeError, ValueError):
        ident = 0
    if ident < 1:
        raise HarborError("that is not an album id", f"{value!r} is not a whole number",
                          "reload the gallery and try again", status=400)
    return ident


class AlbumBook:
    """Albums belong to one person; favorites are that person's own mark on a photo."""

    def __init__(self, db: Database, now: Callable[[], datetime] = local_now) -> None:
        self._db = db
        self._now = now

    def summary(self, profile: str) -> tuple:
        """``(favorite count, [Album, ...])`` for the signed-in person, names in A-Z order."""
        with self._db.lock:
            favorites = self._db.conn.execute(
                "SELECT COUNT(*) FROM favorites f JOIN photos p ON p.sha256 = f.sha256"
                " WHERE f.profile = ?", (profile,)).fetchone()[0]
            rows = self._db.conn.execute(
                "SELECT al.id, al.name, COUNT(p.sha256) AS n,"
                " (SELECT a2.sha256 FROM album_photos a2 JOIN photos p2 ON p2.sha256 = a2.sha256"
                "  WHERE a2.album_id = al.id"
                "  ORDER BY p2.sort_time DESC, p2.sha256 DESC LIMIT 1) AS cover"
                " FROM albums al"
                " LEFT JOIN album_photos a ON a.album_id = al.id"
                " LEFT JOIN photos p ON p.sha256 = a.sha256"
                " WHERE al.profile = ? GROUP BY al.id ORDER BY al.name COLLATE NOCASE",
                (profile,)).fetchall()
        return favorites, [Album(id=row[0], name=row[1], count=row[2], cover=row[3])
                           for row in rows]

    def create(self, profile: str, name) -> Album:
        clean = _clean_name(name)
        with self._db.lock:
            try:
                cursor = self._db.conn.execute(
                    "INSERT INTO albums (profile, name, created_at) VALUES (?, ?, ?)",
                    (profile, clean, self._now().isoformat(timespec="seconds")))
            except sqlite3.IntegrityError as exc:
                raise HarborError(f"you already have an album called {clean!r}",
                                  "album names are unique for each person",
                                  "choose another name or rename the existing album",
                                  status=409) from exc
        return Album(id=cursor.lastrowid, name=clean)

    def rename(self, profile: str, ident, name) -> Album:
        album = _album_id(ident)
        clean = _clean_name(name)
        with self._db.lock:
            self._owned(profile, album)
            try:
                self._db.conn.execute("UPDATE albums SET name = ? WHERE id = ?", (clean, album))
            except sqlite3.IntegrityError as exc:
                raise HarborError(f"you already have an album called {clean!r}",
                                  "album names are unique for each person",
                                  "choose another name", status=409) from exc
        return Album(id=album, name=clean)

    def delete(self, profile: str, ident) -> None:
        album = _album_id(ident)
        with self._db.lock:
            self._owned(profile, album)
            self._db.conn.execute("SAVEPOINT drop_album")
            try:
                self._db.conn.execute("DELETE FROM album_photos WHERE album_id = ?", (album,))
                self._db.conn.execute("DELETE FROM albums WHERE id = ?", (album,))
            except sqlite3.Error:
                self._db.conn.execute("ROLLBACK TO drop_album")
                self._db.conn.execute("RELEASE drop_album")
                raise
            self._db.conn.execute("RELEASE drop_album")

    def owned(self, profile: str, ident) -> bool:
        """Whether this person owns the album; a bad id is a 400, a missing one is False."""
        album = _album_id(ident)
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT 1 FROM albums WHERE id = ? AND profile = ?", (album, profile)).fetchone()
        return row is not None

    def members(self, profile: str, ident) -> list:
        """The hashes in one owned album, newest photo first."""
        album = _album_id(ident)
        with self._db.lock:
            self._owned(profile, album)
            rows = self._db.conn.execute(
                "SELECT a.sha256 FROM album_photos a JOIN photos p ON p.sha256 = a.sha256"
                " WHERE a.album_id = ? ORDER BY p.sort_time DESC, p.sha256 DESC",
                (album,)).fetchall()
        return [row[0] for row in rows]

    def add(self, profile: str, ident, sha256: str, member: bool) -> bool:
        """Put a photo in an album or take it out; True when the album changed."""
        return self.add_many(profile, ident, [sha256], member) == 1

    def add_many(self, profile: str, ident, sha256s: list, member: bool) -> int:
        """Add or remove several photos in one lock; returns how many rows changed."""
        album = _album_id(ident)
        if not sha256s:
            return 0
        with self._db.lock:
            self._owned(profile, album)
            if member:
                at = self._now().isoformat(timespec="seconds")
                cursor = self._db.conn.executemany(
                    "INSERT OR IGNORE INTO album_photos (album_id, sha256, added_at)"
                    " VALUES (?, ?, ?)",
                    [(album, sha256, at) for sha256 in sha256s])
            else:
                marks = ",".join("?" for _ in sha256s)
                cursor = self._db.conn.execute(
                    f"DELETE FROM album_photos WHERE album_id = ? AND sha256 IN ({marks})",
                    (album, *sha256s))
        return cursor.rowcount

    def favorite(self, profile: str, sha256: str, favorite: bool) -> bool:
        """Mark or unmark one photo for one person; True when the mark changed."""
        return self.favorite_many(profile, [sha256], favorite) == 1

    def favorite_many(self, profile: str, sha256s: list, favorite: bool) -> int:
        """Mark or unmark several photos in one lock; returns how many rows changed."""
        if not sha256s:
            return 0
        with self._db.lock:
            if favorite:
                at = self._now().isoformat(timespec="seconds")
                cursor = self._db.conn.executemany(
                    "INSERT OR IGNORE INTO favorites (profile, sha256, added_at)"
                    " VALUES (?, ?, ?)",
                    [(profile, sha256, at) for sha256 in sha256s])
            else:
                marks = ",".join("?" for _ in sha256s)
                cursor = self._db.conn.execute(
                    f"DELETE FROM favorites WHERE profile = ? AND sha256 IN ({marks})",
                    (profile, *sha256s))
        return cursor.rowcount

    def _owned(self, profile: str, album: int) -> None:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT 1 FROM albums WHERE id = ? AND profile = ?", (album, profile)).fetchone()
        if row is None:
            raise HarborError(f"no album {album}", "it was deleted or belongs to someone else",
                              "reload the gallery and try again", status=404)
