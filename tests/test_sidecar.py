import io
import json
import unittest
import zipfile

from photo_harbor.errors import HarborError
from photo_harbor.messages import Request
from photo_harbor.records import Identity
from photo_harbor.sidecar import SidecarApi
from photo_harbor.tags import TagBook
from tests.library_fixture import Library, sha


class SidecarTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.tags = TagBook(self.lib.db)
        self.one = self.lib.put(b"one", name="one.jpg").record.sha256
        self.two = self.lib.put(b"two", name="same.jpg").record.sha256
        with self.lib.db.lock:
            self.lib.db.conn.execute(
                "UPDATE photos SET camera = ?, lens = ?, latitude = ?, longitude = ?"
                " WHERE sha256 = ?", ("Acme Cam 1", "35 mm", 37.04, 23.72, self.one))
            self.lib.db.conn.execute(
                "UPDATE photos SET camera = ?, lens = ?, latitude = ?, longitude = ?"
                " WHERE sha256 = ?", ("Acme Cam 1", "50 mm", 40.1, 20.2, self.two))
        tag = self.tags.create("main", "Beach & sun")
        self.tags.add("main", tag.id, self.one, True)
        self.api = SidecarApi(self.lib.catalog, self.tags)

    def _request(self, body):
        payload = json.dumps(body).encode()
        return Request("POST", "/api/sidecar", body=io.BytesIO(payload), length=len(payload),
                       identity=Identity("main", True))

    def _zip(self, body):
        reply = self.api.export(self._request(body))
        return zipfile.ZipFile(io.BytesIO(reply.body))

    def test_json_sidecar_contains_tags_place_and_camera(self):
        archive = self._zip({"sha256s": [self.one]})
        names = archive.namelist()
        self.assertEqual(names, ["one.json"])
        data = json.loads(archive.read(names[0]))
        self.assertEqual((data["camera"], data["lens"]), ("Acme Cam 1", "35 mm"))
        self.assertEqual((data["latitude"], data["longitude"]), (37.04, 23.72))
        self.assertEqual(data["tags"], ["Beach & sun"])

    def test_xmp_sidecar_escapes_tags_and_writes_gps(self):
        archive = self._zip({"sha256s": [self.one], "format": "xmp"})
        text = archive.read("one.xmp").decode("utf-8")
        self.assertIn("<rdf:li>Beach &amp; sun</rdf:li>", text)
        self.assertIn("<exif:GPSLatitude>37,2.400000N</exif:GPSLatitude>", text)
        self.assertIn("<exif:GPSLongitude>23,43.200000E</exif:GPSLongitude>", text)
        self.assertIn("<tiff:Model>Acme Cam 1</tiff:Model>", text)

    def test_duplicate_names_get_unique_sidecar_files(self):
        archive = self._zip({"sha256s": [self.one, self.two]})
        names = sorted(archive.namelist())
        self.assertEqual(len(names), 2)
        self.assertEqual(len(set(names)), 2)
        self.assertTrue(all(name.endswith(".json") for name in names))

    def test_another_person_cannot_export_someone_elses_photo(self):
        payload = json.dumps({"sha256s": [self.one]}).encode()
        request = Request("POST", "/api/sidecar", body=io.BytesIO(payload),
                          length=len(payload), identity=Identity("ayse", False))
        with self.assertRaises(HarborError):
            self.api.export(request)

    def test_format_and_empty_selection_are_clear_errors(self):
        with self.assertRaises(HarborError):
            self.api.export(self._request({"sha256s": [self.one], "format": "pdf"}))
        with self.assertRaises(HarborError):
            self.api.export(self._request({"sha256s": []}))
