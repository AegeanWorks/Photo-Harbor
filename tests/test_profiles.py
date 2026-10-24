import io
import sqlite3
import unittest

from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.errors import HarborError
from photo_harbor.importer import find_media, import_folder
from photo_harbor.journal import SYNC_DONE
from photo_harbor.profiles import ProfileBook, profile_id
from photo_harbor.records import PhotoFilter, UploadClaim
from tests.library_fixture import Library, sha

V1_SCHEMA = """
CREATE TABLE photos (sha256 TEXT PRIMARY KEY, rel_path TEXT NOT NULL UNIQUE, size INTEGER NOT NULL,
    original_name TEXT NOT NULL, media_type TEXT NOT NULL, taken_at TEXT, received_at TEXT NOT NULL,
    sort_time TEXT NOT NULL);
CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, kind TEXT NOT NULL,
    sha256 TEXT, detail TEXT);
INSERT INTO photos VALUES ('%s', '2025/01/a.jpg', 3, 'a.jpg', 'image/jpeg', NULL,
    '2025-01-02T00:00:00', '2025-01-02T00:00:00');
INSERT INTO events (at, kind, detail) VALUES ('2025-01-02T00:00:00', 'sync_done', '2025-01-01T23:00:00');
PRAGMA user_version=1;
""" % ("a" * 64)


class ProfileBookTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.book = ProfileBook(self.lib.db, "owner-key-0123456789")

    def test_the_owner_profile_holds_the_library_key(self):
        self.assertEqual([(p.id, p.key) for p in self.book.all()], [("main", "owner-key-0123456789")])
        self.assertEqual(self.book.by_key("owner-key-0123456789").id, "main")

    def test_a_new_library_key_reaches_the_owner_profile(self):
        ProfileBook(self.lib.db, "rotated-key-0123456789")
        self.assertIsNone(self.book.by_key("owner-key-0123456789"))
        self.assertEqual(self.book.by_key("rotated-key-0123456789").id, "main")

    def test_ids_are_folder_safe_and_unique(self):
        self.assertEqual(profile_id("Ayşe Yılmaz"), "ayse-yilmaz")
        added = self.book.create("  Ayşe  ")
        self.assertEqual((added.id, added.name), ("ayse", "Ayşe"))
        self.assertEqual(self.book.by_key(added.key), added)
        with self.assertRaises(HarborError):
            self.book.create("AYŞE")
        with self.assertRaises(HarborError):
            self.book.create("!!!")

    def test_a_new_key_retires_the_old_one(self):
        added = self.book.create("Ayşe")
        renewed = self.book.update("ayse", new_key=True)
        self.assertIsNone(self.book.by_key(added.key))
        self.assertEqual(self.book.by_key(renewed.key).id, "ayse")
        with self.assertRaises(HarborError):
            self.book.update("main", new_key=True)


class MigrationTest(unittest.TestCase):
    def test_a_format_1_catalog_is_upgraded_and_owned_by_main(self):
        lib = Library(self)
        path = lib.root / "old.sqlite3"
        old = sqlite3.connect(path)
        old.executescript(V1_SCHEMA)
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(db.conn.execute("SELECT profile FROM photos").fetchone()[0], "main")
        self.assertTrue((lib.root / "old.sqlite3.v1.bak").exists())
        from photo_harbor.journal import SyncJournal
        self.assertEqual(SyncJournal(db).last_sync("main"), "2025-01-01T23:00:00")

    def test_a_format_2_catalog_gains_the_import_list(self):
        lib = Library(self)
        path = lib.root / "v2.sqlite3"
        old = sqlite3.connect(path)
        old.executescript(V1_SCHEMA.replace("PRAGMA user_version=1;", ""))
        old.executescript("ALTER TABLE photos ADD COLUMN profile TEXT NOT NULL DEFAULT 'main';"
                          "ALTER TABLE events ADD COLUMN profile TEXT;"
                          "CREATE TABLE profiles (id TEXT PRIMARY KEY, name TEXT NOT NULL,"
                          " key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);"
                          "PRAGMA user_version=2;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM imported_files").fetchone()[0], 0)
        self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0], 1)
        self.assertTrue((lib.root / "v2.sqlite3.v2.bak").exists())


class ProfileStorageTest(unittest.TestCase):
    def test_photos_land_in_their_profile_and_filter_by_it(self):
        lib = Library(self)
        claim = UploadClaim("IMG.JPG", sha256=sha(b"hers"), taken_at="2026-02-01T10:00:00",
                            profile="ayse")
        record = lib.store.ingest(io.BytesIO(b"hers"), 4, claim).record
        lib.put(b"mine")
        self.assertEqual(record.rel_path, "ayse/2026/2026-02/IMG.jpg")
        found = lib.catalog.page(0, 10, PhotoFilter(profile="ayse"))
        self.assertEqual([r.sha256 for r in found], [sha(b"hers")])
        self.assertEqual(lib.catalog.stats("main").count, 1)
        self.assertEqual([m for m, _ in lib.catalog.outline("ayse").months], ["2026-02"])

    def test_last_sync_is_kept_per_profile(self):
        lib = Library(self)
        lib.journal.record("2026-10-24T10:00:00", SYNC_DONE, None, "2026-10-24T09:00:00", "ayse")
        self.assertEqual(lib.journal.last_sync("ayse"), "2026-10-24T09:00:00")
        self.assertIsNone(lib.journal.last_sync("main"))


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.source = self.lib.root.parent / (self.lib.root.name + "_src")
        (self.source / "trip" / ".hidden").mkdir(parents=True)
        self.addCleanup(__import__("shutil").rmtree, self.source, True)
        (self.source / "trip" / "a.JPG").write_bytes(b"photo a")
        (self.source / "trip" / "clip.mov").write_bytes(b"video")
        (self.source / "trip" / "notes.txt").write_text("not media")
        (self.source / "trip" / ".hidden" / "b.jpg").write_bytes(b"hidden")
        (self.source / "copy.jpg").write_bytes(b"photo a")

    def test_finds_media_only_and_skips_hidden_folders(self):
        names = [p.name for p in find_media(self.source, self.lib.root)]
        self.assertEqual(names, ["copy.jpg", "a.JPG", "clip.mov"])

    def test_imports_into_a_profile_once_and_leaves_the_source_alone(self):
        steps = []
        report = import_folder(self.lib.store, self.source, self.lib.root, "ayse",
                               lambda done, total, path: steps.append((done, total)))
        self.assertEqual((report.stored, report.duplicate, report.failed), (2, 1, 0))
        self.assertEqual(steps[-1], (3, 3))
        again = import_folder(self.lib.store, self.source, self.lib.root, "ayse")
        self.assertEqual((again.stored, again.duplicate), (0, 3))
        self.assertTrue((self.source / "trip" / "a.JPG").exists())
        self.assertEqual(self.lib.catalog.stats("ayse").count, 2)

    def test_refuses_a_folder_inside_the_library(self):
        with self.assertRaises(HarborError):
            find_media(self.lib.root / "photos", self.lib.root)
