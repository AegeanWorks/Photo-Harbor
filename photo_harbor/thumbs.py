"""Small JPEG previews, made only when the optional Pillow (and pillow-heif for HEIC) is installed."""

import io
import queue
import threading
from pathlib import Path
from typing import Optional

from .atomic_file import write_atomic
from .pillow_support import load_pillow
from .records import PhotoRecord

EDGE = 480
QUALITY = 82


class Thumbnailer:
    def __init__(self, cache_dir: Path, pillow=load_pillow) -> None:
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
                # JPEG decodes straight to a reduced size: several times faster for big photos.
                image.draft("RGB", (EDGE * 2, EDGE * 2))
                image = ops.exif_transpose(image).convert("RGB")
                image.thumbnail((EDGE, EDGE))
                buffer = io.BytesIO()
                image.save(buffer, "JPEG", quality=QUALITY, optimize=True)
        except Exception:  # hygiene: allow Pillow raises many types for unsupported formats
            return None
        with self._lock:
            write_atomic(target, buffer.getvalue())
        return target


class PreviewWarmer:
    """Makes previews ahead of time on one background thread, so a large library scrolls without
    waiting: newly stored photos first, then every older photo still without one, newest first."""

    def __init__(self, thumbs: Thumbnailer, catalog, store, page: int = 200) -> None:
        self._thumbs = thumbs
        self._catalog = catalog
        self._store = store
        self._page = page
        self._fresh: "queue.Queue[PhotoRecord]" = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="harbor-previews", daemon=True)
        self.made = 0

    def start(self) -> None:
        self._thread.start()

    def add(self, record: PhotoRecord) -> None:
        self._fresh.put(record)

    def stop(self) -> None:
        self._stop.set()
        self._fresh.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def _warm(self, record: PhotoRecord) -> None:
        found = self._store.locate(record.sha256)
        if found is not None and not record.is_video:
            if self._thumbs.preview(record, found[0]) is not None:
                self.made += 1

    def _run(self) -> None:
        offset = 0
        backlog = True
        while not self._stop.is_set():
            try:
                record = self._fresh.get(timeout=0 if backlog else 1)
            except queue.Empty:
                record = None
                if backlog:
                    batch = self._catalog.page(offset, self._page)
                    offset += len(batch)
                    backlog = len(batch) == self._page
                    for older in batch:
                        if self._stop.is_set() or not self._fresh.empty():
                            break
                        self._warm(older)
                continue
            if record is not None:
                self._warm(record)
