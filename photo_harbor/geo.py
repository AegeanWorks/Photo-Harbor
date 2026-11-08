"""The camera's GPS point, read once at ingest for the Places rail."""

from pathlib import Path
from typing import Optional

from .pillow_support import load_image

GPS_IFD = 0x8825
LATITUDE_REF = 1
LATITUDE = 2
LONGITUDE_REF = 3
LONGITUDE = 4


def _number(value) -> Optional[float]:
    try:
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return float(value[0]) / float(value[1])
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _degrees(value) -> Optional[float]:
    """A GPS coordinate written as three rational degrees/minutes/seconds."""
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        return _number(value)
    parts = [_number(part) for part in value]
    if any(part is None for part in parts):
        return None
    degrees, minutes, seconds = parts
    return degrees + minutes / 60 + seconds / 3600


def _point(gps) -> Optional[tuple]:
    lat = _degrees(gps.get(LATITUDE))
    lon = _degrees(gps.get(LONGITUDE))
    if lat is None or lon is None:
        return None
    if str(gps.get(LATITUDE_REF) or "N").upper().startswith("S"):
        lat = -lat
    if str(gps.get(LONGITUDE_REF) or "E").upper().startswith("W"):
        lon = -lon
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 6), round(lon, 6)


def read_place(path: Path) -> Optional[tuple]:
    """``(latitude, longitude)`` from EXIF GPS, or None without Pillow or a valid point."""
    Image = load_image()
    if Image is None:
        return None
    try:
        # hygiene: allow Pillow's Image.open reads binary image data, not text
        with Image.open(path) as image:
            gps = image.getexif().get_ifd(GPS_IFD)
    except Exception:  # hygiene: allow Pillow raises many types for files it cannot parse
        return None
    return _point(gps)
