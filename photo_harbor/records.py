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
    profile: str = "main"
    favorite: bool = False

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
    profile: str = "main"


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
    ``photo`` or ``video``. ``viewer`` is whose favorites and albums are read; ``favorite`` and
    ``album`` narrow to that viewer's marks. None means no narrowing on that axis."""

    month: Optional[str] = None
    query: Optional[str] = None
    kind: Optional[str] = None
    profile: Optional[str] = None
    viewer: str = "main"
    favorite: bool = False
    album: Optional[int] = None


@dataclass(frozen=True)
class Outline:
    """What the browser sidebar lists: ``(YYYY-MM, count)`` newest first, the video count and the
    viewer's favorites."""

    months: tuple
    videos: int
    favorites: int = 0


@dataclass(frozen=True)
class Album:
    """One person's named collection; ``cover`` is the newest member's SHA-256, if any."""

    id: int
    name: str
    count: int = 0
    cover: Optional[str] = None


@dataclass(frozen=True)
class PersonStorage:
    """One person's share: shared photos count in each person's share."""

    profile: str
    count: int
    bytes: int


@dataclass(frozen=True)
class StorageFile:
    """One row of the largest-files list."""

    sha256: str
    name: str
    size: int
    time: Optional[str]


@dataclass(frozen=True)
class StorageReport:
    """Disk use for one profile, or for the whole library when ``profile`` is None."""

    count: int
    bytes: int
    photos: int
    videos: int
    shared: int
    largest: tuple
    people: tuple = ()


@dataclass(frozen=True)
class Profile:
    """A person: ``folder`` is their folder in the library, ``key`` is what their Shortcut sends."""

    id: str
    name: str
    key: str
    folder: str = ""


@dataclass(frozen=True)
class Identity:
    """Who a request comes from; the owner (library key) may manage every profile."""

    profile: str
    owner: bool
