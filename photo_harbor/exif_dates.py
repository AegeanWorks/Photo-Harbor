"""The capture time stored inside a photo, for uploads that arrive without one (browser uploads)."""

from pathlib import Path
from typing import Optional

from .pillow_support import load_image

DATETIME_ORIGINAL = 0x9003
EXIF_IFD = 0x8769
DATETIME = 0x0132


def read_taken(path: Path) -> Optional[str]:
    """``YYYY-MM-DDTHH:MM:SS`` from EXIF DateTimeOriginal, or None without Pillow or a date."""
    Image = load_image()
    if Image is None:
        return None
    try:
        # hygiene: allow Pillow's Image.open reads binary image data, not text
        with Image.open(path) as image:
            exif = image.getexif()
            value = exif.get_ifd(EXIF_IFD).get(DATETIME_ORIGINAL) or exif.get(DATETIME)
    except Exception:  # hygiene: allow Pillow raises many types for files it cannot parse
        return None
    if not isinstance(value, str) or len(value) < 19:
        return None
    return f"{value[0:4]}-{value[5:7]}-{value[8:10]}T{value[11:19]}"
