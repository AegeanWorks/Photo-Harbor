"""A second copy of the library's originals on another drive, so one disk failure loses nothing."""

import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from .atomic_file import replace_with_retry
from .errors import HarborError

DAY_SECONDS = 24 * 3600


@dataclass(frozen=True)
class BackupReport:
    copied: int
    unchanged: int
    bytes_copied: int


def mirror(source: Path, target: Path) -> BackupReport:
    """Copy each original missing from ``target`` or differing in size; never deletes there."""
    if target.resolve() == source.resolve() or source.resolve() in target.resolve().parents:
        raise HarborError(f"{target} is inside the library",
                          "a backup in the same folder dies with the same disk",
                          "choose a folder on another drive, e.g. E:\\HarborBackup")
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
        self._thread = threading.Thread(target=self._run, name="harbor-backup", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                report = mirror(self._source, self._target)
                self._log(f"Backup: {report.copied} copied, {report.unchanged} already there "
                          f"-> {self._target}")
            except (OSError, HarborError) as error:
                self._log(f"Backup failed: {error}. It retries in 24 hours.")
            self._stop.wait(DAY_SECONDS)
