import unittest

from photo_harbor.albums import AlbumBook
from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.errors import HarborError
from photo_harbor.records import PhotoFilter
from tests.library_fixture import FIXED_NOW, Library, sha


class AlbumBookTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.book = AlbumBook(self.lib.db, now=lambda: FIXED_NOW)
        self.one = self.lib.put(b"one", name="one.jpg", taken="2026-01-01T10:00:00").record.sha256
        self.two = self.lib.put(b"two", name="two.jpg", taken="2026-02-01T10:00:00").record.sha256

    def test_an_album_holds_photos_without_moving_any_file(self):
        album = self.book.create("main", "Summer 2026")
        self.assertTrue(self.book.add("main", album.id, self.one, True))
        self.assertFalse(self.book.add("main", album.id, self.one, True))
        favorites, albums = self.book.summary("main")
        self.assertEqual(favorites, 0)
        self.assertEqual((albums[0].name, albums[0].count, albums[0].cover),
                         ("Summer 2026", 1, self.one))
        page = self.lib.catalog.page(0, 10, PhotoFilter(album=album.id, viewer="main"))
        self.assertEqual([record.sha256 for record in page], [self.one])
        self.assertTrue(self.book.add("main", album.id, self.one, False))
        self.assertEqual(self.book.summary("main")[1][0].count, 0)

    def test_favorites_are_private_to_the_person_who_marked_them(self):
        self.assertTrue(self.book.favorite("main", self.one, True))
        self.assertFalse(self.book.favorite("main", self.one, True))
        favorite = self.lib.catalog.page(0, 10, PhotoFilter(favorite=True, viewer="main"))
        self.assertEqual([(record.sha256, record.favorite) for record in favorite],
                         [(self.one, True)])
        self.assertEqual(self.lib.catalog.page(0, 10, PhotoFilter(favorite=True, viewer="ayse")), [])
        self.assertEqual(self.book.summary("main")[0], 1)
        self.assertEqual(self.book.summary("ayse")[0], 0)

    def test_album_names_are_cleaned_and_unique_per_person(self):
        album = self.book.create("main", "  Summer   2026 ")
        self.assertEqual(album.name, "Summer 2026")
        with self.assertRaises(HarborError):
            self.book.create("main", "summer 2026")
        other = self.book.create("ayse", "Summer 2026")
        self.assertNotEqual(album.id, other.id)
        with self.assertRaises(HarborError):
            self.book.create("main", "   ")

    def test_a_person_cannot_touch_another_persons_album(self):
        album = self.book.create("main", "Mine")
        self.assertTrue(self.book.owned("main", album.id))
        self.assertFalse(self.book.owned("ayse", album.id))
        for action in (lambda: self.book.rename("ayse", album.id, "Theirs"),
                       lambda: self.book.delete("ayse", album.id),
                       lambda: self.book.add("ayse", album.id, self.one, True)):
            with self.assertRaises(HarborError):
                action()

    def test_bulk_membership_and_favorites_change_each_row_once(self):
        album = self.book.create("main", "Batch")
        self.assertEqual(self.book.add_many("main", album.id, [self.one, self.two], True), 2)
        self.assertEqual(self.book.add_many("main", album.id, [self.one, self.two], True), 0)
        self.assertEqual(self.book.summary("main")[1][0].count, 2)
        self.assertEqual(self.book.favorite_many("main", [self.one, self.two], True), 2)
        self.assertEqual(self.book.favorite_many("main", [self.one, self.two], True), 0)
        self.assertEqual(self.book.summary("main")[0], 2)
        self.assertEqual(self.book.favorite_many("main", [self.one], False), 1)
        self.assertEqual(self.book.summary("main")[0], 1)

    def test_renaming_and_deleting_an_album_keeps_its_photos(self):
        album = self.book.create("main", "Old name")
        self.book.add("main", album.id, self.one, True)
        self.book.add("main", album.id, self.two, True)
        self.book.rename("main", album.id, "New name")
        self.assertEqual(self.book.summary("main")[1][0].name, "New name")
        self.book.delete("main", album.id)
        self.assertEqual(self.book.summary("main")[1], [])
        self.assertIsNotNone(self.lib.catalog.get(self.one))
        self.assertIsNotNone(self.lib.catalog.get(self.two))


class CollectionMigrationTest(unittest.TestCase):
    def test_a_format_4_catalog_gains_collections_and_keeps_its_photos(self):
        lib = Library(self)
        path = lib.root / "v4.sqlite3"
        old = Database(path)
        old.conn.execute(
            "INSERT INTO photos (sha256, rel_path, size, original_name, media_type, taken_at,"
            " received_at, sort_time, profile) VALUES (?, 'main/2026/2026-01/a.jpg', 3, 'a.jpg',"
            " 'image/jpeg', NULL, '2026-01-02T00:00:00', '2026-01-02T00:00:00', 'main')",
            (sha(b"a"),))
        old.conn.executescript("DROP TABLE album_photos; DROP TABLE favorites; DROP TABLE albums;"
                               "PRAGMA user_version=4;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0], 1)
        for table in ("favorites", "albums", "album_photos"):
            self.assertEqual(
                db.conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                                (table,)).fetchone()[0], 1)
        self.assertTrue((lib.root / "v4.sqlite3.v4.bak").exists())

    def test_a_bad_collection_id_is_a_clear_error(self):
        lib = Library(self)
        book = AlbumBook(lib.db)
        with self.assertRaises(HarborError):
            book.owned("main", "not-a-number")
        with self.assertRaises(HarborError):
            book.owned("main", 0)
