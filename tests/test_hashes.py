import unittest

from photo_harbor.records import PhotoFilter
from tests.library_fixture import Library


class HashSelectionTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.records = [self.lib.put(data, name=name, taken=taken).record
                        for data, name, taken in (
                            (b"a", "a.jpg", "2026-05-01T10:00:00"),
                            (b"bb", "b.jpg", "2026-05-02T10:00:00"),
                            (b"ccc", "c.jpg", "2026-06-01T10:00:00"))]

    def test_hashes_follow_the_same_filter_and_order_as_the_page(self):
        self.assertEqual(self.lib.catalog.hashes(PhotoFilter(order="oldest")),
                         [record.sha256 for record in self.records])
        self.assertEqual(self.lib.catalog.hashes(PhotoFilter(order="largest")),
                         [self.records[2].sha256, self.records[1].sha256,
                          self.records[0].sha256])
        self.assertEqual(self.lib.catalog.hashes(PhotoFilter(start="2026-05-01",
                                                              end="2026-05-31")),
                         [self.records[1].sha256, self.records[0].sha256])

    def test_a_limit_caps_the_result(self):
        self.assertEqual(len(self.lib.catalog.hashes(PhotoFilter(), limit=2)), 2)

    def test_negative_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            self.lib.catalog.hashes(PhotoFilter(), limit=-1)
        with self.assertRaises(ValueError):
            self.lib.catalog.page(0, -1)

    def test_known_and_copies_of_chunk_large_batches(self):
        import hashlib
        big = [hashlib.sha256(f"k{i}".encode()).hexdigest() for i in range(2000)]
        self.assertEqual(self.lib.catalog.known(big), set())
        self.assertEqual(self.lib.catalog.copies_of("main", big), set())
        have = [r.sha256 for r in self.records]
        self.assertEqual(self.lib.catalog.known(have + big[:1500]), set(have))
