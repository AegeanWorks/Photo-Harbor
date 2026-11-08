"""One background rebuild of the cached Similar groups."""

import threading


class SimilarBuilder:
    def __init__(self, catalog, radius: int = 8) -> None:
        self._catalog = catalog
        self._radius = radius
        self._lock = threading.Lock()
        self._thread = None
        self._error = None

    def start(self) -> bool:
        """Start a rebuild unless one is already running; True when this call started it."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._error = None
            self._thread = threading.Thread(target=self._run, name="harbor-similar",
                                            daemon=True)
            self._thread.start()
            return True

    def running(self) -> bool:
        with self._lock:
            return bool(self._thread is not None and self._thread.is_alive())

    def error(self):
        with self._lock:
            return self._error

    def _run(self) -> None:
        try:
            self._catalog.rebuild_groups(radius=self._radius)
        except Exception as exc:  # hygiene: allow the background worker reports any failure
            with self._lock:
                self._error = str(exc)
