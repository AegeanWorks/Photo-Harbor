"""Crash-safe file placement: temp file, fsync, atomic replace, directory fsync, and exclusive
placement that never overwrites a name another writer already holds."""

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


def copy_exclusive(source: Path, target: Path) -> None:
    """Copy ``source`` to ``target`` only when that name is free; a failed copy leaves nothing."""
    try:
        with open(target, "xb") as out, open(source, "rb") as handle:
            shutil.copyfileobj(handle, out, 1 << 20)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError:
        raise
    except OSError:
        try:
            target.unlink()
        # hygiene: allow [silent-except] scanner may still hold the partial copy; the copy error wins
        except OSError:
            pass
        raise


def place_exclusive(source: Path, target: Path) -> None:
    """Give ``target`` the bytes of ``source`` only when the name is free, then remove ``source``.
    ``FileExistsError`` leaves both files untouched, so a rival caller never loses its file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except FileExistsError:
        raise
    except OSError:
        copy_exclusive(source, target)
    try:
        source.unlink()
    except OSError:  # hygiene: allow the caller's own temp cleanup to finish the job
        pass
    fsync_dir(target.parent)


def fsync_dir(directory: Path) -> None:
    """Persist a directory entry; Windows cannot open a directory, and NTFS journals it anyway."""
    if os.name == "nt":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
