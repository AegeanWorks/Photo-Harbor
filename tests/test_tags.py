import io
import unittest

from photo_harbor.archive import ArchiveBook
from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.errors import HarborError
from photo_harbor.records import PhotoFilter, UploadClaim
from photo_harbor.tags import TagBook
from tests.library_fixture import FIXED_NOW, Library, sha


class TagBookTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.book = TagBook(self.lib.db, now=lambda: FIXED_NOW)
        self.one = self.lib.put(b"one", name="one.jpg",
                                taken="2026-01-01T10:00:00").record.sha256
        self.two = self.lib.put(b"two", name="two.jpg",
                                taken="2026-02-01T10:00:00").record.sha256

    def test_creating_a_tag_is_case_insensitive_and_idempotent(self):
        first = self.book.create("main", "  Beach   day ")
        second = self.book.create("main", "beach DAY")
        self.assertEqual((first.id, first.name), (second.id, "Beach day"))
        self.assertEqual([(tag.name, tag.count) for tag in self.book.summary("main")],
                         [("Beach day", 0)])
        with self.assertRaises(HarborError):
            self.book.create("main", "   ")

    def test_tagging_filters_the_gallery_and_renaming_keeps_marks(self):
        tag = self.book.create("main", "Keepers")
        self.assertTrue(self.book.add("main", tag.id, self.one, True))
        self.assertFalse(self.book.add("main", tag.id, self.one, True))
        page = self.lib.catalog.page(0, 10, PhotoFilter(tag=tag.id, viewer="main"))
        self.assertEqual([record.sha256 for record in page], [self.one])
        self.assertEqual(self.book.summary("main")[0].count, 1)
        renamed = self.book.rename("main", tag.id, "Best")
        self.assertEqual(renamed.name, "Best")
        page = self.lib.catalog.page(0, 10, PhotoFilter(tag=tag.id, viewer="main"))
        self.assertEqual([record.sha256 for record in page], [self.one])

    def test_tags_are_private_to_the_person_who_made_them(self):
        tag = self.book.create("main", "Mine")
        self.book.add("main", tag.id, self.one, True)
        self.assertFalse(self.book.owned("ayse", tag.id))
        self.assertEqual(self.lib.catalog.page(0, 10, PhotoFilter(tag=tag.id, viewer="ayse")), [])
        self.assertEqual(self.book.summary("ayse"), [])
        with self.assertRaises(HarborError):
            self.book.add("ayse", tag.id, self.one, True)

    def test_archived_photos_leave_the_tag_count_and_delete_removes_marks(self):
        tag = self.book.create("main", "Keepers")
        self.book.add_many("main", tag.id, [self.one, self.two], True)
        ArchiveBook(self.lib.db, now=lambda: FIXED_NOW).set("main", self.one, True)
        self.assertEqual(self.book.summary("main")[0].count, 1)
        self.book.delete("main", tag.id)
        self.assertEqual(self.book.summary("main"), [])
        self.assertEqual(self.lib.db.conn.execute(
            "SELECT COUNT(*) FROM photo_tags").fetchone()[0], 0)

    def test_a_batch_changes_each_row_once(self):
        tag = self.book.create("main", "Batch")
        self.assertEqual(self.book.add_many("main", tag.id, [self.one, self.two, self.one], True), 2)
        self.assertEqual(self.book.add_many("main", tag.id, [self.one, self.two], True), 0)
        self.assertEqual(self.book.add_many("main", tag.id, [self.one], False), 1)

    def test_forgetting_a_copy_drops_only_that_persons_marks(self):
        mine = self.book.create("main", "Mine")
        hers = self.book.create("ayse", "Hers")
        self.book.add("main", mine.id, self.one, True)
        self.book.add("ayse", hers.id, self.one, True)
        claim = UploadClaim(original_name="one.jpg", sha256=self.one,
                            taken_at="2026-01-01T10:00:00", profile="ayse")
        self.lib.store.ingest(io.BytesIO(b"one"), 3, claim)
        self.assertFalse(self.lib.copies.forget("main", self.one))
        self.assertEqual(self.book.members("main", self.one), [])
        self.assertEqual(self.book.members("ayse", self.one), [hers.id])


class TagMigrationTest(unittest.TestCase):
    def test_a_format_8_catalog_gains_the_tag_tables(self):
        lib = Library(self)
        path = lib.root / "v8.sqlite3"
        old = Database(path)
        old.conn.executescript("DROP TABLE photo_tags; DROP TABLE tags;"
                               "ALTER TABLE photos DROP COLUMN latitude;"
                               "ALTER TABLE photos DROP COLUMN longitude;"
                               "ALTER TABLE photos DROP COLUMN camera;"
                               "ALTER TABLE photos DROP COLUMN lens;"
                               "PRAGMA user_version=8;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        for table in ("tags", "photo_tags"):
            self.assertEqual(db.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table,)).fetchone()[0], 1)
        self.assertTrue((lib.root / "v8.sqlite3.v8.bak").exists())
