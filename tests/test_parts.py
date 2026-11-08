import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from photo_harbor.auth import is_home_network
from photo_harbor.backup import DailyBackup, mirror, verify
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

    def test_a_json_body_split_over_chunks_is_read_whole(self):
        raw = io.BytesIO(b'7\r\n{"a": 1\r\n1\r\n}\r\n0\r\n\r\n')
        request = Request("POST", "/", body=ChunkedReader(raw), length=None)
        self.assertEqual(request.json(), {"a": 1})

    def test_a_chunked_json_body_over_the_cap_is_refused(self):
        from photo_harbor.messages import MAX_JSON_BYTES
        payload = b"x" * (MAX_JSON_BYTES + 10)
        raw = io.BytesIO(f"{len(payload):x}\r\n".encode() + payload + b"\r\n0\r\n\r\n")
        request = Request("POST", "/", body=ChunkedReader(raw), length=None)
        with self.assertRaises(HarborError) as caught:
            request.json()
        self.assertEqual(caught.exception.status, 413)


class AtomicPlacementTest(unittest.TestCase):
    def test_placing_a_new_name_refuses_an_existing_file(self):
        from photo_harbor.atomic_file import place_exclusive
        root = temp_dir(self)
        source, target = root / "incoming", root / "month" / "photo.jpg"
        target.parent.mkdir(parents=True)
        source.write_bytes(b"new bytes")
        target.write_bytes(b"older bytes")
        with self.assertRaises(FileExistsError):
            place_exclusive(source, target)
        self.assertEqual(target.read_bytes(), b"older bytes")
        self.assertEqual(source.read_bytes(), b"new bytes")

    def test_placing_moves_the_bytes_and_removes_the_source(self):
        from photo_harbor.atomic_file import place_exclusive
        root = temp_dir(self)
        source, target = root / "incoming", root / "month" / "photo.jpg"
        source.write_bytes(b"new bytes")
        place_exclusive(source, target)
        self.assertFalse(source.exists())
        self.assertEqual(target.read_bytes(), b"new bytes")

    def test_a_copy_fallback_also_refuses_an_existing_file(self):
        from unittest.mock import patch
        from photo_harbor.atomic_file import place_exclusive
        root = temp_dir(self)
        source, target = root / "incoming", root / "month" / "photo.jpg"
        target.parent.mkdir(parents=True)
        source.write_bytes(b"new bytes")
        target.write_bytes(b"older bytes")
        with patch("photo_harbor.atomic_file.os.link", side_effect=OSError("no links here")):
            with self.assertRaises(FileExistsError):
                place_exclusive(source, target)
        self.assertEqual(target.read_bytes(), b"older bytes")

    def test_a_copy_fallback_still_places_the_bytes(self):
        from unittest.mock import patch
        from photo_harbor.atomic_file import place_exclusive
        root = temp_dir(self)
        source, target = root / "incoming", root / "month" / "photo.jpg"
        source.write_bytes(b"new bytes")
        with patch("photo_harbor.atomic_file.os.link", side_effect=OSError("no links here")):
            place_exclusive(source, target)
        self.assertFalse(source.exists())
        self.assertEqual(target.read_bytes(), b"new bytes")


class RouterTest(unittest.TestCase):
    def test_exact_and_prefix_routes(self):
        router = Router()
        router.add("GET", "/", "index", public=True)
        router.add("GET", "/media/", "media")
        self.assertEqual(router.match("GET", "/").handler, "index")
        self.assertEqual(router.match("GET", "/media/abc").param, "abc")
        self.assertIsNone(router.match("GET", "/media/a/b"))
        self.assertIsNone(router.match("POST", "/media/abc"))

    def test_an_exact_trailing_slash_route_is_not_a_prefix(self):
        router = Router()
        router.add_exact("GET", "/android/", "page")
        self.assertEqual(router.match("GET", "/android/").handler, "page")
        self.assertIsNone(router.match("GET", "/android/other"))


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

    def test_verify_hashes_every_copy_and_reports_damage(self):
        root = temp_dir(self)
        source, target = root / "photos", root / "backup"
        (source / "2026" / "10").mkdir(parents=True)
        (source / "2026" / "10" / "a.heic").write_bytes(b"aaa")
        (source / "2026" / "10" / "b.heic").write_bytes(b"bbb")
        mirror(source, target)
        clean = verify(source, target)
        self.assertTrue(clean.ok)
        self.assertEqual((clean.checked, clean.bytes_checked, clean.extra), (2, 6, 0))
        (target / "2026" / "10" / "a.heic").write_bytes(b"zzz")
        (target / "2026" / "10" / "b.heic").unlink()
        (target / "2026" / "10" / "old.heic").write_bytes(b"old")
        damaged = verify(source, target)
        self.assertFalse(damaged.ok)
        self.assertEqual((damaged.checked, damaged.missing, damaged.different, damaged.extra),
                         (2, 1, 1, 1))
        self.assertEqual(sorted(kind for _, kind in damaged.problems), ["different", "missing"])

    def test_mirror_recopies_same_size_content_change(self):
        root = temp_dir(self)
        source, target = root / "photos", root / "backup"
        (source / "2026" / "10").mkdir(parents=True)
        (source / "2026" / "10" / "a.jpg").write_bytes(b"original-bytes!!")
        self.assertEqual(mirror(source, target).copied, 1)
        (target / "2026" / "10" / "a.jpg").write_bytes(b"tampered-xxxxxxx")
        report = mirror(source, target)
        self.assertEqual((report.copied, report.unchanged), (1, 0))
        self.assertEqual((target / "2026" / "10" / "a.jpg").read_bytes(),
                         b"original-bytes!!")
        self.assertTrue(verify(source, target).ok)

    def test_verify_refuses_a_target_that_is_not_there(self):
        root = temp_dir(self)
        with self.assertRaises(HarborError):
            verify(root, root / "missing")

    def test_a_missing_source_is_refused_instead_of_an_empty_success(self):
        root = temp_dir(self)
        target = root / "backup"
        target.mkdir()
        with self.assertRaises(HarborError):
            mirror(root / "missing", target)
        with self.assertRaises(HarborError):
            verify(root / "missing", target)
        missing = DailyBackup(root / "missing", target, log=lambda text: None)
        self.assertIsNotNone(missing.run_once().error)

    def test_a_backup_run_records_its_last_status(self):
        root = temp_dir(self)
        source, target = root / "photos", root / "backup"
        source.mkdir()
        (source / "a.jpg").write_bytes(b"aaa")
        backup = DailyBackup(source, target, log=lambda text: None)
        status = backup.run_once()
        self.assertIsNotNone(status.last_at)
        self.assertEqual((status.copied, status.unchanged, status.bytes_copied),
                         (1, 0, 3))
        self.assertIsNone(status.error)
        self.assertEqual(backup.status(), status)
        backup.stop()
        broken = DailyBackup(source, source / "inside", log=lambda text: None)
        self.assertIsNotNone(broken.run_once().error)


class ThumbnailerTest(unittest.TestCase):
    def test_without_pillow_previews_are_off(self):
        from photo_harbor.thumbs import Thumbnailer
        thumbs = Thumbnailer(temp_dir(self), pillow=lambda: None)
        self.assertFalse(thumbs.enabled)

    def test_prune_removes_only_previews_of_photos_that_are_gone(self):
        from photo_harbor.thumbs import Thumbnailer
        cache = temp_dir(self)
        live = "a" * 64
        gone = "b" * 64
        for digest in (live, gone):
            path = cache / digest[:2] / f"{digest}.jpg"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"jpeg")
        thumbs = Thumbnailer(cache, pillow=lambda: None)
        self.assertEqual(thumbs.prune({live}), 1)
        self.assertTrue((cache / live[:2] / f"{live}.jpg").exists())
        self.assertFalse((cache / gone[:2] / f"{gone}.jpg").exists())


class ArchiveUiTest(unittest.TestCase):
    def test_gallery_archive_is_reachable_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        for element in ('data-scope="archive"', 'id="rail-archived"',
                        'id="viewer-archive"', 'id="select-archive"'):
            self.assertIn(element, page)
        self.assertIn('params.set("archived", "1")', script)
        self.assertIn("/api/archive", script)
        self.assertIn("selectArchive", script)
        self.assertIn("bulkArchive", script)
        self.assertIn("toggleArchiveCurrent", script)


class TagUiTest(unittest.TestCase):
    def test_gallery_tags_are_reachable_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        for element in ('id="rail-tags"', 'id="tag-new"', 'id="select-tag"',
                        'id="select-tags"', 'id="viewer-tag-add"', 'id="viewer-tags"'):
            self.assertIn(element, page)
        self.assertIn('params.set("tag", String(state.scope.tag))', script)
        self.assertIn("/api/tags", script)
        self.assertIn("/api/photo-tags", script)
        self.assertIn("selectTag", script)
        self.assertIn("bulkTag", script)
        self.assertIn("toggleTagMenu", script)


class PlaceUiTest(unittest.TestCase):
    def test_gallery_places_are_reachable_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="rail-places"', page)
        self.assertIn('params.set("place", state.scope.place)', script)
        self.assertIn("placeLabel", script)
        self.assertIn("selectPlace", script)
        self.assertIn("data-place", script)


class CameraUiTest(unittest.TestCase):
    def test_gallery_cameras_are_reachable_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="rail-cameras"', page)
        self.assertIn('params.set("camera", state.scope.camera)', script)
        self.assertIn("selectCamera", script)
        self.assertIn("data-camera", script)


class SimilarUiTest(unittest.TestCase):
    def test_similar_review_is_read_only_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        for element in ('data-view="similar"', 'id="view-similar"',
                        'id="similar-scan"', 'id="similar-build"',
                        'id="similar-groups"', 'id="similar-threshold"'):
            self.assertIn(element, page)
        self.assertIn("/api/similar", script)
        self.assertIn("/api/similar/scan", script)
        self.assertIn("/api/similar/build", script)
        self.assertIn("loadSimilar", script)
        self.assertIn("scanSimilar", script)
        self.assertIn("startSimilarBuild", script)
        self.assertIn("data.threshold", script)
        self.assertIn("data.building", script)
        self.assertNotIn("deleteSimilar", script)


class MapUiTest(unittest.TestCase):
    def test_offline_map_is_embedded_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        for element in ('data-view="map"', 'id="view-map"', 'id="photo-map"',
                        'id="map-points"', 'id="map-list"', 'id="map-status"'):
            self.assertIn(element, page)
        self.assertIn("map-land", page)
        self.assertIn("loadMap", script)
        self.assertIn("mapPoint", script)
        self.assertIn("/api/outline", script)
        self.assertNotIn("tile.openstreetmap", page)
        self.assertNotIn("mapbox", page.lower())


class SidecarUiTest(unittest.TestCase):
    def test_sidecar_export_is_reachable_for_selection_and_viewer(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        for element in ('id="select-sidecar"', 'id="select-sidecars"',
                        'id="sidecar-json"', 'id="sidecar-xmp"',
                        'id="viewer-sidecar"'):
            self.assertIn(element, page)
        self.assertIn("/api/sidecar", script)
        self.assertIn("downloadSidecars", script)
        self.assertIn("sidecarCurrent", script)


class LensUiTest(unittest.TestCase):
    def test_gallery_lenses_are_reachable_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="rail-lenses"', page)
        self.assertIn('params.set("lens", state.scope.lens)', script)
        self.assertIn("selectLens", script)
        self.assertIn("data-lens", script)
        self.assertIn("outline.lenses", script)


class FolderUiTest(unittest.TestCase):
    def test_read_only_folders_view_is_wired(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        for element in ('data-view="folders"', 'id="view-folders"',
                        'id="folders-tree"', 'id="folders-status"'):
            self.assertIn(element, page)
        self.assertIn("/api/folders", script)
        self.assertIn("loadFolders", script)
        self.assertIn("openFolder", script)


class AndroidVersionTest(unittest.TestCase):
    def test_gallery_android_card_has_live_download_controls(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "photo_harbor" / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="android-download"', page)
        self.assertIn('id="android-meta"', page)
        self.assertIn("/android/Harbor.apk", page)
        self.assertIn("/api/android", script)
        self.assertIn("loadAndroid", script)

    def test_android_page_loads_its_script_from_a_csp_allowed_file(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "photo_harbor" / "web" / "android" / "index.html").read_text(
            encoding="utf-8")
        self.assertNotIn("<script>", page)
        self.assertNotIn("<style>", page)
        self.assertIn('src="/android/meta.js"', page)
        self.assertIn('href="/android/style.css"', page)
        self.assertTrue((root / "photo_harbor" / "web" / "android" / "meta.js").is_file())
        self.assertTrue((root / "photo_harbor" / "web" / "android" / "style.css").is_file())

    def test_android_requests_partial_media_access(self):
        root = Path(__file__).resolve().parents[1]
        activity = (root / "android" / "src" / "works" / "aegean" / "harbor"
                    / "MainActivity.java").read_text(encoding="utf-8")
        engine = (root / "android" / "src" / "works" / "aegean" / "harbor"
                  / "SyncEngine.java").read_text(encoding="utf-8")
        self.assertIn("READ_MEDIA_VISUAL_USER_SELECTED", activity)
        self.assertIn("hasMediaAccess", engine)
        self.assertIn("READ_MEDIA_VISUAL_USER_SELECTED", engine)

    def test_android_version_constants_match_the_build(self):
        import hashlib
        import json
        import re
        root = Path(__file__).resolve().parents[1]
        build = (root / "android" / "build.py").read_text(encoding="utf-8")
        activity = (root / "android" / "src" / "works" / "aegean" / "harbor"
                    / "MainActivity.java").read_text(encoding="utf-8")
        manifest_text = (root / "android" / "AndroidManifest.xml").read_text(encoding="utf-8")
        sidecar_path = root / "photo_harbor" / "web" / "android" / "Harbor.apk.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        version = re.search(r'VERSION\s*=\s*"([^"]+)"', build).group(1)
        code = re.search(r"VERSION_CODE\s*=\s*(\d+)", build).group(1)
        self.assertEqual(version, re.search(r'VERSION_NAME\s*=\s*"([^"]+)"', activity).group(1))
        self.assertEqual(code, re.search(r"VERSION_CODE\s*=\s*(\d+)", activity).group(1))
        self.assertEqual(version, re.search(r'versionName="([^"]+)"', manifest_text).group(1))
        self.assertEqual(code, re.search(r'versionCode="(\d+)"', manifest_text).group(1))
        self.assertEqual((version, code), (sidecar["version"], str(sidecar["versionCode"])))
        apk = (root / "photo_harbor" / "web" / "android" / "Harbor.apk").read_bytes()
        self.assertEqual(sidecar["size"], len(apk))
        self.assertEqual(sidecar["sha256"], hashlib.sha256(apk).hexdigest())


class CliErrorTest(unittest.TestCase):
    def test_an_oserror_is_a_clear_failure_not_a_traceback(self):
        import contextlib
        import io
        from unittest.mock import patch
        from photo_harbor.__main__ import main
        root = temp_dir(self)
        target = root / "backup"
        with patch("photo_harbor.backup.verify", side_effect=OSError("locked file")):
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                code = main(["--library", str(root), "backup", "--to", str(target), "--check"])
        self.assertEqual(code, 1)
        text = errors.getvalue()
        self.assertIn("Error:", text)
        self.assertIn("Why:", text)
        self.assertNotIn("Traceback", text)


class PasswordHashTest(unittest.TestCase):
    def test_malformed_stored_hash_returns_false_not_500(self):
        from photo_harbor.accounts import password_matches
        self.assertFalse(password_matches("x", "pbkdf2_sha256$notanint$c2FsdA==$aGFzaA=="))
        self.assertFalse(password_matches("x", "pbkdf2_sha256$240000$!!!$AAA="))
        self.assertFalse(password_matches("x", "not-a-hash"))

    def test_lan_address_falls_back_when_socket_creation_fails(self):
        import socket
        from unittest.mock import patch
        from photo_harbor.setup_api import lan_address
        with patch.object(socket, "socket", side_effect=OSError("too many open files")):
            self.assertEqual(lan_address(), "127.0.0.1")

    def test_sync_done_rejects_a_future_started_at(self):
        import io
        import json
        from photo_harbor.errors import HarborError
        from photo_harbor.messages import Request
        from photo_harbor.records import Identity
        from photo_harbor.sync_api import SyncApi
        from tests.library_fixture import Library
        lib = Library(self)
        api = SyncApi(lib.store, lib.journal, None)
        body = json.dumps({"started_at": "2999-01-01T00:00:00+00:00"}).encode()
        req = Request("POST", "/api/sync/done", body=io.BytesIO(body), length=len(body),
                      identity=Identity("main", True))
        with self.assertRaises(HarborError) as ctx:
            api.done(req)
        self.assertEqual(ctx.exception.status, 400)

    def test_sync_done_rejects_a_naive_future_started_at(self):
        import io
        import json
        from photo_harbor.errors import HarborError
        from photo_harbor.messages import Request
        from photo_harbor.records import Identity
        from photo_harbor.sync_api import SyncApi
        from tests.library_fixture import Library
        lib = Library(self)
        api = SyncApi(lib.store, lib.journal, None)
        body = json.dumps({"started_at": "2999-01-01T00:00:00"}).encode()
        req = Request("POST", "/api/sync/done", body=io.BytesIO(body), length=len(body),
                      identity=Identity("main", True))
        with self.assertRaises(HarborError) as ctx:
            api.done(req)
        self.assertEqual(ctx.exception.status, 400)

    def test_sync_done_rejects_future_when_clocks_mix_naive_and_aware(self):
        import io
        import json
        from datetime import datetime
        from photo_harbor.errors import HarborError
        from photo_harbor.messages import Request
        from photo_harbor.records import Identity
        from photo_harbor.sync_api import SyncApi
        from tests.library_fixture import Library
        lib = Library(self)
        api = SyncApi(lib.store, lib.journal, None,
                      now=lambda: datetime(2026, 5, 1, 12, 0, 0))
        body = json.dumps({"started_at": "2999-01-01T00:00:00+00:00"}).encode()
        req = Request("POST", "/api/sync/done", body=io.BytesIO(body), length=len(body),
                      identity=Identity("main", True))
        with self.assertRaises(HarborError) as ctx:
            api.done(req)
        self.assertEqual(ctx.exception.status, 400)

    def test_start_ignores_a_future_cursor_left_by_an_old_clock(self):
        import json
        from datetime import datetime, timezone
        from photo_harbor.journal import SYNC_DONE
        from photo_harbor.messages import Request
        from photo_harbor.records import Identity
        from photo_harbor.sync_api import FIRST_SYNC_SINCE, SyncApi
        from tests.library_fixture import Library
        lib = Library(self)
        now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        for cursor in ("2999-01-01T00:00:00+00:00", "2999-01-01T00:00:00"):
            lib.journal.record("2026-05-01T12:00:00+00:00", SYNC_DONE, None, cursor)
            api = SyncApi(lib.store, lib.journal, None, now=lambda: now)
            reply = api.start(Request("POST", "/api/sync/start",
                                      identity=Identity("main", True)))
            self.assertEqual(json.loads(reply.body)["since"], FIRST_SYNC_SINCE, cursor)

    def test_media_and_thumb_vary_by_cookie(self):
        import io
        from photo_harbor.albums import AlbumBook
        from photo_harbor.library_api import LibraryApi
        from photo_harbor.messages import Request
        from photo_harbor.records import Identity
        from photo_harbor.tags import TagBook
        from tests.library_fixture import Library
        lib = Library(self)
        rec = lib.put(b"img", name="a.jpg").record

        class _Thumbs:
            def preview(self, record, original):
                return original

        api = LibraryApi(lib.store, lib.catalog, lib.journal, _Thumbs(),
                          AlbumBook(lib.db), TagBook(lib.db), now=lambda: None)
        ident = Identity("main", True)
        for reply in (api.media(Request("GET", f"/media/{rec.sha256}",
                                        identity=ident), rec.sha256),
                      api.thumb(Request("GET", f"/thumb/{rec.sha256}",
                                        identity=ident), rec.sha256)):
            headers = dict(reply.headers)
            self.assertIn("must-revalidate", headers.get("Cache-Control", ""))
            self.assertNotIn("immutable", headers.get("Cache-Control", ""))
            self.assertEqual(headers.get("Vary"), "Cookie")

    def test_warmer_survives_a_catalog_failure(self):
        import queue
        import time
        from photo_harbor.thumbs import PreviewWarmer

        class BoomOnce:
            def __init__(self):
                self.calls = 0
                self.records = []

            def page(self, offset, limit):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("db boom")
                return []

        class FakeStore:
            def locate(self, sha):
                return None

        class FakeThumbs:
            def preview(self, *args):
                return None

        warmer = PreviewWarmer(FakeThumbs(), BoomOnce(), FakeStore(), page=10)
        warmer.start()
        self.addCleanup(warmer.stop)
        deadline = time.time() + 5
        while not warmer._thread.is_alive() and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.5)
        self.assertTrue(warmer._thread.is_alive())

    def test_warmer_retries_backlog_after_a_transient_failure(self):
        import time
        from photo_harbor.records import PhotoRecord
        from photo_harbor.thumbs import PreviewWarmer

        record = PhotoRecord(sha256="a" * 64, rel_path="Main/2026/2026-10/a.jpg",
                             size=3, original_name="a.jpg", media_type="image/jpeg",
                             taken_at=None, received_at="2026-10-24T12:00:00")

        class FlakyCatalog:
            def __init__(self):
                self.calls = 0

            def page(self, offset, limit):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("transient db boom")
                if offset == 0:
                    return [record]
                return []

        class FakeStore:
            def __init__(self):
                self.lookups = 0

            def locate(self, sha):
                self.lookups += 1
                return ("original-path", record)

        class FakeThumbs:
            def __init__(self):
                self.previews = 0

            def preview(self, *args):
                self.previews += 1
                return "preview-path"

        catalog, store, thumbs = FlakyCatalog(), FakeStore(), FakeThumbs()
        warmer = PreviewWarmer(thumbs, catalog, store, page=10)
        warmer.start()
        self.addCleanup(warmer.stop)
        deadline = time.time() + 10
        while thumbs.previews == 0 and time.time() < deadline:
            time.sleep(0.05)
        self.assertEqual(thumbs.previews, 1)

    def test_too_long_password_names_the_maximum(self):
        from photo_harbor.accounts import check_new_password
        from photo_harbor.errors import HarborError
        with self.assertRaises(HarborError) as ctx:
            check_new_password("x" * 201)
        self.assertIn("at most 200", ctx.exception.fix)
        with self.assertRaises(HarborError) as ctx:
            check_new_password("x" * 5)
        self.assertIn("at least 6", ctx.exception.fix)

    def test_details_corrupt_exif_returns_file_facts(self):
        from unittest.mock import patch
        from photo_harbor.details import read_details
        from tests.test_details import record_for
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.jpg"
            path.write_bytes(b"not jpeg")

            class BadExif(dict):
                def get(self, k, d=None):
                    raise ValueError("bad tag decode")

                def get_ifd(self, _):
                    return {}

            class FakeImg:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                @property
                def size(self):
                    return (10, 10)

                def getexif(self):
                    return BadExif()

            with patch("photo_harbor.details.load_image") as loader:
                loader.return_value = type("M", (), {"open": staticmethod(lambda p: FakeImg())})
                facts = read_details(record_for(path, "x.jpg"), path)
            self.assertEqual(facts["name"], "x.jpg")
            self.assertIsNone(facts["width"])


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
