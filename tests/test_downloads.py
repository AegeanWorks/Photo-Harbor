import hashlib
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from photo_harbor.downloads import Downloads, TTL_SECONDS
from photo_harbor.errors import HarborError
from photo_harbor.records import PhotoRecord


class DownloadsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="harbor_downloads_"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.now = 1000.0
        self.downloads = Downloads(self.root, clock=lambda: self.now)
        self.one = self.photo(b"one", "one.jpg")
        self.two = self.photo(b"two", "two.jpg")

    def photo(self, data: bytes, name: str):
        path = self.root / name
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        record = PhotoRecord(
            sha256=digest, rel_path=f"main/2026/2026-05/{name}", size=len(data),
            original_name=name, media_type="image/jpeg", taken_at="2026-05-01T10:00:00",
            received_at="2026-05-01T11:00:00")
        return record, path

    def test_a_selection_becomes_one_zip_with_original_names(self):
        info = self.downloads.prepare([self.one, self.two], "Harbor - selection.zip", "main")
        self.assertEqual((info["count"], info["bytes"]), (2, 6))
        self.assertTrue(info["url"].startswith("/api/download/"))
        path, name, total = self.downloads.take(info["url"].rsplit("/", 1)[-1], "main")
        self.assertEqual((name, total), ("Harbor - selection.zip", 6))
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.namelist(), ["one.jpg", "two.jpg"])
            self.assertEqual(archive.read("one.jpg"), b"one")
        path.unlink()

    def test_duplicate_names_get_a_hash_prefix(self):
        same_record, same_path = self.photo(b"three", "one.jpg")
        same_record = PhotoRecord(**{**same_record.__dict__, "sha256": "b" * 64})
        info = self.downloads.prepare([self.one, (same_record, same_path)], "Harbor.zip", "main")
        path, _, _ = self.downloads.take(info["url"].rsplit("/", 1)[-1], "main")
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.namelist(), ["one.jpg", f"{'b' * 8}-one.jpg"])
        path.unlink()

    def test_a_token_expires_and_removes_its_file(self):
        info = self.downloads.prepare([self.one], "Harbor.zip", "main")
        token = info["url"].rsplit("/", 1)[-1]
        self.now += TTL_SECONDS + 1
        self.assertIsNone(self.downloads.take(token, "main"))
        self.assertEqual(list(self.root.glob("*.zip")), [])

    def test_a_token_belongs_to_the_person_who_prepared_it(self):
        info = self.downloads.prepare([self.one], "Harbor.zip", "main")
        token = info["url"].rsplit("/", 1)[-1]
        self.assertIsNone(self.downloads.take(token, "ayse"))
        self.assertIsNotNone(self.downloads.take(token, "main"))

    def test_an_empty_download_is_refused(self):
        with self.assertRaises(HarborError):
            self.downloads.prepare([], "Harbor.zip", "main")
