import io
import unittest

from photo_harbor.database import Database
from photo_harbor.errors import HarborError
from photo_harbor.journal import MISSING, STORED, SYNC_DONE
from photo_harbor.records import UploadClaim
from tests.library_fixture import Library, sha


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)

    def test_stores_under_the_month_it_was_taken(self):
        result = self.lib.put(b"photo-bytes", taken="2025-07-04T09:00:00")
        self.assertEqual(result.status, "stored")
        self.assertEqual(result.record.rel_path, "2025/07/IMG_0001.heic")
        self.assertEqual((self.lib.store.photos_dir / result.record.rel_path).read_bytes(),
                         b"photo-bytes")

    def test_same_bytes_twice_is_a_duplicate_and_keeps_one_file(self):
        self.lib.put(b"same")
        second = self.lib.put(b"same", name="copy.heic")
        self.assertEqual(second.status, "duplicate")
        self.assertEqual(self.lib.catalog.stats().count, 1)

    def test_a_name_clash_with_different_bytes_gets_a_hash_suffix(self):
        self.lib.put(b"first")
        second = self.lib.put(b"second")
        self.assertEqual(second.record.rel_path, f"2026/10/IMG_0001-{sha(b'second')[:8]}.heic")

    def test_hash_mismatch_keeps_nothing(self):
        claim = UploadClaim("IMG.HEIC", sha256=sha(b"what the phone hashed"))
        with self.assertRaises(HarborError) as caught:
            self.lib.store.ingest(io.BytesIO(b"something else"), 14, claim)
        self.assertEqual(caught.exception.status, 422)
        self.assertEqual(self.lib.catalog.stats().count, 0)
        self.assertEqual(list(self.lib.store.photos_dir.rglob("*.*")), [])

    def test_a_short_body_is_refused_and_leaves_no_temp_file(self):
        claim = UploadClaim("IMG.HEIC")
        with self.assertRaises(HarborError):
            self.lib.store.ingest(io.BytesIO(b"abc"), 10, claim)
        self.assertEqual(list((self.lib.root / ".harbor" / "incoming").iterdir()), [])

    def test_a_malformed_hash_is_a_usage_error(self):
        with self.assertRaises(HarborError) as caught:
            self.lib.store.ingest(io.BytesIO(b"x"), 1, UploadClaim("a.jpg", sha256="abc"))
        self.assertEqual(caught.exception.status, 400)


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.record = self.lib.put(b"original").record

    def test_an_intact_file_verifies(self):
        self.assertTrue(self.lib.store.verify(self.record.sha256))

    def test_an_unknown_hash_does_not(self):
        self.assertFalse(self.lib.store.verify(sha(b"never sent")))

    def test_a_changed_file_does_not(self):
        (self.lib.store.photos_dir / self.record.rel_path).write_bytes(b"0riginal")
        self.assertFalse(self.lib.store.verify(self.record.sha256))

    def test_a_deleted_file_does_not(self):
        (self.lib.store.photos_dir / self.record.rel_path).unlink()
        self.assertFalse(self.lib.store.verify(self.record.sha256))


class CatalogAndJournalTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)

    def test_page_is_newest_taken_first(self):
        self.lib.put(b"old", name="old.jpg", taken="2020-01-01T00:00:00")
        self.lib.put(b"new", name="new.jpg", taken="2024-01-01T00:00:00")
        names = [r.original_name for r in self.lib.catalog.page(0, 10)]
        self.assertEqual(names, ["new.jpg", "old.jpg"])

    def test_missing_report_clears_once_the_photo_arrives(self):
        digest = sha(b"late")
        self.lib.journal.record("2026-10-24T10:00:00", MISSING, digest, "IMG_9.HEIC")
        self.assertEqual([m["name"] for m in self.lib.journal.missing()], ["IMG_9.HEIC"])
        self.lib.put(b"late")
        self.assertEqual(self.lib.journal.missing(), [])

    def test_last_sync_and_counts(self):
        self.lib.journal.record("2026-10-24T10:00:00", STORED, "a" * 64)
        self.lib.journal.record("2026-10-24T10:05:00", SYNC_DONE, None, "2026-10-24T09:59:00")
        self.assertEqual(self.lib.journal.last_sync(), "2026-10-24T09:59:00")
        self.assertEqual(self.lib.journal.counts_since("2026-10-24")["stored"], 1)

    def test_an_unknown_catalog_version_is_refused_untouched(self):
        self.lib.db.conn.execute("PRAGMA user_version=99")
        path = self.lib.root / ".harbor" / "catalog.sqlite3"
        with self.assertRaises(HarborError):
            Database(path)


class SearchEscapingTest(unittest.TestCase):
    def test_wildcards_in_a_search_are_literal(self):
        from photo_harbor.records import PhotoFilter
        lib = Library(self)
        lib.put(b"one", name="100%_done.jpg")
        lib.put(b"two", name="100xxdone.jpg")
        found = lib.catalog.page(0, 10, PhotoFilter(query="100%_"))
        self.assertEqual([r.original_name for r in found], ["100%_done.jpg"])


class EmbeddedDateTest(unittest.TestCase):
    def test_the_file_date_is_used_when_the_phone_sends_none(self):
        lib = Library(self)
        from photo_harbor.store import PhotoStore
        store = PhotoStore(lib.root, lib.catalog, embedded_date=lambda path: "2019-07-01T12:00:00")
        claim = UploadClaim("old.jpg", modified_at="2024-01-01T00:00:00Z")
        result = store.ingest(io.BytesIO(b"exif photo"), 10, claim)
        self.assertEqual(result.record.rel_path, "2019/07/old.jpg")


class RepairAndNamingTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)

    def test_resending_a_photo_whose_pc_copy_vanished_restores_it(self):
        record = self.lib.put(b"precious").record
        (self.lib.store.photos_dir / record.rel_path).unlink()
        again = self.lib.put(b"precious")
        self.assertEqual(again.status, "stored")
        self.assertTrue(self.lib.store.verify(record.sha256))

    def test_resending_over_a_damaged_copy_restores_it(self):
        record = self.lib.put(b"precious").record
        (self.lib.store.photos_dir / record.rel_path).write_bytes(b"precioUs")
        self.assertEqual(self.lib.put(b"precious").status, "stored")
        self.assertTrue(self.lib.store.verify(record.sha256))

    def test_a_name_held_by_a_catalogued_but_missing_file_is_not_reused(self):
        first = self.lib.put(b"first").record
        (self.lib.store.photos_dir / first.rel_path).unlink()
        second = self.lib.put(b"second").record
        self.assertNotEqual(second.rel_path, first.rel_path)
        self.assertEqual(self.lib.catalog.get(second.sha256), second)
        self.assertTrue(self.lib.store.verify(second.sha256))

    def test_a_connection_error_mid_upload_is_a_clear_failure(self):
        class Broken(io.BytesIO):
            def read(self, size=-1):
                raise ConnectionResetError("reset by peer")
        with self.assertRaises(HarborError) as caught:
            self.lib.store.ingest(Broken(), 10, UploadClaim("a.jpg"))
        self.assertIn("stopped early", caught.exception.message)
