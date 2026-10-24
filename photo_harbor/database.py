"""The SQLite file behind the catalog and the sync journal, with its format version."""

import sqlite3
import threading
from pathlib import Path

from .errors import HarborError

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    sha256 TEXT PRIMARY KEY,
    rel_path TEXT NOT NULL UNIQUE,
    size INTEGER NOT NULL,
    original_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    taken_at TEXT,
    received_at TEXT NOT NULL,
    sort_time TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS photos_by_time ON photos (sort_time DESC, sha256 DESC);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL,
    sha256 TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS events_by_kind ON events (kind, at);
"""


class Database:
    """One shared connection; every statement runs under ``lock`` so server threads take turns."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self._open_schema(path)

    def _open_schema(self, path: Path) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            with self.lock:
                self.conn.executescript(_SCHEMA)
                self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        elif version != SCHEMA_VERSION:
            self.conn.close()
            raise HarborError(
                f"{path} uses catalog format {version}",
                f"this photo-harbor reads format {SCHEMA_VERSION} only",
                "run the photo-harbor version that created this library",
                status=500,
            )

    def close(self) -> None:
        with self.lock:
            self.conn.close()
