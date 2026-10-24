"""Crash-safe file placement: temp file, fsync, atomic replace, directory fsync."""

import os
import shutil
import time
from pathlib import Path

REPLACE_TRIES = 5


def write_atomic(path: Path, data: bytes, keep_backup: bool = False) -> None:
    """Replace ``path`` with ``data`` so a power cut leaves the old or the new file, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".tmp_{path.name}.{os.getpid()}")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if keep_backup and path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    replace_with_retry(tmp, path)
    fsync_dir(path.parent)


def replace_with_retry(src: Path, dst: Path) -> None:
    """os.replace, retried because Windows briefly locks files that a scanner has open."""
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def fsync_dir(directory: Path) -> None:
    """Persist a directory entry; Windows cannot open a directory, and NTFS journals it anyway."""
    if os.name == "nt":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
