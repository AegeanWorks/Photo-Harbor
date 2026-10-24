"""Bringing photos already on the PC's disk into a profile, without touching the source folder."""

import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .database import Database
from .errors import HarborError
from .records import UploadClaim
from .store import PhotoStore

MEDIA_SUFFIXES = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".dng", ".bmp",
    ".mov", ".mp4", ".m4v", ".avi", ".3gp", ".mkv",
})


@dataclass(frozen=True)
class ImportReport:
    stored: int
    duplicate: int
    failed: int
    errors: tuple

    @property
    def summary(self) -> str:
        return (f"{self.stored} added, {self.duplicate} already in Harbor, "
                f"{self.failed} could not be read")


class ImportLedger:
    """Source files already imported, by path, size and modification time. A file that is
    unchanged since, and whose photo is still in the library, is skipped without being read."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def known(self, source: Path, size: int, mtime_ns: int) -> Optional[str]:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT sha256 FROM imported_files WHERE source = ? AND size = ? AND mtime_ns = ?",
                (str(source), size, mtime_ns),
            ).fetchone()
        return row[0] if row else None

    def remember(self, source: Path, size: int, mtime_ns: int, sha256: str) -> None:
        with self._db.lock:
            self._db.conn.execute(
                "INSERT OR REPLACE INTO imported_files (source, size, mtime_ns, sha256)"
                " VALUES (?, ?, ?, ?)", (str(source), size, mtime_ns, sha256),
            )


def find_media(folder: Path, library: Path) -> list:
    """Photos and videos under ``folder``, sorted; the Harbor library itself is skipped."""
    source, own = folder.resolve(), library.resolve()
    if source == own or own in source.parents:
        raise HarborError(f"{folder} is inside the Harbor library",
                          "importing the library into itself would copy nothing new",
                          "choose a folder outside it, such as an old phone backup")
    found = []
    for root, dirs, files in os.walk(source):
        here = Path(root)
        dirs[:] = sorted(d for d in dirs if (here / d).resolve() != own and not d.startswith("."))
        found.extend(here / name for name in sorted(files)
                     if Path(name).suffix.lower() in MEDIA_SUFFIXES)
    return found


def _modified(stat: os.stat_result) -> str:
    return datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds")


def import_folder(store: PhotoStore, folder: Path, library: Path, profile: str,
                  progress: Optional[Callable[[int, int, Path], None]] = None,
                  stop: Optional[threading.Event] = None,
                  ledger: Optional[ImportLedger] = None) -> ImportReport:
    """Copy each photo in; each file is hashed by the store, so re-running adds only new ones.
    With a ``ledger``, files imported before and unchanged since are not even read."""
    files = find_media(folder, library)
    stored = duplicate = failed = 0
    errors = []
    for index, path in enumerate(files):
        if stop is not None and stop.is_set():
            break
        if progress is not None:
            progress(index, len(files), path)
        try:
            stat = path.stat()
            seen = ledger.known(path, stat.st_size, stat.st_mtime_ns) if ledger else None
            if seen is not None and store.locate(seen, profile) is not None:
                duplicate += 1  # already in this person's folder: not even read
                continue
            claim = UploadClaim(original_name=path.name, modified_at=_modified(stat), profile=profile)
            with open(path, "rb") as handle:
                result = store.ingest(handle, stat.st_size, claim)
        except (OSError, HarborError) as error:
            failed += 1
            errors.append(f"{path}: {getattr(error, 'message', error)}")
            continue
        if ledger is not None:
            ledger.remember(path, stat.st_size, stat.st_mtime_ns, result.record.sha256)
        if result.status == "stored":
            stored += 1
        else:
            duplicate += 1
    if progress is not None:
        progress(len(files), len(files), folder)
    return ImportReport(stored, duplicate, failed, tuple(errors[:50]))
