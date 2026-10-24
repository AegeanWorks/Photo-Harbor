"""Where an original lands on disk: a safe file name inside a YYYY/MM folder."""

import mimetypes
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Optional

MAX_STEM = 100
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)),
             *(f"LPT{n}" for n in range(1, 10))}
_EXTRA_TYPES = {".heic": "image/heic", ".heif": "image/heif", ".mov": "video/quicktime",
                ".dng": "image/x-adobe-dng", ".m4v": "video/x-m4v"}


def safe_name(original: str) -> str:
    """A Windows-safe base name; a name that sanitises to nothing becomes ``photo``."""
    base = PurePosixPath(original.replace("\\", "/")).name
    base = _FORBIDDEN.sub("_", base).strip(" .")
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = stem[:MAX_STEM] or "photo"
    if stem.upper() in _RESERVED:
        stem = f"_{stem}"
    return f"{stem}.{ext.lower()}" if ext else stem


def parse_taken(value: Optional[str]) -> Optional[datetime]:
    """ISO 8601 as Shortcuts formats it; anything unreadable counts as unknown."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def month_folder(moment: datetime) -> str:
    return f"{moment.year:04d}/{moment.month:02d}"


def media_type(name: str) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in _EXTRA_TYPES:
        return _EXTRA_TYPES[suffix]
    return mimetypes.guess_type(name)[0] or "application/octet-stream"
