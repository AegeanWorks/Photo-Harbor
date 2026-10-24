"""Receives originals, proves their bytes against the phone's hash, and re-proves them on request."""

import hashlib
import os
import re
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Callable, Optional

from .atomic_file import fsync_dir, replace_with_retry
from .catalog import Catalog
from .exif_dates import read_taken
from .errors import HarborError
from .naming import media_type, month_folder, parse_taken, safe_name
from .records import IngestResult, PhotoRecord, UploadClaim

CHUNK = 1 << 20
MIN_FREE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_BYTES = 16 * 1024 ** 3
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def local_now() -> datetime:
    return datetime.now().astimezone()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def normalise_sha(value: Optional[str]) -> Optional[str]:
    """Lower-case hex, or HarborError when the text is not a SHA-256."""
    if value is None or value.strip() == "":
        return None
    cleaned = value.strip().lower()
    if not SHA256_HEX.match(cleaned):
        raise HarborError("the hash is not a SHA-256 hex string",
                          f"got {len(cleaned)} characters, expected 64 of 0-9a-f",
                          "set the Shortcut's Generate Hash action to SHA256")
    return cleaned


class PhotoStore:
    def __init__(self, library: Path, catalog: Catalog,
                 now: Callable[[], datetime] = local_now,
                 embedded_date: Callable[[Path], Optional[str]] = read_taken) -> None:
        self.photos_dir = library / "photos"
        self._incoming = library / ".harbor" / "incoming"
        self._catalog = catalog
        self._now = now
        self._embedded_date = embedded_date
        self._place_lock = threading.Lock()
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self._incoming.mkdir(parents=True, exist_ok=True)
        for stale in self._incoming.glob(".tmp_upload_*"):
            stale.unlink(missing_ok=True)

    def ingest(self, stream: BinaryIO, length: Optional[int], claim: UploadClaim) -> IngestResult:
        """Stream ``length`` bytes (None: until the stream ends) to disk; keep them only when the
        hash matches the claim."""
        expected = normalise_sha(claim.sha256)
        self._check_capacity(length)
        tmp = self._incoming / f".tmp_upload_{uuid.uuid4().hex}"
        try:
            actual, size = self._receive(stream, length, tmp)
            if expected is not None and actual != expected:
                raise HarborError("the photo arrived different from what the phone sent",
                                  "the SHA-256 of the received bytes does not match the phone's",
                                  "nothing was kept; the next sync sends it again", status=422)
            return self._place(tmp, actual, size, claim)
        finally:
            tmp.unlink(missing_ok=True)

    def verify(self, sha256: str) -> bool:
        """True only when the catalogued file exists and its bytes still hash to ``sha256``."""
        record = self._catalog.get(sha256)
        if record is None:
            return False
        path = self.photos_dir / record.rel_path
        try:
            if path.stat().st_size != record.size:
                return False
            return hash_file(path) == sha256
        except OSError:
            return False

    def locate(self, sha256: str) -> Optional[tuple]:
        """``(path, record)`` of a stored original, or None."""
        record = self._catalog.get(sha256)
        if record is None:
            return None
        path = self.photos_dir / record.rel_path
        return (path, record) if path.is_file() else None

    def _check_capacity(self, length: Optional[int]) -> None:
        if length is None:
            length = 0
        elif length <= 0 or length > MAX_UPLOAD_BYTES:
            raise HarborError(f"an upload of {length} bytes was refused",
                              f"uploads must be 1 byte to {MAX_UPLOAD_BYTES} bytes",
                              "send the file as the request body with its Content-Length",
                              status=413 if length > 0 else 411)
        free = shutil.disk_usage(self._incoming).free
        if free < length + MIN_FREE_BYTES:
            raise HarborError("the PC's photo drive is full",
                              f"{free} bytes free, {length + MIN_FREE_BYTES} needed",
                              "free space on the library drive, then sync again", status=507)

    def _receive(self, stream: BinaryIO, length: Optional[int], tmp: Path) -> tuple:
        digest = hashlib.sha256()
        received = 0
        limit = MAX_UPLOAD_BYTES if length is None else length
        with open(tmp, "wb") as handle:
            while received < limit:
                try:
                    block = stream.read(min(CHUNK, limit - received))
                except OSError as exc:
                    raise HarborError("the upload stopped early", f"the connection failed: {exc}",
                                      "keep the phone on Wi-Fi; the next sync sends it again") from exc
                if not block:
                    break
                digest.update(block)
                handle.write(block)
                received += len(block)
            handle.flush()
            os.fsync(handle.fileno())
        if length is None and received == limit and stream.read(1):
            raise HarborError("an upload was refused", f"it is larger than {MAX_UPLOAD_BYTES} bytes",
                              "send files smaller than 16 GiB", status=413)
        if received == 0 or (length is not None and received < length):
            raise HarborError("the upload stopped early",
                              f"{received} of {length if length is not None else 'some'} bytes arrived",
                              "keep the phone on Wi-Fi; the next sync sends it again")
        return digest.hexdigest(), received

    def _place(self, tmp: Path, sha256: str, size: int, claim: UploadClaim) -> IngestResult:
        # The phone's date wins; then the date inside the file; then the browser's file date.
        taken = (parse_taken(claim.taken_at) or parse_taken(self._embedded_date(tmp))
                 or parse_taken(claim.modified_at))
        if taken is not None and taken.tzinfo is not None:
            taken = taken.astimezone()
        received = self._now()
        name = safe_name(claim.original_name)
        with self._place_lock:
            existing = self._catalog.get(sha256)
            if existing is not None:
                if self.verify(sha256):
                    return IngestResult("duplicate", existing)
                return IngestResult("stored", self._repair(tmp, existing))
            folder = self.photos_dir / month_folder(taken or received)
            folder.mkdir(parents=True, exist_ok=True)
            stem, suffix = Path(name).stem, Path(name).suffix
            # A name can be held on disk, or by a catalogued photo whose file is gone.
            for candidate in (name, f"{stem}-{sha256[:8]}{suffix}", f"{stem}-{sha256}{suffix}"):
                target = folder / candidate
                if target.exists():
                    continue
                replace_with_retry(tmp, target)
                fsync_dir(folder)
                record = PhotoRecord(
                    sha256=sha256,
                    rel_path=target.relative_to(self.photos_dir).as_posix(),
                    size=size,
                    original_name=claim.original_name[:255],
                    media_type=media_type(name),
                    taken_at=taken.isoformat(timespec="seconds") if taken else None,
                    received_at=received.isoformat(timespec="seconds"),
                )
                try:
                    self._catalog.add(record)
                except sqlite3.IntegrityError:
                    replace_with_retry(target, tmp)
                    continue
                return IngestResult("stored", record)
        raise HarborError(f"no free file name for {name}", "every candidate name is taken",
                          "rename the photo and send it again", status=409)

    def _repair(self, tmp: Path, record: PhotoRecord) -> PhotoRecord:
        """Put verified bytes back where a catalogued original went missing or was damaged."""
        target = self.photos_dir / record.rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        replace_with_retry(tmp, target)
        fsync_dir(target.parent)
        return record
