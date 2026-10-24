"""The SQLite file behind the catalog, people, copies, sign-ins, journal and import list."""

import sqlite3
import threading
from pathlib import Path

from .errors import HarborError

SCHEMA_VERSION = 4
OWNER_PROFILE = "main"

# Format 4, as a new library gets it. ``photos`` holds one row per distinct file (by SHA-256);
# ``copies`` says whose folder holds it and where, and repeats the photo's date, size and
# kind so one person's view is read in date order from an index. Paths are relative to the library.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    sha256 TEXT PRIMARY KEY,
    rel_path TEXT NOT NULL UNIQUE,
    size INTEGER NOT NULL,
    original_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    taken_at TEXT,
    received_at TEXT NOT NULL,
    sort_time TEXT NOT NULL,
    profile TEXT NOT NULL DEFAULT 'main'
);
CREATE INDEX IF NOT EXISTS photos_by_time ON photos (sort_time DESC, sha256 DESC);
CREATE INDEX IF NOT EXISTS photos_by_profile ON photos (profile, sort_time DESC);
CREATE INDEX IF NOT EXISTS photos_profile_totals ON photos (profile, size, received_at);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL,
    sha256 TEXT,
    detail TEXT,
    profile TEXT
);
CREATE INDEX IF NOT EXISTS events_by_kind ON events (kind, at);
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    folder TEXT UNIQUE,
    password_hash TEXT
);
CREATE TABLE IF NOT EXISTS imported_files (
    source TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS copies (
    profile TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    rel_path TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    added_at TEXT NOT NULL,
    sort_time TEXT NOT NULL,
    size INTEGER NOT NULL,
    is_video INTEGER NOT NULL,
    PRIMARY KEY (profile, sha256)
);
CREATE INDEX IF NOT EXISTS copies_by_sha ON copies (sha256);
CREATE INDEX IF NOT EXISTS copies_by_time ON copies (profile, sort_time DESC, sha256 DESC);
CREATE INDEX IF NOT EXISTS copies_totals ON copies (profile, sort_time, is_video, size, added_at);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

# Format 1 had no profiles: every photo and event belongs to the owner profile.
_FROM_1 = """
ALTER TABLE photos ADD COLUMN profile TEXT NOT NULL DEFAULT 'main';
ALTER TABLE events ADD COLUMN profile TEXT;
CREATE INDEX IF NOT EXISTS photos_by_profile ON photos (profile, sort_time DESC);
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
"""

# Format 3 added a covering index for per-profile totals and the list of imported files.
_FROM_2 = """
CREATE INDEX IF NOT EXISTS photos_profile_totals ON photos (profile, size, received_at);
CREATE TABLE IF NOT EXISTS imported_files (
    source TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
"""

# Format 4: per-person copies, folders and passwords. Paths that were relative to photos/ become
# relative to the library; every existing photo becomes a copy owned by its profile. The files
# themselves are moved to the readable layout afterwards, one by one (see layout.py).
_FROM_3 = """
ALTER TABLE profiles ADD COLUMN folder TEXT;
ALTER TABLE profiles ADD COLUMN password_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS profiles_by_folder ON profiles (folder);
UPDATE photos SET rel_path = 'photos/' || rel_path;
CREATE TABLE IF NOT EXISTS copies (
    profile TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    rel_path TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    added_at TEXT NOT NULL,
    sort_time TEXT NOT NULL,
    size INTEGER NOT NULL,
    is_video INTEGER NOT NULL,
    PRIMARY KEY (profile, sha256)
);
CREATE INDEX IF NOT EXISTS copies_by_sha ON copies (sha256);
CREATE INDEX IF NOT EXISTS copies_by_time ON copies (profile, sort_time DESC, sha256 DESC);
CREATE INDEX IF NOT EXISTS copies_totals ON copies (profile, sort_time, is_video, size, added_at);
INSERT INTO copies (profile, sha256, rel_path, original_name, added_at, sort_time, size,
                    is_video)
    SELECT profile, sha256, rel_path, original_name, received_at, sort_time, size,
           media_type LIKE 'video/%' FROM photos;
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

_UPGRADES = {1: _FROM_1 + _FROM_2 + _FROM_3, 2: _FROM_2 + _FROM_3, 3: _FROM_3}


class Database:
    """One shared connection; every statement runs under ``lock`` so server threads take turns."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None,
                                    timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self._open_schema(path)

    def _open_schema(self, path: Path) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            return
        if version == 0:
            self._apply(_SCHEMA)
        elif version in _UPGRADES:
            self._backup(path.with_name(f"{path.name}.v{version}.bak"))
            self._apply(_UPGRADES[version])
        else:
            self.conn.close()
            raise HarborError(
                f"{path} uses catalog format {version}",
                f"this photo-harbor reads formats 1 to {SCHEMA_VERSION} only",
                "run the photo-harbor version that created this library",
                status=500,
            )

    def _apply(self, script: str) -> None:
        """Run ``script`` and stamp the version in one transaction: all of it or none."""
        statements = [part.strip() for part in script.split(";") if part.strip()]
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in statements:
                    self.conn.execute(statement)
                self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            except sqlite3.Error:
                self.conn.execute("ROLLBACK")
                raise
            self.conn.execute("COMMIT")

    def _backup(self, target: Path) -> None:
        """A consistent copy of the catalog before it is migrated."""
        copy = sqlite3.connect(target)
        try:
            self.conn.backup(copy)
        finally:
            copy.close()

    def close(self) -> None:
        with self.lock:
            self.conn.close()
