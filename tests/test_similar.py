import io
import json
import unittest

from photo_harbor.archive import ArchiveBook
from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.messages import Request
from photo_harbor.phash import hash_pixels
from photo_harbor.records import Identity
from photo_harbor.similar_api import SimilarApi
from tests.library_fixture import FIXED_NOW, Library, sha


class HashTest(unittest.TestCase):
    def test_a_gradient_becomes_a_hex_difference_hash(self):
        self.assertEqual(hash_pixels([0] * 72), "0000000000000000")
        self.assertEqual(hash_pixels(list(range(8, -1, -1)) * 8),
                         "ffffffffffffffff")
        self.assertIsNone(hash_pixels([0] * 71))


class SimilarCatalogTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.one = self.lib.put(b"one", name="one.jpg").record.sha256
        self.two = self.lib.put(b"two", name="two.jpg").record.sha256
        self.three = self.lib.put(b"three", name="three.jpg").record.sha256
        self.four = self.lib.put(b"four", name="four.jpg").record.sha256
        self.lib.catalog.set_hash(self.one, "aaaaaaaaaaaaaaaa")
        self.lib.catalog.set_hash(self.two, "aaaaaaaaaaaaaaaa")
        self.lib.catalog.set_hash(self.three, "bbbbbbbbbbbbbbbb")
        self.lib.catalog.set_hash(self.four, "skip")

    def test_status_and_groups_are_read_only(self):
        status = self.lib.catalog.similar_status(viewer="main")
        self.assertEqual(status, {"total": 4, "missing": 0, "skipped": 1, "indexed": 3})
        groups = self.lib.catalog.similar_groups(viewer="main")
        self.assertEqual(len(groups), 1)
        dhash, records = groups[0]
        self.assertEqual(dhash, "aaaaaaaaaaaaaaaa")
        self.assertEqual({record.sha256 for record in records}, {self.one, self.two})
        self.assertEqual(self.lib.catalog.stats().count, 4)

    def test_archiving_removes_a_photo_from_the_review(self):
        ArchiveBook(self.lib.db, now=lambda: FIXED_NOW).set("main", self.one, True)
        self.assertEqual(self.lib.catalog.similar_groups(viewer="main"), [])
        self.assertEqual(self.lib.catalog.similar_status(viewer="main")["total"], 3)

    def test_another_person_sees_only_their_copies(self):
        status = self.lib.catalog.similar_status(profile="ayse", viewer="ayse")
        self.assertEqual(status["total"], 0)
        self.assertEqual(self.lib.catalog.similar_groups(profile="ayse", viewer="ayse"), [])


class SimilarApiTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.api = SimilarApi(self.lib.catalog, self.lib.store,
                              dhash=lambda path: "0123456789abcdef")
        self.one = self.lib.put(b"one", name="one.jpg").record.sha256
        self.two = self.lib.put(b"two", name="two.jpg").record.sha256

    def _request(self, method="GET", path="/api/similar", body=None):
        payload = json.dumps(body or {}).encode()
        return Request(method, path, body=io.BytesIO(payload), length=len(payload),
                       identity=Identity("main", True))

    def test_scan_indexes_visible_photos_and_listing_groups_them(self):
        scan = json.loads(self.api.scan(self._request("POST", "/api/similar/scan",
                                                      {"limit": 10})).body)
        self.assertEqual((scan["processed"], scan["indexed"], scan["skipped"]), (2, 2, 0))
        listing = json.loads(self.api.listing(self._request()).body)
        self.assertEqual(listing["status"]["indexed"], 2)
        self.assertEqual(listing["groups"][0]["count"], 2)
        self.assertEqual({photo["sha256"] for photo in listing["groups"][0]["photos"]},
                         {self.one, self.two})

    def test_unreadable_files_are_skipped_once(self):
        api = SimilarApi(self.lib.catalog, self.lib.store, dhash=lambda path: None)
        first = json.loads(api.scan(self._request("POST", "/api/similar/scan",
                                                  {"limit": 10})).body)
        self.assertEqual((first["indexed"], first["skipped"]), (0, 2))
        second = json.loads(api.scan(self._request("POST", "/api/similar/scan",
                                                   {"limit": 10})).body)
        self.assertEqual(second["processed"], 0)
        self.assertEqual(second["status"]["missing"], 0)


class SimilarMigrationTest(unittest.TestCase):
    def test_a_format_11_catalog_gains_the_hash_cache(self):
        lib = Library(self)
        path = lib.root / "v11.sqlite3"
        old = Database(path)
        old.conn.executescript("DROP TABLE photo_hashes; PRAGMA user_version=11;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(db.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='photo_hashes'"
        ).fetchone()[0], 1)
        self.assertTrue((lib.root / "v11.sqlite3.v11.bak").exists())
