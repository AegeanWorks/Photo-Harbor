import unittest
from pathlib import Path
from unittest.mock import patch

from photo_harbor.archive import ArchiveBook
from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.details import read_camera
from photo_harbor.records import PhotoFilter, PhotoRecord
from tests.library_fixture import FIXED_NOW, Library, sha


class _Exif:
    def __init__(self, tags):
        self.tags = tags

    def get_ifd(self, number):
        return self.tags

    def get(self, number):
        return None


class _Image:
    def __init__(self, tags):
        self.tags = tags

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getexif(self):
        return _Exif(self.tags)


class _ImageModule:
    def __init__(self, tags):
        self.tags = tags

    def open(self, path):
        return _Image(self.tags)


class CameraTest(unittest.TestCase):
    def test_make_model_and_lens_are_read_together(self):
        tags = {0x010F: "Acme", 0x0110: "Cam 1", 0xA434: "35 mm"}
        with patch("photo_harbor.details.load_image", return_value=_ImageModule(tags)):
            self.assertEqual(read_camera(Path("x.jpg")), ("Acme Cam 1", "35 mm"))

    def test_unreadable_or_missing_exif_is_empty(self):
        with patch("photo_harbor.details.load_image", return_value=_ImageModule({})):
            self.assertEqual(read_camera(Path("x.jpg")), (None, None))
        with patch("photo_harbor.details.load_image", return_value=None):
            self.assertEqual(read_camera(Path("x.jpg")), (None, None))


class CameraFilterTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.shot = self._add(b"shot", "shot.jpg", "Acme Cam 1")
        self.plain = self._add(b"plain", "plain.jpg", None)

    def _add(self, data, name, camera):
        digest = sha(data)
        record = PhotoRecord(
            sha256=digest, rel_path=f"main/2026/2026-01/{name}", size=len(data),
            original_name=name, media_type="image/jpeg", taken_at="2026-01-01T10:00:00",
            received_at="2026-01-01T11:00:00", profile="main", camera=camera)
        self.lib.catalog.add(record)
        return digest

    def test_a_camera_filters_and_lists_the_rail(self):
        page = self.lib.catalog.page(0, 10,
                                     PhotoFilter(camera="Acme Cam 1", viewer="main"))
        self.assertEqual([record.sha256 for record in page], [self.shot])
        self.assertEqual(self.lib.catalog.outline(viewer="main").cameras,
                         (("Acme Cam 1", 1),))

    def test_archiving_removes_the_camera_count(self):
        ArchiveBook(self.lib.db, now=lambda: FIXED_NOW).set("main", self.shot, True)
        self.assertEqual(self.lib.catalog.outline(viewer="main").cameras, ())
        page = self.lib.catalog.page(0, 10,
                                     PhotoFilter(camera="Acme Cam 1", viewer="main"))
        self.assertEqual(page, [])


class CameraMigrationTest(unittest.TestCase):
    def test_a_format_10_catalog_gains_the_camera_columns(self):
        lib = Library(self)
        path = lib.root / "v10.sqlite3"
        old = Database(path)
        old.conn.executescript("ALTER TABLE photos DROP COLUMN camera;"
                               "ALTER TABLE photos DROP COLUMN lens;"
                               "PRAGMA user_version=10;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        columns = [row[1] for row in db.conn.execute("PRAGMA table_info(photos)")]
        self.assertIn("camera", columns)
        self.assertIn("lens", columns)
        self.assertTrue((lib.root / "v10.sqlite3.v10.bak").exists())
