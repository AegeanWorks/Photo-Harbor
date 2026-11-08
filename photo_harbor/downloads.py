"""One-off ZIP archives for a selection or album, with expiring one-time tokens."""

import shutil
import secrets
import threading
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Callable

from .errors import HarborError
from .naming import safe_name
from .records import PhotoRecord

MAX_BYTES = 8 * 1024 ** 3
RESERVE_BYTES = 1 * 1024 ** 3
TTL_SECONDS = 15 * 60
STALE_SECONDS = 3600


def _entry_key(name: str) -> str:
    """One key for names a case- or normalization-insensitive filesystem would merge."""
    return unicodedata.normalize("NFC", name).casefold()


def _entry_name(record: PhotoRecord, used: set) -> str:
    base = safe_name(record.original_name)
    if _entry_key(base) not in used:
        used.add(_entry_key(base))
        return base
    hashed = f"{record.sha256[:8]}-{base}"
    if _entry_key(hashed) not in used:
        used.add(_entry_key(hashed))
        return hashed
    counter = len(used) + 1
    while True:
        name = f"{counter}-{hashed}"
        if _entry_key(name) not in used:
            used.add(_entry_key(name))
            return name
        counter += 1


class Downloads:
    """Builds stored ZIPs in the library's state directory; tokens live in memory."""

    def __init__(self, state_dir: Path, clock: Callable[[], float] = time.monotonic) -> None:
        self._dir = state_dir / "downloads"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = threading.Lock()
        self._tokens = {}
        self.clean()

    def clean(self) -> None:
        """Startup cleanup: no token survives a restart, so an abandoned archive older than an
        hour should not either. A younger one may belong to a Harbor process still serving it."""
        with self._lock:
            cutoff = time.time() - STALE_SECONDS
            for path in self._dir.glob("*.zip"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError:
                    continue
            self._tokens.clear()

    def prepare(self, entries: list, name: str, profile: str) -> dict:
        """Write ``[(PhotoRecord, path), ...]`` to a new ZIP and return its token details."""
        if not entries:
            raise HarborError("nothing to download", "the selection or album was empty",
                              "choose at least one photo", status=400)
        try:
            total = sum(path.stat().st_size for _, path in entries)
        except OSError as exc:
            raise HarborError("a photo disappeared before it could be zipped",
                              str(exc), "reload the gallery and try again", status=404) from exc
        if total > MAX_BYTES:
            raise HarborError("that download is too large", f"it would be {total} bytes",
                              f"download fewer than {MAX_BYTES // 1024 ** 3} GiB at once",
                              status=413)
        free = shutil.disk_usage(self._dir).free
        if free < total + RESERVE_BYTES:
            raise HarborError("not enough free disk space for that download",
                              f"{total} bytes are needed with a {RESERVE_BYTES} byte reserve,"
                              f" but only {free} are free",
                              "free some space or download fewer photos", status=507)
        token = secrets.token_urlsafe(18)
        target = self._dir / f"{token}.zip"
        try:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
                used = set()
                for record, path in entries:
                    try:
                        archive.write(path, _entry_name(record, used))
                    except OSError as exc:
                        raise HarborError("a photo disappeared before it could be zipped",
                                          str(exc), "reload the gallery and try again",
                                          status=404) from exc
        except HarborError:
            target.unlink(missing_ok=True)
            raise
        except Exception:  # hygiene: allow zipfile errors must not leave a tokenless temp file
            target.unlink(missing_ok=True)
            raise
        with self._lock:
            self._expire_locked()
            self._tokens[token] = (target, name, profile, self._clock() + TTL_SECONDS, total)
        return {"url": f"/api/download/{token}", "name": name, "count": len(entries),
                "bytes": total}

    def take(self, token: str, profile: str, consume: bool = True):
        """The ``(path, name, bytes)`` for this person's live token; removes it when consumed.

        ``consume`` is False for a HEAD probe: the link works once, and asking for its headers
        must not spend that single use or delete the file the real download needs.
        """
        with self._lock:
            self._expire_locked()
            item = self._tokens.get(token)
            if item is None or item[2] != profile:
                return None
            if consume:
                self._tokens.pop(token, None)
        path, name, _, expires, total = item
        if expires < self._clock() or not path.is_file():
            if consume:
                path.unlink(missing_ok=True)
            return None
        return path, name, total

    def _expire_locked(self) -> None:
        now = self._clock()
        for token, (path, _, _, expires, _) in list(self._tokens.items()):
            if expires < now:
                self._tokens.pop(token, None)
                path.unlink(missing_ok=True)
