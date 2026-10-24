import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from photo_harbor.auth import is_home_network
from photo_harbor.backup import mirror
from photo_harbor.body_readers import ChunkedReader, LengthReader
from photo_harbor.config import load_or_create, rotate_key
from photo_harbor.errors import HarborError
from photo_harbor.messages import Request, parse_range
from photo_harbor.router import Router


def temp_dir(test_case) -> Path:
    path = Path(tempfile.mkdtemp(prefix="harbor_parts_"))
    test_case.addCleanup(shutil.rmtree, path, True)
    return path


class RangeTest(unittest.TestCase):
    def test_closed_open_and_suffix_ranges(self):
        self.assertEqual(parse_range("bytes=2-4", 10), (2, 4))
        self.assertEqual(parse_range("bytes=7-", 10), (7, 9))
        self.assertEqual(parse_range("bytes=-3", 10), (7, 9))

    def test_unsatisfiable_or_multiple_ranges_mean_the_whole_file(self):
        self.assertIsNone(parse_range("bytes=12-20", 10))
        self.assertIsNone(parse_range("bytes=0-1,4-5", 10))
        self.assertIsNone(parse_range("items=0-1", 10))


class BodyReaderTest(unittest.TestCase):
    def test_length_reader_stops_at_the_length(self):
        reader = LengthReader(io.BytesIO(b"abcdef"), 4)
        self.assertEqual(reader.read(), b"abcd")
        self.assertTrue(reader.exhausted)

    def test_chunked_reader_decodes_and_consumes_the_trailer(self):
        raw = io.BytesIO(b"3\r\nabc\r\n2;ext=1\r\nde\r\n0\r\n\r\nNEXT")
        reader = ChunkedReader(raw)
        self.assertEqual(reader.read(10) + reader.read(10) + reader.read(10), b"abcde")
        self.assertTrue(reader.exhausted)
        self.assertEqual(raw.read(), b"NEXT")

    def test_json_body_must_be_an_object(self):
        request = Request("POST", "/", body=io.BytesIO(b"[1]"), length=3)
        with self.assertRaises(HarborError):
            request.json()


class RouterTest(unittest.TestCase):
    def test_exact_and_prefix_routes(self):
        router = Router()
        router.add("GET", "/", "index", public=True)
        router.add("GET", "/media/", "media")
        self.assertEqual(router.match("GET", "/").handler, "index")
        self.assertEqual(router.match("GET", "/media/abc").param, "abc")
        self.assertIsNone(router.match("GET", "/media/a/b"))
        self.assertIsNone(router.match("POST", "/media/abc"))


class HomeNetworkTest(unittest.TestCase):
    def test_private_addresses_are_home(self):
        for address in ("192.168.1.20", "10.0.0.5", "127.0.0.1", "::ffff:192.168.1.9", "fe80::1%12"):
            self.assertTrue(is_home_network(address), address)

    def test_public_addresses_are_not(self):
        self.assertFalse(is_home_network("8.8.8.8"))
        self.assertFalse(is_home_network("not an ip"))


class ConfigTest(unittest.TestCase):
    def test_first_run_creates_a_key_that_later_runs_reuse(self):
        library = temp_dir(self)
        first = load_or_create(library)
        self.assertGreaterEqual(len(first.key), 16)
        self.assertEqual(load_or_create(library).key, first.key)

    def test_a_damaged_file_is_restored_from_its_backup(self):
        library = temp_dir(self)
        rotate_key(library)
        second = rotate_key(library)
        config = library / ".harbor" / "config.json"
        config.write_text("{broken", encoding="utf-8")
        restored = load_or_create(library)
        self.assertNotEqual(restored.key, second.key)
        self.assertTrue((library / ".harbor" / "config.json.corrupt").exists())

    def test_an_unknown_version_is_refused_without_touching_the_file(self):
        library = temp_dir(self)
        config = library / ".harbor" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"version": 9, "key": "x" * 20}), encoding="utf-8")
        with self.assertRaises(HarborError):
            load_or_create(library)
        self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["version"], 9)


class BackupTest(unittest.TestCase):
    def test_copies_new_files_and_skips_ones_already_there(self):
        root = temp_dir(self)
        source, target = root / "photos", root / "backup"
        (source / "2026" / "10").mkdir(parents=True)
        (source / "2026" / "10" / "a.heic").write_bytes(b"aaa")
        first = mirror(source, target)
        second = mirror(source, target)
        self.assertEqual((first.copied, second.copied, second.unchanged), (1, 0, 1))
        self.assertEqual((target / "2026" / "10" / "a.heic").read_bytes(), b"aaa")

    def test_refuses_a_target_inside_the_library(self):
        root = temp_dir(self)
        with self.assertRaises(HarborError):
            mirror(root, root / "inside")


class ThumbnailerTest(unittest.TestCase):
    def test_without_pillow_previews_are_off(self):
        from photo_harbor.thumbs import Thumbnailer
        thumbs = Thumbnailer(temp_dir(self), pillow=lambda: None)
        self.assertFalse(thumbs.enabled)


class DamagedConfigTest(unittest.TestCase):
    def test_both_copies_damaged_is_a_clear_error(self):
        library = temp_dir(self)
        rotate_key(library)
        rotate_key(library)
        state = library / ".harbor"
        (state / "config.json").write_text("{", encoding="utf-8")
        (state / "config.json.bak").write_text("{", encoding="utf-8")
        with self.assertRaises(HarborError):
            load_or_create(library)
