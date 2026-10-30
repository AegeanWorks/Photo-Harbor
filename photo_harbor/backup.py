"""A second copy of the library's originals on another drive, so one disk failure loses nothing."""

import hashlib
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .atomic_file import replace_with_retry
from .errors import HarborError

DAY_SECONDS = 24 * 3600
HASH_BLOCK = 1024 * 1024


@dataclass(frozen=True)
class BackupReport:
    copied: int
    unchanged: int
    bytes_copied: int


@dataclass(frozen=True)
class VerifyReport:
    checked: int
    missing: int
    different: int
    extra: int
    bytes_checked: int
    problems: tuple

    @property
    def ok(self) -> bool:
        return self.missing == 0 and self.different == 0


@dataclass(frozen=True)
class BackupStatus:
    target: Path
    last_at: Optional[str] = None
    copied: int = 0
    unchanged: int = 0
    bytes_copied: int = 0
    error: Optional[str] = None


def _refuse_inside(source: Path, target: Path) -> None:
    if target.resolve() == source.resolve() or source.resolve() in target.resolve().parents:
        raise HarborError(f"{target} is inside the library",
                          "a backup in the same folder dies with the same disk",
                          "choose a folder on another drive, e.g. E:\\HarborBackup")


def _files(root: Path):
    """Every visible file below ``root``, skipping Harbor's dot folders."""
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part.startswith(".")
                                      for part in path.relative_to(root).parts):
            yield path


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(HASH_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(source: Path, target: Path) -> VerifyReport:
    """Re-hash every source original against its backup copy; extras there are reported only."""
    _refuse_inside(source, target)
    if not target.is_dir():
        raise HarborError(f"{target} is not a folder",
                          "no backup exists there yet",
                          "run `python -m photo_harbor backup --to <folder>` first")
    checked = missing = different = extra = total = 0
    problems = []
    source_files = {}
    for path in _files(source):
        rel = path.relative_to(source)
        source_files[rel] = path
        checked += 1
        total += path.stat().st_size
        dest = target / rel
        if not dest.is_file():
            missing += 1
            kind = "missing"
        elif dest.stat().st_size != path.stat().st_size:
            different += 1
            kind = "different"
        elif _digest(path) != _digest(dest):
            different += 1
            kind = "different"
        else:
            continue
        if len(problems) < 50:
            problems.append((str(rel), kind))
    for path in _files(target):
        if path.relative_to(target) not in source_files:
            extra += 1
    return VerifyReport(checked=checked, missing=missing, different=different, extra=extra,
                        bytes_checked=total, problems=tuple(problems))


def mirror(source: Path, target: Path) -> BackupReport:
    """Copy each original missing from ``target`` or differing in size; never deletes there."""
    _refuse_inside(source, target)
    copied = unchanged = total = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        dest = target / path.relative_to(source)
        size = path.stat().st_size
        if dest.is_file() and dest.stat().st_size == size:
            unchanged += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".tmp_{dest.name}")
        shutil.copyfile(path, tmp)
        with open(tmp, "rb+") as handle:
            os.fsync(handle.fileno())
        replace_with_retry(tmp, dest)
        copied += 1
        total += size
    return BackupReport(copied, unchanged, total)


class DailyBackup:
    """Mirrors at start-up and every 24 hours on a background thread while the server runs."""

    def __init__(self, source: Path, target: Path, log=print) -> None:
        self._source = source
        self._target = target
        self._log = log
        self._stop = threading.Event()
        self._status_lock = threading.Lock()
        self._status = BackupStatus(target)
        self._thread = threading.Thread(target=self._run, name="harbor-backup", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def status(self) -> BackupStatus:
        with self._status_lock:
            return self._status

    def run_once(self) -> BackupStatus:
        now = datetime.now().isoformat(timespec="seconds")
        try:
            report = mirror(self._source, self._target)
            status = BackupStatus(self._target, now, report.copied, report.unchanged,
                                  report.bytes_copied)
            self._log(f"Backup: {report.copied} copied, {report.unchanged} already there "
                      f"-> {self._target}")
        except (OSError, HarborError) as error:
            status = BackupStatus(self._target, now, error=str(error))
            self._log(f"Backup failed: {error}. It retries in 24 hours.")
        with self._status_lock:
            self._status = status
        return status

    def _run(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(DAY_SECONDS)
