"""Immutable values passed between the store, the catalog and the web layer."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PhotoRecord:
    """One stored original, identified by the SHA-256 of its bytes."""

    sha256: str
    rel_path: str
    size: int
    original_name: str
    media_type: str
    taken_at: Optional[str]
    received_at: str

    @property
    def sort_time(self) -> str:
        return self.taken_at or self.received_at

    @property
    def is_video(self) -> bool:
        return self.media_type.startswith("video/")


@dataclass(frozen=True)
class UploadClaim:
    """What the phone says about a file before its bytes are checked."""

    original_name: str
    sha256: Optional[str] = None
    taken_at: Optional[str] = None
    modified_at: Optional[str] = None


@dataclass(frozen=True)
class IngestResult:
    """``status`` is ``stored`` for a new file or ``duplicate`` when the bytes were already held."""

    status: str
    record: PhotoRecord


@dataclass(frozen=True)
class LibraryStats:
    count: int
    total_bytes: int
    last_received: Optional[str]


@dataclass(frozen=True)
class PhotoFilter:
    """Gallery narrowing: ``month`` is ``YYYY-MM``, ``query`` matches the file name, ``kind`` is
    ``photo`` or ``video``; None means no narrowing on that axis."""

    month: Optional[str] = None
    query: Optional[str] = None
    kind: Optional[str] = None


@dataclass(frozen=True)
class Outline:
    """What the browser sidebar lists: ``(YYYY-MM, count)`` newest first, and the video count."""

    months: tuple
    videos: int
