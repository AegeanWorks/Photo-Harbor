"""Personal tags: named marks on photos that never move or copy a file."""

import sqlite3
from datetime import datetime
from typing import Callable

from .database import Database, MAX_ROW_ID
from .errors import HarborError
from .records import Tag
from .store import local_now

MAX_NAME = 40


def _clean_name(value) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        raise HarborError("a tag needs a name", "the name was empty",
                          "type a name such as \u201cbeach\u201d", status=400)
    if len(name) > MAX_NAME:
        raise HarborError("that tag name is too long", f"names are at most {MAX_NAME} characters",
                          "choose a shorter name", status=400)
    return name


def _tag_id(value) -> int:
    if isinstance(value, bool):
        ident = 0
    elif isinstance(value, int):
        ident = value
    elif isinstance(value, str):
        try:
            ident = int(value.strip())
        except (TypeError, ValueError):
            ident = 0
    else:
        ident = 0
    if ident < 1 or ident > MAX_ROW_ID:
        raise HarborError("that is not a tag id",
                          f"{value!r} is not a whole number this library can use",
                          "reload the gallery and try again", status=400)
    return ident


class TagBook:
    """Tags belong to one person; a tag marks a photo without touching its folder."""

    def __init__(self, db: Database, now: Callable[[], datetime] = local_now) -> None:
        self._db = db
        self._now = now

    def summary(self, profile: str) -> list:
        """The person's tags and how many non-archived photos each one marks."""
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT t.id, t.name,"
                " COALESCE(SUM(CASE WHEN pt.sha256 IS NOT NULL AND ar.sha256 IS NULL"
                "  THEN 1 ELSE 0 END), 0) AS n"
                " FROM tags t"
                " LEFT JOIN photo_tags pt ON pt.tag_id = t.id"
                " LEFT JOIN archived ar ON ar.profile = t.profile AND ar.sha256 = pt.sha256"
                " WHERE t.profile = ? GROUP BY t.id ORDER BY t.name COLLATE NOCASE",
                (profile,)).fetchall()
        return [Tag(id=row[0], name=row[1], count=row[2]) for row in rows]

    def create(self, profile: str, name) -> Tag:
        """Return the person's tag with this name, creating it once; matching is case-insensitive."""
        clean = _clean_name(name)
        with self._db.lock:
            self._db.conn.execute(
                "INSERT OR IGNORE INTO tags (profile, name, created_at) VALUES (?, ?, ?)",
                (profile, clean, self._now().isoformat(timespec="seconds")))
            row = self._db.conn.execute(
                "SELECT id, name FROM tags WHERE profile = ? AND name = ?",
                (profile, clean)).fetchone()
        return Tag(id=row[0], name=row[1])

    def rename(self, profile: str, ident, name) -> Tag:
        tag = _tag_id(ident)
        clean = _clean_name(name)
        with self._db.lock:
            self._owned(profile, tag)
            try:
                self._db.conn.execute("UPDATE tags SET name = ? WHERE id = ?", (clean, tag))
            except sqlite3.IntegrityError as exc:
                raise HarborError(f"you already have a tag called {clean!r}",
                                  "tag names are unique for each person",
                                  "choose another name", status=409) from exc
        return Tag(id=tag, name=clean)

    def delete(self, profile: str, ident) -> None:
        tag = _tag_id(ident)
        with self._db.lock:
            self._owned(profile, tag)
            self._db.conn.execute("SAVEPOINT drop_tag")
            try:
                self._db.conn.execute("DELETE FROM photo_tags WHERE tag_id = ?", (tag,))
                self._db.conn.execute("DELETE FROM tags WHERE id = ?", (tag,))
            except sqlite3.Error:
                self._db.conn.execute("ROLLBACK TO drop_tag")
                self._db.conn.execute("RELEASE drop_tag")
                raise
            self._db.conn.execute("RELEASE drop_tag")

    def owned(self, profile: str, ident) -> bool:
        """Whether this person owns the tag; a bad id is a 400, a missing one is False."""
        tag = _tag_id(ident)
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT 1 FROM tags WHERE id = ? AND profile = ?", (tag, profile)).fetchone()
        return row is not None

    def members(self, profile: str, sha256: str) -> list:
        """The ids of this person's tags on one photo."""
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT t.id FROM tags t JOIN photo_tags pt ON pt.tag_id = t.id"
                " WHERE t.profile = ? AND pt.sha256 = ? ORDER BY t.name COLLATE NOCASE",
                (profile, sha256)).fetchall()
        return [row[0] for row in rows]

    def names(self, profile: str, sha256: str) -> list:
        """The names of this person's tags on one photo, A-Z."""
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT t.name FROM tags t JOIN photo_tags pt ON pt.tag_id = t.id"
                " WHERE t.profile = ? AND pt.sha256 = ? ORDER BY t.name COLLATE NOCASE",
                (profile, sha256)).fetchall()
        return [row[0] for row in rows]

    def add(self, profile: str, ident, sha256: str, member: bool) -> bool:
        """Put a tag on a photo or take it off; True when the mark changed."""
        return self.add_many(profile, ident, [sha256], member) == 1

    def add_many(self, profile: str, ident, sha256s: list, member: bool) -> int:
        """Mark or unmark several photos in one lock; returns how many rows changed."""
        tag = _tag_id(ident)
        if not sha256s:
            return 0
        with self._db.lock:
            self._owned(profile, tag)
            if member:
                at = self._now().isoformat(timespec="seconds")
                cursor = self._db.conn.executemany(
                    "INSERT OR IGNORE INTO photo_tags (tag_id, sha256, added_at)"
                    " VALUES (?, ?, ?)",
                    [(tag, sha256, at) for sha256 in sha256s])
            else:
                marks = ",".join("?" for _ in sha256s)
                cursor = self._db.conn.execute(
                    f"DELETE FROM photo_tags WHERE tag_id = ? AND sha256 IN ({marks})",
                    (tag, *sha256s))
        return cursor.rowcount

    def _owned(self, profile: str, tag: int) -> None:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT 1 FROM tags WHERE id = ? AND profile = ?", (tag, profile)).fetchone()
        if row is None:
            raise HarborError(f"no tag {tag}", "it was deleted or belongs to someone else",
                              "reload the gallery and try again", status=404)
