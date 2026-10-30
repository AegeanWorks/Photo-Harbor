import unittest

from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.errors import HarborError
from photo_harbor.trash import TrashBook
from tests.library_fixture import FIXED_NOW, Library


class TrashBookTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.book = TrashBook(self.lib.db, self.lib.root, self.lib.store, self.lib.copies,
                              now=lambda: FIXED_NOW)

    def test_a_copy_moves_to_trash_and_restores_its_bytes(self):
        record = self.lib.put(b"one", name="one.jpg").record
        trash_id = self.book.move("main", record.sha256)
        self.assertIsNone(self.lib.catalog.get(record.sha256))
        items = self.book.listing("main")
        self.assertEqual([(item.id, item.name) for item in items], [(trash_id, "one.jpg")])
        self.assertEqual(len(list(self.book.root.rglob("*.jpg"))), 1)
        result = self.book.restore("main", trash_id)
        self.assertEqual(result.status, "stored")
        self.assertEqual(self.book.listing("main"), [])
        self.assertEqual(self.lib.store.locate(record.sha256, "main")[0].read_bytes(), b"one")

    def test_a_shared_photo_stays_for_the_other_person(self):
        record = self.lib.put(b"shared", name="shared.jpg").record
        self.assertTrue(self.lib.store.ensure_copy("ayse", record.sha256))
        self.book.move("main", record.sha256)
        self.assertIsNotNone(self.lib.catalog.get(record.sha256))
        self.assertIsNotNone(self.lib.store.locate(record.sha256, "ayse"))
        self.assertIsNone(self.lib.store.locate(record.sha256, "main"))
        self.book.restore("main", self.book.listing("main")[0].id)
        self.assertIsNotNone(self.lib.store.locate(record.sha256, "main"))
        self.assertIsNotNone(self.lib.store.locate(record.sha256, "ayse"))

    def test_permanent_delete_and_empty_remove_the_files(self):
        one = self.lib.put(b"one", name="one.jpg").record
        two = self.lib.put(b"two", name="two.jpg").record
        first = self.book.move("main", one.sha256)
        self.book.delete("main", first)
        self.assertEqual(self.book.listing("main"), [])
        self.assertEqual(list(self.book.root.rglob("*.jpg")), [])
        self.book.move("main", two.sha256)
        self.assertEqual(self.book.empty("main"), 1)
        self.assertEqual(self.book.listing("main"), [])
        self.assertEqual(list(self.book.root.rglob("*.jpg")), [])

    def test_another_person_cannot_restore_or_delete_the_entry(self):
        record = self.lib.put(b"one", name="one.jpg").record
        self.book.move("main", record.sha256)
        entry = self.book.listing("main")[0]
        with self.assertRaises(HarborError):
            self.book.restore("ayse", entry.id)
        with self.assertRaises(HarborError):
            self.book.delete("ayse", entry.id)


class TrashMigrationTest(unittest.TestCase):
    def test_a_format_5_catalog_gains_the_trash_table(self):
        lib = Library(self)
        path = lib.root / "v5.sqlite3"
        old = Database(path)
        old.conn.executescript("DROP TABLE trash; PRAGMA user_version=5;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(db.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='trash'"
        ).fetchone()[0], 1)
        self.assertTrue((lib.root / "v5.sqlite3.v5.bak").exists())
