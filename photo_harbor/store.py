"""Receives originals, proves their bytes against the phone's hash, and re-proves them on request.

Files live in plain folders a person can open in File Explorer: ``<Person>/<YYYY>/<YYYY-MM>/``.
A photo two people own is one file with two names (an NTFS hard link), so it costs no extra space.
"""

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
from .copies import CopyIndex
from .exif_dates import read_taken
from .errors import HarborError
from .naming import media_type, month_folder, parse_taken, safe_name
from .records import IngestResult, PhotoRecord, UploadClaim

CHUNK = 4 << 20
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


def link_or_copy(source: Path, target: Path) -> None:
    """A second name for the same file (no extra space); a real copy where links are refused."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        tmp = target.with_name(f".tmp_{target.name}")
        shutil.copyfile(source, tmp)
        replace_with_retry(tmp, target)
    fsync_dir(target.parent)


def _stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class PhotoStore:
    def __init__(self, library: Path, catalog: Catalog, copies: CopyIndex,
                 folder_of: Callable[[str], str] = lambda profile: profile,
                 now: Callable[[], datetime] = local_now,
                 embedded_date: Callable[[Path], Optional[str]] = read_taken,
                 on_stored: Optional[Callable[[PhotoRecord], None]] = None) -> None:
        """``folder_of`` maps a profile id to that person's folder name in the library."""
        self.root = library
        self._incoming = library / ".harbor" / "incoming"
        self._catalog = catalog
        self._copies = copies
        self._folder_of = folder_of
        self._now = now
        self._embedded_date = embedded_date
        self.on_stored = on_stored
        # Held while a file is placed, linked, moved or registered: one change at a time.
        self.lock = threading.RLock()
        self._incoming.mkdir(parents=True, exist_ok=True)
        for stale in self._incoming.glob(".tmp_upload_*"):
            stale.unlink(missing_ok=True)

    def ingest(self, stream: BinaryIO, length: Optional[int], claim: UploadClaim) -> IngestResult:
        """Stream ``length`` bytes (None: until the stream ends) to disk; keep them only when the
        hash matches the claim. ``on_stored`` hears about every newly stored or repaired file."""
        expected = normalise_sha(claim.sha256)
        self._check_capacity(length)
        tmp = self._incoming / f".tmp_upload_{uuid.uuid4().hex}"
        try:
            actual, size = self._receive(stream, length, tmp)
            if expected is not None and actual != expected:
                raise HarborError("the photo arrived different from what the phone sent",
                                  "the SHA-256 of the received bytes does not match the phone's",
                                  "nothing was kept; the next sync sends it again", status=422)
            result = self._place(tmp, actual, size, claim)
        finally:
            tmp.unlink(missing_ok=True)
        if result.status == "stored" and self.on_stored is not None:
            self.on_stored(result.record)
        return result

    def verify(self, sha256: str) -> bool:
        """True only when some catalogued copy exists and its bytes still hash to ``sha256``."""
        return self._intact(sha256) is not None

    def locate(self, sha256: str, profile: Optional[str] = None) -> Optional[tuple]:
        """``(path, record)`` of ``profile``'s copy, or of any copy when no profile is given."""
        record = self._catalog.get(sha256)
        if record is None:
            return None
        rel = self._copies.path_for(profile, sha256) if profile else record.rel_path
        if rel is None:
            return None
        path = self.root / rel
        if path.is_file():
            return path, record
        if profile is None:
            for _, other in self._copies.paths_of(sha256):
                if (self.root / other).is_file():
                    return self.root / other, record
        return None

    def ensure_copy(self, profile: str, sha256: str) -> bool:
        """Make sure ``profile``'s folder holds this photo, linking it from another person's
        verified copy if needed. False when no intact copy exists on this PC."""
        source = self._intact(sha256)
        if source is None:
            return False
        with self.lock:
            own = self._copies.path_for(profile, sha256)
            if own is not None:
                if not (self.root / own).is_file():
                    link_or_copy(source, self.root / own)
                return True
            record = self._catalog.get(sha256)
            self._link_new_copy(source, record, profile, record.original_name)
            return True

    # ---------- receiving ----------

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

    # ---------- placing ----------

    def _place(self, tmp: Path, sha256: str, size: int, claim: UploadClaim) -> IngestResult:
        # The phone's date wins; then the date inside the file; then the browser's file date.
        taken = (parse_taken(claim.taken_at) or parse_taken(self._embedded_date(tmp))
                 or parse_taken(claim.modified_at))
        if taken is not None and taken.tzinfo is not None:
            taken = taken.astimezone()
        received = self._now()
        with self.lock:
            existing = self._catalog.get(sha256)
            if existing is not None:
                return self._known(tmp, existing, claim)
            for target in self.candidate_paths(claim.profile, taken or received, claim.original_name,
                                           sha256):
                replace_with_retry(tmp, target)
                fsync_dir(target.parent)
                record = PhotoRecord(
                    sha256=sha256, rel_path=self._rel(target), size=size,
                    original_name=claim.original_name[:255],
                    media_type=media_type(safe_name(claim.original_name)),
                    taken_at=_stamp(taken) if taken else None, received_at=_stamp(received),
                    profile=claim.profile,
                )
                try:
                    added = self._catalog.add(record)
                except sqlite3.IntegrityError:
                    replace_with_retry(target, tmp)
                    continue
                if not added:
                    # Another process (a CLI import) catalogued the same bytes meanwhile.
                    target.unlink(missing_ok=True)
                    return IngestResult("duplicate", self._catalog.get(sha256) or record)
                return IngestResult("stored", record)
        raise HarborError(f"no free file name for {claim.original_name}",
                          "every candidate name is taken", "rename the photo and send it again",
                          status=409)

    def _known(self, tmp: Path, existing: PhotoRecord, claim: UploadClaim) -> IngestResult:
        """Bytes the library already has: repair a damaged copy, or give this person their own."""
        source = self._intact(existing.sha256)
        repaired = source is None
        if source is None:
            source = self.root / existing.rel_path
            source.parent.mkdir(parents=True, exist_ok=True)
            replace_with_retry(tmp, source)
            fsync_dir(source.parent)
            # Hard links shared the damaged bytes: point every other copy at the repaired file.
            for _, rel in self._copies.paths_of(existing.sha256):
                if self.root / rel != source:
                    (self.root / rel).unlink(missing_ok=True)
                    link_or_copy(source, self.root / rel)
        own = self._copies.path_for(claim.profile, existing.sha256)
        if own is None:
            return IngestResult("stored", self._link_new_copy(source, existing, claim.profile,
                                                              claim.original_name[:255]))
        if not (self.root / own).is_file():
            link_or_copy(source, self.root / own)
            repaired = True
        mine = PhotoRecord(**{**existing.__dict__, "rel_path": own, "profile": claim.profile})
        return IngestResult("stored" if repaired else "duplicate", mine)

    def _link_new_copy(self, source: Path, record: PhotoRecord, profile: str,
                       name: str) -> PhotoRecord:
        moment = parse_taken(record.sort_time) or self._now()
        for target in self.candidate_paths(profile, moment, name, record.sha256):
            link_or_copy(source, target)
            try:
                added = self._copies.add(profile, record, self._rel(target), name,
                                         _stamp(self._now()))
            except sqlite3.IntegrityError:
                added = False  # that path belongs to another photo: try the next name
            if added:
                return PhotoRecord(**{**record.__dict__, "rel_path": self._rel(target),
                                      "original_name": name, "profile": profile})
            target.unlink(missing_ok=True)
        raise HarborError(f"no free file name for {name}", "every candidate name is taken",
                          "rename the photo and send it again", status=409)

    def candidate_paths(self, profile: str, moment: datetime, original: str, sha256: str):
        """Free paths in the person's month folder: the name, then the name with a hash suffix."""
        folder = self.root / self._folder_of(profile) / month_folder(moment)
        folder.mkdir(parents=True, exist_ok=True)
        name = safe_name(original)
        stem, suffix = Path(name).stem, Path(name).suffix
        for candidate in (name, f"{stem}-{sha256[:8]}{suffix}", f"{stem}-{sha256}{suffix}"):
            if not (folder / candidate).exists():
                yield folder / candidate

    def _intact(self, sha256: str) -> Optional[Path]:
        """The first copy whose size and SHA-256 still match, or None."""
        record = self._catalog.get(sha256)
        if record is None:
            return None
        seen = set()
        for rel in [record.rel_path] + [rel for _, rel in self._copies.paths_of(sha256)]:
            if rel in seen:
                continue
            seen.add(rel)
            path = self.root / rel
            try:
                if path.stat().st_size == record.size and hash_file(path) == sha256:
                    return path
            except OSError:
                continue
        return None

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()
