"""A throwaway library for tests: temp folder, database, catalog, journal and store."""

import hashlib
import io
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from photo_harbor.catalog import Catalog
from photo_harbor.database import Database
from photo_harbor.journal import SyncJournal
from photo_harbor.records import UploadClaim
from photo_harbor.store import PhotoStore

FIXED_NOW = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Library:
    def __init__(self, test_case) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="harbor_test_"))
        test_case.addCleanup(shutil.rmtree, self.root, True)
        self.db = Database(self.root / ".harbor" / "catalog.sqlite3")
        test_case.addCleanup(self.db.close)
        self.catalog = Catalog(self.db)
        self.journal = SyncJournal(self.db)
        self.store = PhotoStore(self.root, self.catalog, now=lambda: FIXED_NOW,
                                embedded_date=lambda path: None)

    def put(self, data: bytes, name: str = "IMG_0001.HEIC", taken: str = None):
        claim = UploadClaim(original_name=name, sha256=sha(data), taken_at=taken)
        return self.store.ingest(io.BytesIO(data), len(data), claim)
