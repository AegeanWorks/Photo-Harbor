import unittest

from photo_harbor.records import PhotoFilter
from tests.library_fixture import Library


class DateFilterTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        for name, taken in (("may-first.jpg", "2026-05-01T10:00:00"),
                            ("may-tenth.jpg", "2026-05-10T10:00:00"),
                            ("june-first.jpg", "2026-06-01T10:00:00")):
            self.lib.put(name.encode(), name=name, taken=taken)

    def names(self, narrow):
        return [record.original_name for record in self.lib.catalog.page(0, 10, narrow)]

    def test_an_inclusive_range_selects_days_on_both_ends(self):
        self.assertEqual(self.names(PhotoFilter(start="2026-05-01", end="2026-05-31")),
                         ["may-tenth.jpg", "may-first.jpg"])
        self.assertEqual(self.names(PhotoFilter(start="2026-05-10", end="2026-05-10")),
                         ["may-tenth.jpg"])

    def test_either_end_can_stand_alone(self):
        self.assertEqual(self.names(PhotoFilter(start="2026-05-10")),
                         ["june-first.jpg", "may-tenth.jpg"])
        self.assertEqual(self.names(PhotoFilter(end="2026-05-01")), ["may-first.jpg"])

    def test_dates_combine_with_the_existing_narrowing(self):
        self.assertEqual(self.names(PhotoFilter(start="2026-05-01", end="2026-05-31",
                                                 query="tenth")), ["may-tenth.jpg"])
