import unittest

from photo_harbor.records import PhotoFilter
from tests.library_fixture import Library


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.lib.put(b"one", name="may-tenth.jpg", taken="2026-05-10T10:00:00")
        self.lib.put(b"two", name="may-first.jpg", taken="2026-05-01T10:00:00")
        self.lib.put(b"three", name="june-trip.jpg", taken="2026-06-01T10:00:00")

    def names(self, query, **kwargs):
        return [record.original_name
                for record in self.lib.catalog.page(0, 10, PhotoFilter(query=query, **kwargs))]

    def test_every_word_must_appear_in_the_file_name(self):
        self.assertEqual(self.names("may tenth"), ["may-tenth.jpg"])
        self.assertEqual(self.names("may"), ["may-tenth.jpg", "may-first.jpg"])
        self.assertEqual(self.names("tenth june"), [])

    def test_search_combines_with_other_narrowing(self):
        self.assertEqual(self.names("may", start="2026-05-05"), ["may-tenth.jpg"])
        self.assertEqual(self.names("may", start="2026-06-01"), [])

    def test_like_wildcards_are_literal(self):
        self.lib.put(b"four", name="100%-done.jpg", taken="2026-05-11T10:00:00")
        self.assertEqual(self.names("100%"), ["100%-done.jpg"])
        self.assertEqual(self.names("100_"), [])
