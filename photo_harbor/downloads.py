"""One-off ZIP archives for a selection or album, with expiring one-time tokens."""

import shutil
import secrets
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable

from .errors import HarborError
from .naming import safe_name
from .records import PhotoRecord

MAX_BYTES = 8 * 1024 ** 3
RESERVE_BYTES = 1 * 1024 ** 3
TTL_SECONDS = 15 * 60


def _entry_name(record: PhotoRecord, used: set) -> str:
    name = safe_name(record.original_name)
    if name in used:
        name = f"{record.sha256[:8]}-{name}"
    if name in used:
        name = f"{len(used) + 1}-{name}"
    used.add(name)
    return name


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
        """Startup cleanup: no token survives a restart, so no archive should either."""
        with self._lock:
            for path in self._dir.glob("*.zip"):
                try:
                    path.unlink()
                except OSError:  # hygiene: allow locked temp archive must not abort startup cleanup
                    pass
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
                    archive.write(path, _entry_name(record, used))
        except Exception:  # hygiene: allow zipfile errors must not leave a tokenless temp file
            target.unlink(missing_ok=True)
            raise
        with self._lock:
            self._expire_locked()
            self._tokens[token] = (target, name, profile, self._clock() + TTL_SECONDS, total)
        return {"url": f"/api/download/{token}", "name": name, "count": len(entries),
                "bytes": total}

    def take(self, token: str, profile: str):
        """The ``(path, name, bytes)`` for this person's live token, removing it."""
        with self._lock:
            self._expire_locked()
            item = self._tokens.get(token)
            if item is None or item[2] != profile:
                return None
            self._tokens.pop(token, None)
        path, name, _, expires, total = item
        if expires < self._clock():
            path.unlink(missing_ok=True)
            return None
        return path, name, total

    def _expire_locked(self) -> None:
        now = self._clock()
        for token, (path, _, _, expires, _) in list(self._tokens.items()):
            if expires < now:
                self._tokens.pop(token, None)
                path.unlink(missing_ok=True)
