"""A per-person trash: move a copy aside, restore it through the normal ingest, or delete it."""

import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from .atomic_file import fsync_dir, replace_with_retry
from .copies import CopyIndex
from .database import Database
from .errors import HarborError
from .naming import safe_name
from .records import TrashItem, UploadClaim
from .store import PhotoStore, local_now


class TrashBook:
    def __init__(self, db: Database, library: Path, store: PhotoStore, copies: CopyIndex,
                 now: Callable[[], datetime] = local_now) -> None:
        self._db = db
        self._store = store
        self._copies = copies
        self._now = now
        self.root = library / ".harbor" / "trash"
        self.root.mkdir(parents=True, exist_ok=True)

    def move(self, profile: str, sha256: str) -> int:
        """Move one person's copy to trash and forget it in the catalog; returns the trash id."""
        with self._store.lock:
            found = self._store.locate(sha256, profile)
            if found is None:
                raise HarborError("that photo is not in your library",
                                  "it was already removed or moved",
                                  "reload the gallery and try again", status=404)
            source, record = found
            token = secrets.token_hex(8)
            relative = Path(token) / safe_name(record.original_name)
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with self._db.lock:
                cursor = self._db.conn.execute(
                    "INSERT INTO trash (profile, sha256, original_name, rel_path, trash_path,"
                    " size, media_type, taken_at, trashed_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (profile, sha256, record.original_name, record.rel_path,
                     relative.as_posix(), record.size, record.media_type, record.taken_at,
                     self._now().isoformat(timespec="seconds")))
                trash_id = cursor.lastrowid
            try:
                replace_with_retry(source, target)
                fsync_dir(target.parent)
                self._copies.forget(profile, sha256)
            except Exception:
                if target.exists() and not source.exists():
                    try:
                        replace_with_retry(target, source)
                    except OSError:  # hygiene: allow rollback best effort after a failed move
                        pass
                with self._db.lock:
                    self._db.conn.execute("DELETE FROM trash WHERE id = ?", (trash_id,))
                raise
        return trash_id

    def listing(self, profile: str) -> list:
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT id, sha256, original_name, size, media_type, taken_at, trashed_at"
                " FROM trash WHERE profile = ? ORDER BY id DESC", (profile,)).fetchall()
        return [TrashItem(id=row[0], sha256=row[1], name=row[2], size=row[3],
                          media_type=row[4], taken_at=row[5], trashed_at=row[6])
                for row in rows]

    def restore(self, profile: str, ident) -> object:
        """Re-ingest the trashed bytes; the normal hash-verified path places them again."""
        item, path = self._owned(profile, ident)
        if not path.is_file():
            raise HarborError("the trashed file is missing", str(path),
                              "delete this trash entry and recover from the backup")
        claim = UploadClaim(original_name=item.name, sha256=item.sha256,
                            taken_at=item.taken_at, profile=profile)
        with open(path, "rb") as handle:
            result = self._store.ingest(handle, item.size, claim)
        self._forget_file(item, path)
        return result

    def delete(self, profile: str, ident) -> None:
        item, path = self._owned(profile, ident)
        path.unlink(missing_ok=True)
        self._forget_file(item, path)

    def empty(self, profile: str) -> int:
        count = 0
        for item in self.listing(profile):
            _, path = self._owned(profile, item.id)
            path.unlink(missing_ok=True)
            self._forget_file(item, path)
            count += 1
        return count

    def _owned(self, profile: str, ident):
        try:
            number = int(ident)
        except (TypeError, ValueError):
            number = 0
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT id, sha256, original_name, size, media_type, taken_at, trashed_at,"
                " trash_path FROM trash WHERE id = ? AND profile = ?",
                (number, profile)).fetchone()
        if row is None:
            raise HarborError(f"no trash entry {ident}", "it was restored or deleted",
                              "reload the Trash tab", status=404)
        item = TrashItem(id=row[0], sha256=row[1], name=row[2], size=row[3],
                         media_type=row[4], taken_at=row[5], trashed_at=row[6])
        return item, self.root / row[7]

    def _forget_file(self, item: TrashItem, path: Path) -> None:
        with self._db.lock:
            self._db.conn.execute("DELETE FROM trash WHERE id = ?", (item.id,))
        try:
            shutil.rmtree(path.parent)
        except OSError:  # hygiene: allow already-removed trash folder is fine
            pass
