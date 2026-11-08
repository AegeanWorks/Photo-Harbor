import unittest
from pathlib import Path
from unittest.mock import patch

from photo_harbor.archive import ArchiveBook
from photo_harbor.database import SCHEMA_VERSION, Database
from photo_harbor.geo import read_place
from photo_harbor.records import PhotoFilter, PhotoRecord
from tests.library_fixture import FIXED_NOW, Library, sha


class _Exif:
    def __init__(self, gps):
        self.gps = gps

    def get_ifd(self, number):
        return self.gps


class _Image:
    def __init__(self, gps):
        self.gps = gps

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getexif(self):
        return _Exif(self.gps)


class _ImageModule:
    def __init__(self, gps):
        self.gps = gps

    def open(self, path):
        return _Image(self.gps)


class GeoTest(unittest.TestCase):
    def test_degrees_minutes_seconds_and_south_west_are_signed(self):
        gps = {1: "S", 2: (37, 30, 0), 3: "W", 4: (23, 15, 0)}
        with patch("photo_harbor.geo.load_image", return_value=_ImageModule(gps)):
            self.assertEqual(read_place(Path("x.jpg")), (-37.5, -23.25))

    def test_missing_or_out_of_range_gps_is_none(self):
        with patch("photo_harbor.geo.load_image", return_value=_ImageModule({})):
            self.assertIsNone(read_place(Path("x.jpg")))
        bad = {1: "N", 2: (100, 0, 0), 3: "E", 4: (23, 0, 0)}
        with patch("photo_harbor.geo.load_image", return_value=_ImageModule(bad)):
            self.assertIsNone(read_place(Path("x.jpg")))
        with patch("photo_harbor.geo.load_image", return_value=None):
            self.assertIsNone(read_place(Path("x.jpg")))


class PlaceFilterTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.placed = self._add(b"placed", "placed.jpg", 37.04, 23.72)
        self.plain = self._add(b"plain", "plain.jpg", None, None)

    def _add(self, data, name, latitude, longitude):
        digest = sha(data)
        record = PhotoRecord(
            sha256=digest, rel_path=f"main/2026/2026-01/{name}", size=len(data),
            original_name=name, media_type="image/jpeg", taken_at="2026-01-01T10:00:00",
            received_at="2026-01-01T11:00:00", profile="main",
            latitude=latitude, longitude=longitude)
        self.lib.catalog.add(record)
        return digest

    def test_a_coarse_point_filters_and_lists_places(self):
        page = self.lib.catalog.page(0, 10, PhotoFilter(place=(37.0, 23.7), viewer="main"))
        self.assertEqual([record.sha256 for record in page], [self.placed])
        outline = self.lib.catalog.outline(viewer="main")
        self.assertEqual(outline.places, ((37.0, 23.7, 1),))

    def test_archived_photos_leave_places(self):
        ArchiveBook(self.lib.db, now=lambda: FIXED_NOW).set("main", self.placed, True)
        self.assertEqual(self.lib.catalog.outline(viewer="main").places, ())
        page = self.lib.catalog.page(0, 10, PhotoFilter(place=(37.0, 23.7), viewer="main"))
        self.assertEqual(page, [])


class PlaceMigrationTest(unittest.TestCase):
    def test_a_format_9_catalog_gains_the_gps_columns(self):
        lib = Library(self)
        path = lib.root / "v9.sqlite3"
        old = Database(path)
        old.conn.executescript("ALTER TABLE photos DROP COLUMN latitude;"
                               "ALTER TABLE photos DROP COLUMN longitude;"
                               "PRAGMA user_version=9;")
        old.close()
        db = Database(path)
        self.addCleanup(db.close)
        self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        columns = [row[1] for row in db.conn.execute("PRAGMA table_info(photos)")]
        self.assertIn("latitude", columns)
        self.assertIn("longitude", columns)
        self.assertTrue((lib.root / "v9.sqlite3.v9.bak").exists())
