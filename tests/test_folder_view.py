import io
import json
import unittest

from photo_harbor.archive import ArchiveBook
from photo_harbor.folders_api import FoldersApi
from photo_harbor.messages import Request
from photo_harbor.profiles import ProfileBook
from photo_harbor.records import Identity, UploadClaim
from tests.library_fixture import FIXED_NOW, Library, sha


class FoldersApiTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.book = ProfileBook(self.lib.db, "owner-key-0123456789")
        self.ayse = self.book.create("Ayşe")
        self.mine = self.lib.put(b"mine", name="mine.jpg",
                                 taken="2026-01-02T10:00:00").record.sha256
        claim = UploadClaim(original_name="hers.jpg", sha256=sha(b"hers"),
                            taken_at="2026-02-03T10:00:00", profile=self.ayse.id)
        self.lib.store.ingest(io.BytesIO(b"hers"), 4, claim)
        self.api = FoldersApi(self.book, self.lib.catalog)

    def _request(self, profile, owner):
        return Request("GET", "/api/folders", identity=Identity(profile, owner))

    def test_owner_sees_both_people_with_real_paths(self):
        data = json.loads(self.api.listing(self._request("main", True)).body)
        self.assertEqual([folder["name"] for folder in data["folders"]], ["Main", "Ayşe"])
        main = data["folders"][0]
        self.assertEqual(main["months"][0]["month"], "2026-01")
        self.assertTrue(main["months"][0]["path"].endswith("/2026/2026-01"))
        self.assertEqual(data["folders"][1]["months"][0]["month"], "2026-02")

    def test_another_person_sees_only_their_folder(self):
        data = json.loads(self.api.listing(self._request(self.ayse.id, False)).body)
        self.assertEqual([folder["name"] for folder in data["folders"]], ["Ayşe"])
        self.assertEqual(data["folders"][0]["months"][0]["month"], "2026-02")

    def test_archived_photos_leave_the_folder_tree(self):
        ArchiveBook(self.lib.db, now=lambda: FIXED_NOW).set("main", self.mine, True)
        data = json.loads(self.api.listing(self._request("main", True)).body)
        self.assertEqual([folder["name"] for folder in data["folders"]], ["Ayşe"])
