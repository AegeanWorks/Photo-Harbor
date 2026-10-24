"""Small JPEG previews, made only when the optional Pillow (and pillow-heif for HEIC) is installed."""

import importlib.util
import io
import threading
from pathlib import Path
from typing import Optional

from .atomic_file import write_atomic
from .records import PhotoRecord

EDGE = 480
QUALITY = 82


def _load_pillow():
    """Pillow's Image and ImageOps modules, or None without Pillow. HEIC opens only when
    pillow-heif is installed too; without it HEIC previews fail and the gallery falls back."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    if importlib.util.find_spec("pillow_heif") is not None:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    return Image, ImageOps


class Thumbnailer:
    def __init__(self, cache_dir: Path, pillow=_load_pillow) -> None:
        self._cache = cache_dir
        self._pillow = pillow()
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._pillow is not None

    def preview(self, record: PhotoRecord, original: Path) -> Optional[Path]:
        """The cached preview, made on first request; None for videos or unreadable images."""
        if self._pillow is None or record.is_video:
            return None
        target = self._cache / record.sha256[:2] / f"{record.sha256}.jpg"
        if target.exists():
            return target
        image_mod, ops = self._pillow
        try:
            # hygiene: allow Pillow's Image.open reads binary image data, not text
            with image_mod.open(original) as image:
                image = ops.exif_transpose(image).convert("RGB")
                image.thumbnail((EDGE, EDGE))
                buffer = io.BytesIO()
                image.save(buffer, "JPEG", quality=QUALITY, optimize=True)
        except Exception:  # hygiene: allow Pillow raises many types for unsupported formats
            return None
        with self._lock:
            write_atomic(target, buffer.getvalue())
        return target
