import unittest

from tests.library_fixture import Library


class StorageReportTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.picture = self.lib.put(b"picture", name="one.jpg",
                                    taken="2026-05-01T10:00:00").record
        self.video = self.lib.put(b"video-bytes", name="two.mp4",
                                  taken="2026-05-02T10:00:00").record
        self.lib.copies.add("ayse", self.picture, "ayse/2026/2026-05/one.jpg", "ayse.jpg",
                            "2026-05-01T11:00:00")

    def test_the_whole_library_counts_each_photo_once_and_flags_sharing(self):
        report = self.lib.catalog.storage()
        self.assertEqual((report.count, report.photos, report.videos, report.shared),
                         (2, 1, 1, 1))
        self.assertEqual(report.bytes, self.picture.size + self.video.size)
        self.assertEqual([item.name for item in report.largest], ["two.mp4", "one.jpg"])
        self.assertEqual([(p.profile, p.count) for p in report.people],
                         [("main", 2), ("ayse", 1)])

    def test_one_persons_share_uses_their_own_name_and_bytes(self):
        report = self.lib.catalog.storage("ayse")
        self.assertEqual((report.count, report.photos, report.videos, report.shared),
                         (1, 1, 0, 1))
        self.assertEqual(report.bytes, self.picture.size)
        self.assertEqual([item.name for item in report.largest], ["ayse.jpg"])
        self.assertEqual(report.people, ())
