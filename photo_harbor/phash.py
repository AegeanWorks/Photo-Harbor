"""A small perceptual difference hash for the read-only Similar review."""

from pathlib import Path
from typing import Optional

from .pillow_support import load_image

WIDTH = 9
HEIGHT = 8


def hash_pixels(pixels) -> Optional[str]:
    """A 64-bit difference hash as 16 hex digits, or None for the wrong pixel count."""
    if len(pixels) != WIDTH * HEIGHT:
        return None
    value = 0
    for row in range(HEIGHT):
        start = row * WIDTH
        for column in range(WIDTH - 1):
            value = (value << 1) | int(pixels[start + column] > pixels[start + column + 1])
    return f"{value:016x}"


def read_dhash(path: Path) -> Optional[str]:
    """Perceptual hash from the original, or None without Pillow or a readable image."""
    Image = load_image()
    if Image is None:
        return None
    try:
        # hygiene: allow Pillow's Image.open reads binary image data, not text
        with Image.open(path) as image:
            grey = image.convert("L").resize(
                (WIDTH, HEIGHT), getattr(Image, "Resampling", Image).LANCZOS)
            pixels = list(grey.getdata())
    except Exception:  # hygiene: allow Pillow raises many types for unreadable formats
        return None
    return hash_pixels(pixels)
