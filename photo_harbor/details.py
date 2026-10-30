"""File and camera facts for one original, read on demand without touching the catalog."""

from pathlib import Path
from typing import Optional

from .pillow_support import load_image
from .records import PhotoRecord

EXIF_IFD = 0x8769
MAKE = 0x010F
MODEL = 0x0110
LENS = 0xA434
EXPOSURE = 0x829A
APERTURE = 0x829D
ISO = 0x8827
FOCAL_LENGTH = 0x920A


def _text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    value = str(value).strip().strip("\x00").strip()
    return value or None


def _exposure(value) -> Optional[str]:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return _text(value)
    if seconds <= 0:
        return None
    if seconds < 1:
        return f"1/{max(round(1 / seconds), 1)} s"
    return f"{seconds:g} s"


def _aperture(value) -> Optional[str]:
    try:
        return f"f/{float(value):g}"
    except (TypeError, ValueError):
        return _text(value)


def _focal(value) -> Optional[str]:
    try:
        return f"{float(value):g} mm"
    except (TypeError, ValueError):
        return _text(value)


def _iso(value) -> Optional[str]:
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return _text(value)


def _camera(make, model) -> Optional[str]:
    make, model = _text(make), _text(model)
    if make and model:
        return model if model.lower().startswith(make.lower()) else f"{make} {model}"
    return make or model


def read_details(record: PhotoRecord, path: Path) -> dict:
    """File facts always; width, height and EXIF fields when Pillow can read them."""
    facts = {
        "name": record.original_name,
        "type": record.media_type,
        "size": record.size,
        "taken": record.taken_at,
        "received": record.received_at,
        "width": None,
        "height": None,
        "camera": None,
        "lens": None,
        "exposure": None,
        "aperture": None,
        "iso": None,
        "focal_length": None,
    }
    if record.is_video:
        return facts
    Image = load_image()
    if Image is None:
        return facts
    try:
        # hygiene: allow Pillow's Image.open reads binary image data, not text
        with Image.open(path) as image:
            width, height = image.size
            exif = image.getexif()
            try:
                exif_ifd = exif.get_ifd(EXIF_IFD)
            except Exception:  # hygiene: allow a malformed EXIF IFD point
                exif_ifd = {}

            def tag(number):
                return exif_ifd[number] if number in exif_ifd else exif.get(number)
    except Exception:  # hygiene: allow Pillow raises many types for unreadable formats
        return facts
    facts.update(width=width, height=height, camera=_camera(tag(MAKE), tag(MODEL)),
                 lens=_text(tag(LENS)), exposure=_exposure(tag(EXPOSURE)),
                 aperture=_aperture(tag(APERTURE)), iso=_iso(tag(ISO)),
                 focal_length=_focal(tag(FOCAL_LENGTH)))
    return facts
