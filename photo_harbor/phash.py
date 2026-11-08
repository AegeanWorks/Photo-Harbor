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


def hamming(left: str, right: str) -> int:
    """How many bits differ between two 16-hex perceptual hashes."""
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _bands(radius: int) -> list:
    """Split 64 bits into radius+1 bands, so a pair within radius shares one band."""
    width = max(1, (64 + radius) // (radius + 1))
    bands = []
    shift = 0
    left = 64
    while left:
        take = min(width, left)
        bands.append((shift, (1 << take) - 1))
        shift += take
        left -= take
    return bands


def hash_components(hashes, radius: int = 4) -> list:
    """Connected groups of valid hashes whose bits differ by at most ``radius``.

    The band index is the pigeonhole guarantee: with ``radius + 1`` bands, any pair
    within the radius has at least one exactly equal band, so no pair is missed.
    """
    unique = []
    for value in dict.fromkeys(hashes):
        if not isinstance(value, str) or len(value) != 16:
            continue
        try:
            int(value, 16)
        except ValueError:
            continue
        unique.append(value.lower())
    if not unique:
        return []
    numbers = {value: int(value, 16) for value in unique}
    bands = _bands(radius)
    index = {}
    for value in unique:
        for number, (shift, mask) in enumerate(bands):
            index.setdefault((number, (numbers[value] >> shift) & mask), []).append(value)
    parent = {value: value for value in unique}

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for value in unique:
        seen = set()
        for number, (shift, mask) in enumerate(bands):
            for other in index[(number, (numbers[value] >> shift) & mask)]:
                if other == value or other in seen:
                    continue
                seen.add(other)
                if (numbers[value] ^ numbers[other]).bit_count() <= radius:
                    union(value, other)
    grouped = {}
    for value in unique:
        grouped.setdefault(find(value), []).append(value)
    return list(grouped.values())


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
