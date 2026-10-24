"""The people a library belongs to: a name, an id, a folder in the library and a Shortcut key."""

import re
import secrets
import sqlite3
import unicodedata
from datetime import datetime
from typing import Optional

from .database import OWNER_PROFILE, Database
from .errors import HarborError
from .naming import folder_name
from .records import Profile

MAX_NAME = 40
_TRANSLIT = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
_SELECT = "SELECT id, name, key, folder FROM profiles"


def profile_id(name: str) -> str:
    """A URL-safe id: ``Ayşe Yılmaz`` becomes ``ayse-yilmaz``."""
    ascii_name = unicodedata.normalize("NFKD", name.translate(_TRANSLIT))
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:MAX_NAME]


def clean_name(name: str) -> str:
    cleaned = " ".join(str(name).split())[:MAX_NAME]
    if not profile_id(cleaned):
        raise HarborError("a profile needs a name with a letter or digit",
                          f"{name!r} has none", "type a name such as Ayşe")
    return cleaned


def _to_profile(row: sqlite3.Row) -> Profile:
    return Profile(id=row["id"], name=row["name"], key=row["key"], folder=row["folder"] or "")


class ProfileBook:
    def __init__(self, db: Database, owner_key: str) -> None:
        """Make sure the owner profile exists and holds the library key, and that every person
        (including those from older libraries) has a folder."""
        self._db = db
        with self._db.lock:
            self._db.conn.execute(
                "INSERT INTO profiles (id, name, key, created_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET key = excluded.key",
                (OWNER_PROFILE, "Main", owner_key, _now()),
            )
            for row in self._db.conn.execute(
                    "SELECT id, name FROM profiles WHERE folder IS NULL ORDER BY created_at").fetchall():
                self._db.conn.execute("UPDATE profiles SET folder = ? WHERE id = ?",
                                      (self.free_folder(row["name"]), row["id"]))

    def all(self) -> list:
        """Owner first, then the others by name."""
        with self._db.lock:
            rows = self._db.conn.execute(
                f"{_SELECT} ORDER BY id != ?, name COLLATE NOCASE", (OWNER_PROFILE,)
            ).fetchall()
        return [_to_profile(row) for row in rows]

    def get(self, ident: str) -> Profile:
        with self._db.lock:
            row = self._db.conn.execute(f"{_SELECT} WHERE id = ?", (ident,)).fetchone()
        if row is None:
            raise HarborError(f"no profile {ident!r}", "it does not exist in this library",
                              "reload the page", status=404)
        return _to_profile(row)

    def by_key(self, key: str) -> Optional[Profile]:
        if not key:
            return None
        with self._db.lock:
            row = self._db.conn.execute(f"{_SELECT} WHERE key = ?", (key,)).fetchone()
        return _to_profile(row) if row else None

    def create(self, name: str) -> Profile:
        cleaned = clean_name(name)
        with self._db.lock:
            new = Profile(id=profile_id(cleaned), name=cleaned, key=secrets.token_urlsafe(24),  # aikit:allow-secret generated at runtime
                          folder=self.free_folder(cleaned))
            try:
                self._db.conn.execute(
                    "INSERT INTO profiles (id, name, key, created_at, folder) VALUES (?, ?, ?, ?, ?)",
                    (new.id, new.name, new.key, _now(), new.folder),
                )
            except sqlite3.IntegrityError as exc:
                raise HarborError(f"a profile like {cleaned!r} already exists",
                                  f"its id {new.id!r} is taken", "choose a different name",
                                  status=409) from exc
        return new

    def update(self, ident: str, name: Optional[str] = None, new_key: bool = False,
               folder: Optional[str] = None) -> Profile:
        """Rename a person (``folder`` is set by the layout once their folder has moved), or give
        them a new key so their old Shortcut stops working."""
        if new_key and ident == OWNER_PROFILE:
            raise HarborError("the main profile's key is the library key",
                              "it is changed on the PC, not from the gallery",
                              "run `python -m photo_harbor key --new`", status=403)
        self.get(ident)
        with self._db.lock:
            if name is not None:
                self._db.conn.execute("UPDATE profiles SET name = ? WHERE id = ?",
                                      (clean_name(name), ident))
            if folder is not None:
                self._db.conn.execute("UPDATE profiles SET folder = ? WHERE id = ?", (folder, ident))
            if new_key:
                self._db.conn.execute("UPDATE profiles SET key = ? WHERE id = ?",
                                      (secrets.token_urlsafe(24), ident))
        return self.get(ident)

    def free_folder(self, name: str, keep: Optional[str] = None) -> str:
        """``Ayşe``, or ``Ayşe (2)`` when that folder name (any letter case) is already taken.
        ``keep`` is the person being renamed, whose own current folder does not count."""
        with self._db.lock:
            taken = {row[0].lower() for row in self._db.conn.execute(
                "SELECT folder FROM profiles WHERE folder IS NOT NULL AND id IS NOT ?", (keep,))}
        base = folder_name(name)
        candidate, number = base, 2
        while candidate.lower() in taken:
            candidate, number = f"{base} ({number})", number + 1
        return candidate


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
