import unittest

from photo_harbor.archive import ArchiveBook
from photo_harbor.records import PhotoFilter, PhotoRecord
from tests.library_fixture import FIXED_NOW, Library, sha


class LensFilterTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.wide = self._add(b"wide", "wide.jpg", "16-35 mm")
        self.prime = self._add(b"prime", "prime.jpg", "35 mm")
        self.none = self._add(b"none", "none.jpg", None)

    def _add(self, data, name, lens):
        digest = sha(data)
        record = PhotoRecord(
            sha256=digest, rel_path=f"main/2026/2026-01/{name}", size=len(data),
            original_name=name, media_type="image/jpeg", taken_at="2026-01-01T10:00:00",
            received_at="2026-01-01T11:00:00", profile="main", lens=lens)
        self.lib.catalog.add(record)
        return digest

    def test_a_lens_filters_and_lists_the_rail(self):
        page = self.lib.catalog.page(0, 10, PhotoFilter(lens="35 mm", viewer="main"))
        self.assertEqual([record.sha256 for record in page], [self.prime])
        self.assertEqual(self.lib.catalog.outline(viewer="main").lenses,
                         (("16-35 mm", 1), ("35 mm", 1)))

    def test_archiving_removes_the_lens_count(self):
        ArchiveBook(self.lib.db, now=lambda: FIXED_NOW).set("main", self.prime, True)
        self.assertEqual(self.lib.catalog.outline(viewer="main").lenses,
                         (("16-35 mm", 1),))
        page = self.lib.catalog.page(0, 10, PhotoFilter(lens="35 mm", viewer="main"))
        self.assertEqual(page, [])

    def test_another_person_sees_only_their_copies(self):
        self.assertEqual(self.lib.catalog.page(
            0, 10, PhotoFilter(lens="35 mm", profile="ayse", viewer="ayse")), [])
        self.assertEqual(self.lib.catalog.outline(profile="ayse", viewer="ayse").lenses, ())
