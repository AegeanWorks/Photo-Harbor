import unittest

from photo_harbor.journal import STORED, SYNC_DONE
from tests.library_fixture import Library


class JournalRecentTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)

    def test_recent_events_are_newest_first_and_limit(self):
        self.lib.journal.record("2026-01-01T10:00:00", STORED, None, "one.jpg", "main")
        self.lib.journal.record("2026-01-02T10:00:00", SYNC_DONE, None,
                                "2026-01-02T09:00:00", "main")
        events = self.lib.journal.recent(limit=1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], SYNC_DONE)
        self.assertEqual(events[0]["profile"], "main")

    def test_one_person_sees_only_their_events(self):
        self.lib.journal.record("2026-01-01T10:00:00", STORED, None, "old.jpg", None)
        self.lib.journal.record("2026-01-02T10:00:00", STORED, None, "hers.jpg", "ayse")
        main = self.lib.journal.recent(profile="main")
        hers = self.lib.journal.recent(profile="ayse")
        self.assertEqual([event["detail"] for event in main], ["old.jpg"])
        self.assertEqual([event["detail"] for event in hers], ["hers.jpg"])
