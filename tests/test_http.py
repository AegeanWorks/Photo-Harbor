"""The server over a real socket on 127.0.0.1, as the Shortcut and the gallery use it."""

import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from photo_harbor.app import HarborApp
from photo_harbor.autostart import Autostart
from photo_harbor.config import load_or_create
from photo_harbor.http_server import HarborServer
from tests.library_fixture import FIXED_NOW, sha


class _NoPreviews:
    enabled = False

    def preview(self, record, original):
        return None


class _FakeRunKey:
    def __init__(self):
        self.value = None

    def read(self):
        return self.value

    def write(self, command):
        self.value = command

    def delete(self):
        self.value = None


class ServerTest(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="harbor_http_"))
        self.addCleanup(shutil.rmtree, root, True)
        self.settings = load_or_create(root)
        self.registry = _FakeRunKey()
        self.app = HarborApp(self.settings, port=0, thumbs=_NoPreviews(), now=lambda: FIXED_NOW,
                             autostart=Autostart(self.registry, 'pythonw Harbor.pyw', supported=True),
                             password_iterations=1000)
        self.addCleanup(self.app.close)
        self.server = HarborServer(("127.0.0.1", 0), self.app.router, self.app.guard,
                                   verbose=False)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, method, path, body=None, headers=None, key=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        self.addCleanup(conn.close)
        sent = dict(headers or {})
        if key:
            sent["X-Harbor-Key"] = self.settings.key
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            sent["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=sent)
        response = conn.getresponse()
        return response, response.read()

    def upload(self, data, name="IMG_0001.HEIC", digest=None):
        headers = {"X-Name": name, "X-Sha256": digest or sha(data), "X-Taken": "2026-05-01T08:00:00Z"}
        return self.call("POST", "/api/upload", body=data, headers=headers)

    def test_a_full_sync_round(self):
        response, body = self.call("POST", "/api/sync/start", body={})
        start = json.loads(body)
        self.assertEqual(start["since"], "2000-01-01T00:00:00")
        response, body = self.upload(b"heic bytes")
        self.assertEqual((response.status, json.loads(body)["status"]), (200, "stored"))
        response, body = self.upload(b"heic bytes")
        self.assertEqual(json.loads(body)["status"], "duplicate")
        self.call("POST", "/api/sync/done", body={"started_at": start["started_at"]})
        _, body = self.call("POST", "/api/sync/start", body={})
        self.assertEqual(json.loads(body)["since"], "2026-10-24T11:50:00+00:00")

    def test_has_answers_yes_only_for_verified_photos(self):
        self.upload(b"kept")
        _, body = self.call("GET", f"/api/has?sha256={sha(b'kept')}")
        self.assertEqual(json.loads(body)["answer"], "yes")
        _, body = self.call("GET", f"/api/has?sha256={sha(b'not sent')}&name=IMG_6.HEIC")
        self.assertEqual(json.loads(body)["answer"], "no")
        self.call("GET", f"/api/has?sha256={sha(b'also not sent')}&name=IMG_7.HEIC&report=1")
        _, body = self.call("GET", "/api/status")
        self.assertEqual([m["name"] for m in json.loads(body)["missing"]], ["IMG_7.HEIC"])

    def test_a_mismatched_hash_is_rejected_and_counted(self):
        response, body = self.upload(b"actual", digest=sha(b"claimed"))
        self.assertEqual(response.status, 422)
        self.assertIn("why", json.loads(body))
        _, body = self.call("GET", "/api/status")
        self.assertEqual(json.loads(body)["last_day"]["rejected"], 1)

    def test_calls_without_the_key_are_refused_but_the_page_loads(self):
        response, _ = self.call("GET", "/api/status", key=False)
        self.assertEqual(response.status, 401)
        response, body = self.call("GET", "/", key=False)
        self.assertEqual(response.status, 200)
        self.assertIn(b"<html", body)

    def test_login_sets_a_cookie_that_opens_the_api(self):
        response, _ = self.call("POST", "/api/login", body={"key": self.settings.key}, key=False)
        cookie = response.getheader("Set-Cookie").split(";", 1)[0]
        response, _ = self.call("GET", "/api/status", headers={"Cookie": cookie}, key=False)
        self.assertEqual(response.status, 200)

    def test_media_serves_ranges_for_video_scrubbing(self):
        self.upload(b"0123456789", name="clip.MOV")
        response, body = self.call("GET", f"/media/{sha(b'0123456789')}", headers={"Range": "bytes=2-4"})
        self.assertEqual((response.status, body), (206, b"234"))
        self.assertEqual(response.getheader("Content-Type"), "video/quicktime")

    def test_photos_lists_newest_first_with_paging(self):
        self.upload(b"a", name="a.jpg")
        self.upload(b"b", name="b.jpg")
        _, body = self.call("GET", "/api/photos?limit=1")
        page = json.loads(body)
        self.assertEqual((len(page["photos"]), page["next"]), (1, 1))

    def test_a_chunked_upload_is_accepted(self):
        data = b"chunked photo"
        framed = b"%x\r\n%s\r\n0\r\n\r\n" % (len(data), data)
        headers = {"X-Name": "c.jpg", "X-Sha256": sha(data), "Transfer-Encoding": "chunked"}
        response, body = self.call("POST", "/api/upload", body=framed, headers=headers)
        self.assertEqual((response.status, json.loads(body)["status"]), (200, "stored"))

    def test_browsing_by_month_kind_and_name(self):
        self.upload(b"may photo", name="IMG_0001.HEIC")
        self.call("POST", "/api/upload", body=b"clip", headers={
            "X-Name": "clip.MOV", "X-Taken": "2025-12-24T20:00:00"})
        _, body = self.call("GET", "/api/outline")
        outline = json.loads(body)
        self.assertEqual([m["month"] for m in outline["months"]], ["2026-05", "2025-12"])
        self.assertEqual(outline["videos"], 1)
        _, body = self.call("GET", "/api/photos?month=2025-12")
        self.assertEqual([p["name"] for p in json.loads(body)["photos"]], ["clip.MOV"])
        _, body = self.call("GET", "/api/photos?kind=photo&q=img_")
        self.assertEqual([p["name"] for p in json.loads(body)["photos"]], ["IMG_0001.HEIC"])
        response, _ = self.call("GET", "/api/photos?month=2025-13")
        self.assertEqual(response.status, 400)

    def test_a_browser_upload_needs_no_hash_and_keeps_a_non_ascii_name(self):
        response, body = self.call("POST", "/api/upload", body=b"from the browser", headers={
            "X-Name": "Tatil%20foto%C4%9Fraf%C4%B1.jpg", "X-Modified": "2024-03-02T10:00:00.000Z"})
        self.assertEqual(json.loads(body)["status"], "stored")
        _, body = self.call("GET", "/api/photos")
        photo = json.loads(body)["photos"][0]
        self.assertEqual((photo["name"], photo["time"][:7]), ("Tatil fotoğrafı.jpg", "2024-03"))

    def test_a_non_media_upload_downloads_instead_of_rendering(self):
        page = b"<script>alert(1)</script>"
        self.upload(page, name="evil.html")
        response, _ = self.call("GET", f"/media/{sha(page)}")
        self.assertEqual(response.getheader("Content-Type"), "application/octet-stream")
        self.assertEqual(response.getheader("Content-Disposition"), "attachment")

    @unittest.skipUnless(os.name == "nt", "port sharing is the Windows behaviour")
    def test_a_second_server_cannot_share_the_port(self):
        with self.assertRaises(OSError):
            HarborServer(self.server.server_address, self.app.router, self.app.guard, verbose=False)

    def add_person(self, name="Ayşe"):
        _, body = self.call("POST", "/api/profiles", body={"name": name})
        return json.loads(body)

    def test_a_persons_key_uploads_into_their_own_profile(self):
        ayse = self.add_person()
        data = b"her photo"
        self.call("POST", "/api/upload", body=data, key=False,
                  headers={"X-Harbor-Key": ayse["key"], "X-Name": "IMG.HEIC", "X-Sha256": sha(data)})
        _, body = self.call("GET", "/api/photos?profile=ayse")
        self.assertEqual([p["name"] for p in json.loads(body)["photos"]], ["IMG.HEIC"])
        _, body = self.call("POST", "/api/sync/start", body={}, key=False,
                            headers={"X-Harbor-Key": ayse["key"]})
        self.assertEqual(json.loads(body)["since"], "2000-01-01T00:00:00")

    def test_only_the_owner_may_target_or_manage_other_profiles(self):
        ayse = self.add_person()
        as_ayse = {"X-Harbor-Key": ayse["key"]}
        response, _ = self.call("POST", "/api/upload", body=b"x", key=False,
                                headers={**as_ayse, "X-Name": "a.jpg", "X-Profile": "main"})
        self.assertEqual(response.status, 403)
        response, _ = self.call("POST", "/api/profiles", body={"name": "Bob"}, key=False, headers=as_ayse)
        self.assertEqual(response.status, 403)
        _, body = self.call("GET", "/api/profiles", key=False, headers=as_ayse)
        listing = json.loads(body)
        self.assertEqual((listing["me"], listing["owner"]), ("ayse", False))
        self.assertEqual([p["id"] for p in listing["profiles"]], ["ayse"])
        response, body = self.call("POST", "/api/upload", body=b"for her",
                                   headers={"X-Name": "b.jpg", "X-Profile": "ayse"})
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(self.call("GET", "/api/profiles")[1])["profiles"][1]["count"], 1)

    def test_a_retired_key_is_refused(self):
        ayse = self.add_person()
        self.call("POST", "/api/profiles/ayse", body={"new_key": True})
        response, _ = self.call("GET", "/api/status", key=False, headers={"X-Harbor-Key": ayse["key"]})
        self.assertEqual(response.status, 401)

    def test_a_client_hanging_up_prints_no_traceback(self):
        import contextlib
        import io as text_io
        captured = text_io.StringIO()
        with contextlib.redirect_stderr(captured):
            try:
                raise ConnectionAbortedError("client went away")
            except ConnectionAbortedError:
                self.server.handle_error(None, ("127.0.0.1", 1))
        self.assertEqual(captured.getvalue(), "")

    def test_the_owner_can_turn_starting_with_windows_on_and_off(self):
        _, body = self.call("GET", "/api/setup")
        self.assertEqual(json.loads(body)["startup"], {"supported": True, "enabled": False})
        _, body = self.call("POST", "/api/startup", body={"enabled": True})
        self.assertTrue(json.loads(body)["enabled"])
        self.assertEqual(self.registry.value, "pythonw Harbor.pyw")
        ayse = self.add_person()
        response, _ = self.call("POST", "/api/startup", body={"enabled": False}, key=False,
                                headers={"X-Harbor-Key": ayse["key"]})
        self.assertEqual(response.status, 403)
        self.call("POST", "/api/startup", body={"enabled": False})
        self.assertIsNone(self.registry.value)

    def sign_in(self, profile, password):
        response, body = self.call("POST", "/api/login", body={"profile": profile, "password": password},
                                   key=False)
        cookie = response.getheader("Set-Cookie")
        return response.status, (cookie.split(";", 1)[0] if cookie else None)

    def test_people_sign_in_with_a_password_and_see_only_their_own_photos(self):
        self.call("POST", "/api/profiles", body={"name": "Ayşe", "password": "deniz123"})
        self.upload(b"main's photo", name="mine.jpg")
        self.call("POST", "/api/upload", body=b"her photo",
                  headers={"X-Name": "hers.jpg", "X-Profile": "ayse"})
        _, body = self.call("GET", "/api/people", key=False)
        self.assertEqual([p["name"] for p in json.loads(body)["profiles"]], ["Main", "Ayşe"])
        status, cookie = self.sign_in("ayse", "deniz123")
        self.assertEqual(status, 200)
        as_her = {"Cookie": cookie}
        _, body = self.call("GET", "/api/photos", key=False, headers=as_her)
        self.assertEqual([p["name"] for p in json.loads(body)["photos"]], ["hers.jpg"])
        response, _ = self.call("GET", "/api/photos?profile=main", key=False, headers=as_her)
        self.assertEqual(response.status, 403)
        response, _ = self.call("GET", f"/media/{sha(b'main' + chr(39).encode() + b's photo')}",
                                key=False, headers=as_her)
        self.assertEqual(response.status, 404)

    def test_wrong_passwords_are_refused_then_braked(self):
        self.call("POST", "/api/profiles", body={"name": "Ayşe", "password": "deniz123"})
        for _ in range(5):
            self.assertEqual(self.sign_in("ayse", "wrong")[0], 401)
        self.assertEqual(self.sign_in("ayse", "deniz123")[0], 429)

    def test_changing_a_password_needs_the_current_one_and_signs_out_other_browsers(self):
        self.call("POST", "/api/profiles", body={"name": "Ayşe", "password": "deniz123"})
        _, first = self.sign_in("ayse", "deniz123")
        _, second = self.sign_in("ayse", "deniz123")
        response, _ = self.call("POST", "/api/password", body={"current": "nope", "new": "yeni-sifre"},
                                key=False, headers={"Cookie": first})
        self.assertEqual(response.status, 403)
        response, _ = self.call("POST", "/api/password", body={"current": "deniz123", "new": "yeni-sifre"},
                                key=False, headers={"Cookie": first})
        self.assertEqual(response.status, 200)
        self.assertEqual(self.call("GET", "/api/status", key=False, headers={"Cookie": first})[0].status, 200)
        self.assertEqual(self.call("GET", "/api/status", key=False, headers={"Cookie": second})[0].status, 401)
        self.assertEqual(self.sign_in("ayse", "yeni-sifre")[0], 200)

    def test_last_day_counts_follow_the_signed_in_person(self):
        self.call("POST", "/api/profiles", body={"name": "Ayşe", "password": "deniz123"})
        self.upload(b"main photo", name="mine.jpg")
        self.call("POST", "/api/upload", body=b"her photo",
                  headers={"X-Name": "hers.jpg", "X-Profile": "ayse"})
        _, body = self.call("GET", "/api/status")
        self.assertEqual(json.loads(body)["last_day"]["stored"], 2)
        status, cookie = self.sign_in("ayse", "deniz123")
        self.assertEqual(status, 200)
        _, body = self.call("GET", "/api/status", key=False, headers={"Cookie": cookie})
        self.assertEqual(json.loads(body)["last_day"]["stored"], 1)

    def test_the_owner_can_reset_a_password_and_a_key_still_signs_in(self):
        ayse = self.add_person()
        response, _ = self.call("POST", "/api/profiles/ayse", body={"password": "12"})
        self.assertEqual(response.status, 400)
        self.call("POST", "/api/profiles/ayse", body={"password": "baslangic"})
        self.assertEqual(self.sign_in("ayse", "baslangic")[0], 200)
        response, _ = self.call("POST", "/api/login", body={"key": ayse["key"]}, key=False)
        self.assertEqual(response.status, 200)

    def test_albums_and_favorites_page_the_photos_they_hold(self):
        self.upload(b"one", name="one.jpg")
        self.upload(b"two", name="two.jpg")
        response, body = self.call("POST", "/api/albums", body={"name": "Keepers"})
        self.assertEqual(response.status, 201)
        album = json.loads(body)["id"]
        response, body = self.call("POST", "/api/album-photos",
                                   body={"album": album, "sha256": sha(b"one"), "member": True})
        self.assertEqual((response.status, json.loads(body)["changed"]), (200, True))
        _, body = self.call("GET", f"/api/photos?album={album}")
        self.assertEqual([p["name"] for p in json.loads(body)["photos"]], ["one.jpg"])
        _, body = self.call("GET", "/api/albums")
        listing = json.loads(body)
        self.assertEqual(listing["favorites"], 0)
        self.assertEqual((listing["albums"][0]["name"], listing["albums"][0]["count"]),
                         ("Keepers", 1))
        self.assertTrue(listing["albums"][0]["cover"].startswith("/thumb/"))
        response, body = self.call("POST", "/api/favorite",
                                   body={"sha256": sha(b"one"), "favorite": True})
        self.assertEqual((response.status, json.loads(body)["changed"]), (200, True))
        _, body = self.call("GET", "/api/photos?favorite=1")
        self.assertEqual([(p["name"], p["favorite"]) for p in json.loads(body)["photos"]],
                         [("one.jpg", True)])
        _, body = self.call("GET", "/api/outline")
        self.assertEqual(json.loads(body)["favorites"], 1)
        response, _ = self.call("POST", "/api/favorite",
                                body={"sha256": sha(b"one"), "favorite": "yes"})
        self.assertEqual(response.status, 400)
        response, _ = self.call("POST", f"/api/albums/{album}", body={"name": "Best"})
        self.assertEqual(response.status, 200)
        _, body = self.call("GET", "/api/albums")
        self.assertEqual(json.loads(body)["albums"][0]["name"], "Best")
        response, _ = self.call("POST", f"/api/albums/{album}", body={"delete": True})
        self.assertEqual(response.status, 200)
        response, _ = self.call("GET", f"/api/photos?album={album}")
        self.assertEqual(response.status, 404)
        _, body = self.call("GET", "/api/photos?favorite=1")
        self.assertEqual([p["name"] for p in json.loads(body)["photos"]], ["one.jpg"])

    def test_bulk_selection_writes_a_validated_batch(self):
        for name in ("one.jpg", "two.jpg", "three.jpg"):
            self.upload(name.encode(), name=name)
        _, body = self.call("POST", "/api/albums", body={"name": "Batch"})
        album = json.loads(body)["id"]
        one, two, three = (sha(name.encode()) for name in ("one.jpg", "two.jpg", "three.jpg"))
        response, body = self.call("POST", "/api/album-photos",
                                   body={"album": album, "sha256s": [one, two], "member": True})
        result = json.loads(body)
        self.assertEqual((response.status, result["changed"], result["count"]), (200, 2, 2))
        response, body = self.call("POST", "/api/favorite",
                                   body={"sha256s": [one, two, three], "favorite": True})
        self.assertEqual(json.loads(body)["changed"], 3)
        _, body = self.call("GET", "/api/photos?favorite=1")
        self.assertEqual(len(json.loads(body)["photos"]), 3)
        response, body = self.call("POST", "/api/album-photos",
                                   body={"album": album, "sha256s": [one, "f" * 64],
                                         "member": True})
        self.assertEqual(response.status, 404)
        _, body = self.call("GET", f"/api/photos?album={album}")
        self.assertEqual(len(json.loads(body)["photos"]), 2)
        response, _ = self.call("POST", "/api/favorite", body={"sha256s": [], "favorite": True})
        self.assertEqual(response.status, 400)
        response, _ = self.call("POST", "/api/favorite",
                                body={"sha256s": ["f" * 64] * 501, "favorite": True})
        self.assertEqual(response.status, 400)
        response, body = self.call("POST", "/api/album-photos",
                                   body={"album": album, "sha256": three, "member": True})
        self.assertEqual((response.status, json.loads(body)["count"]), (200, 1))

    def test_albums_and_favorites_never_cross_people(self):
        ayse = self.add_person()
        self.upload(b"one", name="one.jpg")
        self.call("POST", "/api/upload", body=b"hers", key=False,
                  headers={"X-Harbor-Key": ayse["key"], "X-Name": "hers.jpg",
                           "X-Sha256": sha(b"hers")})
        _, body = self.call("POST", "/api/albums", body={"name": "Main album"})
        main_album = json.loads(body)["id"]
        self.call("POST", "/api/album-photos",
                  body={"album": main_album, "sha256": sha(b"one"), "member": True})
        response, _ = self.call("POST", "/api/login", body={"key": ayse["key"]}, key=False)
        as_her = {"Cookie": response.getheader("Set-Cookie").split(";", 1)[0]}
        _, body = self.call("GET", "/api/albums", key=False, headers=as_her)
        self.assertEqual(json.loads(body), {"favorites": 0, "albums": []})
        response, _ = self.call("POST", f"/api/albums/{main_album}", body={"name": "Stolen"},
                                key=False, headers=as_her)
        self.assertEqual(response.status, 404)
        response, _ = self.call("GET", f"/api/photos?album={main_album}", key=False, headers=as_her)
        self.assertEqual(response.status, 404)
        response, _ = self.call("POST", "/api/album-photos",
                                body={"album": main_album, "sha256": sha(b"hers"), "member": True},
                                key=False, headers=as_her)
        self.assertEqual(response.status, 404)
        response, _ = self.call("POST", "/api/favorite",
                                body={"sha256": sha(b"one"), "favorite": True},
                                key=False, headers=as_her)
        self.assertEqual(response.status, 404)
        _, body = self.call("POST", "/api/albums", body={"name": "Hers"}, key=False,
                            headers=as_her)
        her_album = json.loads(body)["id"]
        response, _ = self.call("POST", "/api/album-photos",
                                body={"album": her_album, "sha256": sha(b"hers"), "member": True},
                                key=False, headers=as_her)
        self.assertEqual(response.status, 200)
