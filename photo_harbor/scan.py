"""Keeping the catalog in step with the folders, and checking that every file is still intact.

People may add, move or delete photos in File Explorer. ``reconcile`` notices: a new file in a
person's folder joins their photos, a moved file keeps its place in the catalog, and a deleted
file leaves it. ``check`` re-reads every file and reports any whose bytes no longer match.
"""

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from .catalog import Catalog
from .copies import CopyIndex
from .database import Database
from .exif_dates import read_taken
from .importer import MEDIA_SUFFIXES
from .journal import SyncJournal
from .naming import media_type, parse_taken
from .profiles import ProfileBook
from .records import PhotoRecord
from .store import PhotoStore, hash_file

SETTLE_SECONDS = 120          # a file changed this recently may still be copying in
RECONCILE_EVERY = 6 * 3600
CHECK_EVERY = timedelta(days=7)
SCANNED, CHECKED, REMOVED, DAMAGED = "scanned", "checked", "removed", "damaged"
# More missing than this at once looks like an unplugged or renamed drive, not deletions.
MASS_MISSING = 50
MASS_MISSING_SHARE = 0.10


@dataclass(frozen=True)
class ScanReport:
    added: int
    moved: int
    removed: int
    held_back: int = 0


@dataclass(frozen=True)
class CheckReport:
    checked: int
    damaged: tuple


def _stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class LibraryScanner:
    def __init__(self, root: Path, db: Database, catalog: Catalog, copies: CopyIndex,
                 profiles: ProfileBook, store: PhotoStore, journal: SyncJournal,
                 now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
                 clock: Callable[[], float] = time.time) -> None:
        self._root = root
        self._db = db
        self._catalog = catalog
        self._copies = copies
        self._profiles = profiles
        self._store = store
        self._journal = journal
        self._now = now
        self._clock = clock

    def reconcile(self, stop: Optional[threading.Event] = None) -> ScanReport:
        added = moved = removed = 0
        if not self._root.is_dir():
            return ScanReport(0, 0, 0, held_back=-1)
        tracked = self._tracked()
        missing = {rel: key for rel, key in tracked.items() if not (self._root / rel).is_file()}
        for profile in self._profiles.all():
            for path in self._media_in(self._root / profile.folder):
                rel = path.relative_to(self._root).as_posix()
                if rel in tracked:
                    continue
                if stop is not None and stop.is_set():
                    return ScanReport(added, moved, 0)
                outcome = self._register(profile.id, path, rel, missing)
                added += outcome == "added"
                moved += outcome == "moved"
        if len(missing) > MASS_MISSING and len(missing) > MASS_MISSING_SHARE * len(tracked):
            self._journal.record(_stamp(self._now()), SCANNED, None,
                                 f"{len(missing)} files missing at once: none removed")
            return ScanReport(added, moved, 0, held_back=len(missing))
        for rel, (profile, sha) in missing.items():
            if (self._root / rel).is_file():
                continue
            with self._store.lock:
                if self._copies.path_for(profile, sha) == rel:
                    self._copies.forget(profile, sha)
                    self._journal.record(_stamp(self._now()), REMOVED, sha, rel, profile)
                    removed += 1
        self._journal.record(_stamp(self._now()), SCANNED, None,
                             f"{added} added, {moved} moved, {removed} removed")
        return ScanReport(added, moved, removed)

    def check(self, stop: Optional[threading.Event] = None) -> CheckReport:
        """Re-hash every catalogued file; damaged ones are reported, never deleted."""
        damaged = []
        checked = 0
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT c.rel_path, c.sha256, c.profile, p.size FROM copies c"
                " JOIN photos p ON p.sha256 = c.sha256 ORDER BY c.rel_path").fetchall()
        for row in rows:
            if stop is not None and stop.is_set():
                break
            path = self._root / row["rel_path"]
            try:
                intact = path.stat().st_size == row["size"] and hash_file(path) == row["sha256"]
            except OSError:
                continue  # missing files are reconcile's business
            checked += 1
            if not intact:
                damaged.append(row["rel_path"])
                self._journal.record(_stamp(self._now()), DAMAGED, row["sha256"],
                                     row["rel_path"], row["profile"])
        self._journal.record(_stamp(self._now()), CHECKED, None,
                             f"{checked} checked, {len(damaged)} damaged")
        return CheckReport(checked, tuple(damaged))

    # ---------- helpers ----------

    def _tracked(self) -> dict:
        with self._db.lock:
            rows = self._db.conn.execute("SELECT rel_path, profile, sha256 FROM copies").fetchall()
        return {row[0]: (row[1], row[2]) for row in rows}

    def _media_in(self, folder: Path):
        settled_before = self._clock() - SETTLE_SECONDS
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                path = Path(root) / name
                if name.startswith((".", "~$")) or path.suffix.lower() not in MEDIA_SUFFIXES:
                    continue
                try:
                    if path.stat().st_mtime <= settled_before:
                        yield path
                except OSError:
                    continue

    def _register(self, profile: str, path: Path, rel: str, missing: dict) -> str:
        """An untracked file in ``profile``'s folder: a moved copy, a new copy, or a new photo."""
        try:
            sha = hash_file(path)
            size = path.stat().st_size
        except OSError:
            return "skipped"
        with self._store.lock:
            own = self._copies.path_for(profile, sha)
            if own is not None:
                if own in missing:
                    self._copies.move(own, rel)
                    missing.pop(own)
                    return "moved"
                return "skipped"  # a second file with the same bytes in the same folder
            known = self._catalog.get(sha)
            if known is not None:
                self._copies.add(profile, known, rel, path.name, _stamp(self._now()))
                return "added"
            taken = parse_taken(read_taken(path)) or datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc).astimezone()
            self._catalog.add(PhotoRecord(
                sha256=sha, rel_path=rel, size=size, original_name=path.name,
                media_type=media_type(path.name), taken_at=_stamp(taken),
                received_at=_stamp(self._now()), profile=profile))
            return "added"


class ScanSchedule:
    """Reconciles at start and every 6 hours; checks every file when the last full check is a
    week old. One background thread; ``run_now`` asks for an extra pass."""

    def __init__(self, scanner: LibraryScanner, journal: SyncJournal,
                 log: Callable[[str], None] = print) -> None:
        self._scanner = scanner
        self._journal = journal
        self.log = log
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._full = False
        self._thread = threading.Thread(target=self._run, name="harbor-scan", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def run_now(self, full: bool = False) -> None:
        self._full = self._full or full
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def _due_check(self) -> bool:
        """A full re-read is heavy: the first one comes a week after Harbor first ran."""
        now = datetime.now().astimezone()
        last = parse_taken(self._journal.last_event(CHECKED))
        if last is None:
            self._journal.record(_stamp(now), CHECKED, None, "first check scheduled in a week")
            return False
        if last.tzinfo is None:
            last = last.astimezone()
        return now - last >= CHECK_EVERY

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._pass()
            except (sqlite3.Error, OSError) as error:
                if self._stop.is_set():
                    return  # the server closed the catalog while a pass was running
                self.log(f"Folder scan failed: {error}. It runs again in 6 hours.")
            self._wake.wait(RECONCILE_EVERY)
            self._wake.clear()

    def _pass(self) -> None:
        report = self._scanner.reconcile(self._stop)
        if report.held_back > 0:
            self.log(f"{report.held_back} files are missing at once; is the library drive "
                      "connected? Nothing was removed.")
        if report.added or report.moved or report.removed:
            self.log(f"Folders: {report.added} added, {report.moved} moved, "
                      f"{report.removed} removed.")
        if not self._stop.is_set() and (self._full or self._due_check()):
            self._full = False
            result = self._scanner.check(self._stop)
            self.log(f"File check: {result.checked} files, {len(result.damaged)} damaged.")
            for rel in result.damaged[:10]:
                self.log(f"Damaged: {rel} (send it again from the phone to repair it)")
