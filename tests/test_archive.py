import io
import unittest

from photo_harbor.archive import ArchiveBook
from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.records import PhotoFilter, UploadClaim
from tests.library_fixture import FIXED_NOW, Library, sha


class ArchiveBookTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.book = ArchiveBook(self.lib.db, now=lambda: FIXED_NOW)
        self.one = self.lib.put(b"one", name="one.jpg",
                                taken="2026-01-01T10:00:00").record.sha256
        self.two = self.lib.put(b"two", name="two.jpg",
                                taken="2026-02-01T10:00:00").record.sha256

    def test_archiving_hides_from_the_timeline_and_shows_in_the_archive(self):
        self.assertTrue(self.book.set("main", self.one, True))
        self.assertFalse(self.book.set("main", self.one, True))
        page = self.lib.catalog.page(0, 10, PhotoFilter(viewer="main"))
        self.assertEqual([record.sha256 for record in page], [self.two])
        hidden = self.lib.catalog.page(0, 10, PhotoFilter(viewer="main", archived=True))
        self.assertEqual([record.sha256 for record in hidden], [self.one])
        outline = self.lib.catalog.outline(viewer="main")
        self.assertEqual((outline.total, outline.archived), (1, 1))
        self.assertEqual([month for month, _ in outline.months], ["2026-02"])
        self.assertEqual(self.lib.catalog.stats().count, 2)

    def test_archiving_is_private_to_the_viewer(self):
        self.assertTrue(self.book.set("main", self.one, True))
        hers = self.lib.catalog.page(0, 10, PhotoFilter(viewer="ayse"))
        self.assertEqual({record.sha256 for record in hers}, {self.one, self.two})
        self.assertEqual(self.lib.catalog.page(0, 10,
                                               PhotoFilter(viewer="ayse", archived=True)), [])
        outline = self.lib.catalog.outline(viewer="ayse")
        self.assertEqual((outline.total, outline.archived), (2, 0))

    def test_unarchiving_brings_the_photo_back(self):
        self.assertTrue(self.book.set("main", self.one, True))
        self.assertTrue(self.book.set("main", self.one, False))
        page = self.lib.catalog.page(0, 10, PhotoFilter(viewer="main"))
        self.assertEqual({record.sha256 for record in page}, {self.one, self.two})
        self.assertEqual(self.lib.catalog.page(0, 10,
                                               PhotoFilter(viewer="main", archived=True)), [])

    def test_a_batch_changes_each_row_once(self):
        self.assertEqual(self.book.set_many("main", [self.one, self.two, self.one], True), 2)
        self.assertEqual(self.book.set_many("main", [self.one, self.two], True), 0)
        self.assertEqual(self.book.set_many("main", [self.one], False), 1)

    def test_forgetting_a_copy_drops_its_archive_mark(self):
        claim = UploadClaim(original_name="one.jpg", sha256=self.one,
                            taken_at="2026-01-01T10:00:00", profile="ayse")
        self.lib.store.ingest(io.BytesIO(b"one"), 3, claim)
        self.assertTrue(self.book.set("main", self.one, True))
        self.assertFalse(self.lib.copies.forget("main", self.one))
        self.assertIsNotNone(self.lib.catalog.get(self.one))
        self.assertEqual(self.lib.db.conn.execute(
            "SELECT COUNT(*) FROM archived").fetchone()[0], 0)


class ArchiveMigrationTest(unittest.TestCase):
    def test_a_format_7_catalog_gains_the_archive_table(self):
        lib = Library(self)
        path = lib.root / "v7.sqlite3"
        old = Database(path)
        old.conn.execute(
            "INSERT INTO photos (sha256, rel_path, size, original_name, media_type, taken_at,"
            " received_at, sort_time, profile) VALUES (?, 'main/2026/2026-01/a.jpg', 3, 'a.jpg',"
            " 'image/jpeg', NULL, '2026-01-02T00:00:00', '2026-01-02T00:00:00', 'main')",
            (sha(b"a"),))
        old.conn.executescript("DROP TABLE archived;"
                               "ALTER TABLE photos DROP COLUMN latitude;"
                               "ALTER TABLE photos DROP COLUMN longitude;"
                               "PRAGMA user_version=7;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0], 1)
        self.assertEqual(db.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='archived'"
        ).fetchone()[0], 1)
        self.assertTrue((lib.root / "v7.sqlite3.v7.bak").exists())
