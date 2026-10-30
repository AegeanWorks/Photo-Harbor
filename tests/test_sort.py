import unittest

from photo_harbor.records import PhotoFilter
from tests.library_fixture import Library


class SortOrderTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        for name, data, taken in (("a.jpg", b"aaa", "2026-05-01T10:00:00"),
                                  ("b.jpg", b"b", "2026-05-02T10:00:00"),
                                  ("c.jpg", b"ccccc", "2026-05-03T10:00:00")):
            self.lib.put(data, name=name, taken=taken)

    def names(self, order):
        return [record.original_name
                for record in self.lib.catalog.page(0, 10, PhotoFilter(order=order))]

    def test_each_order_is_stable_and_complete(self):
        self.assertEqual(self.names("newest"), ["c.jpg", "b.jpg", "a.jpg"])
        self.assertEqual(self.names("oldest"), ["a.jpg", "b.jpg", "c.jpg"])
        self.assertEqual(self.names("largest"), ["c.jpg", "a.jpg", "b.jpg"])
        self.assertEqual(self.names("smallest"), ["b.jpg", "a.jpg", "c.jpg"])

    def test_an_unknown_order_falls_back_to_newest(self):
        self.assertEqual(self.names("sideways"), ["c.jpg", "b.jpg", "a.jpg"])
