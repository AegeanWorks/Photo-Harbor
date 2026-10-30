"""Optional Pillow loading, with HEIC support when pillow-heif is installed."""

import importlib.util
from typing import Optional


def load_image():
    """Pillow's ``Image`` module, or None when Pillow is not installed."""
    if importlib.util.find_spec("PIL") is None:
        return None
    from PIL import Image
    if importlib.util.find_spec("pillow_heif") is not None:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    return Image


def load_pillow() -> Optional[tuple]:
    """``(Image, ImageOps)``, or None when Pillow is not installed."""
    image = load_image()
    if image is None:
        return None
    from PIL import ImageOps
    return image, ImageOps
