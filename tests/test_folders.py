"""The library as people see it in File Explorer, and Harbor keeping up with changes made there."""

import io
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from photo_harbor.app import HarborApp
from photo_harbor.autostart import Autostart
from photo_harbor.config import load_or_create
from photo_harbor.layout import GUIDE
from photo_harbor.records import UploadClaim
from tests.library_fixture import FIXED_NOW, sha


class _NoPreviews:
    enabled = False

    def preview(self, record, original):
        return None


class _NoRegistry:
    def read(self):
        return None


class PreviewCacheTest(unittest.TestCase):
    def test_startup_drops_previews_of_photos_that_are_gone(self):
        from photo_harbor.thumbs import Thumbnailer
        root = Path(tempfile.mkdtemp(prefix="harbor_cache_"))
        self.addCleanup(shutil.rmtree, root, True)
        settings = load_or_create(root)
        first = HarborApp(settings, port=0, thumbs=_NoPreviews(), now=lambda: FIXED_NOW,
                          password_iterations=1000)
        record = first.store.ingest(io.BytesIO(b"kept"), 4, UploadClaim(
            "kept.jpg", sha256=sha(b"kept"), taken_at="2026-01-01T00:00:00")).record
        first.close()
        cache = settings.state_dir / "thumbs"
        for digest in (record.sha256, "b" * 64):
            path = cache / digest[:2] / f"{digest}.jpg"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"jpeg")
        thumbs = Thumbnailer(cache, pillow=lambda: (None, None))
        app = HarborApp(settings, port=0, thumbs=thumbs, now=lambda: FIXED_NOW,
                        password_iterations=1000)
        self.addCleanup(app.close)
        self.assertTrue((cache / record.sha256[:2] / f"{record.sha256}.jpg").exists())
        self.assertFalse((cache / ("b" * 64)[:2] / f"{'b' * 64}.jpg").exists())


def make_app(test_case, root=None):
    root = root or Path(tempfile.mkdtemp(prefix="harbor_folders_"))
    test_case.addCleanup(shutil.rmtree, root, True)
    app = HarborApp(load_or_create(root), port=0, thumbs=_NoPreviews(), now=lambda: FIXED_NOW,
                    autostart=Autostart(_NoRegistry(), "x", supported=False),
                    password_iterations=1000)
    test_case.addCleanup(app.close)
    app.scanner._clock = lambda: 4102444800.0  # far future: every file counts as settled
    app.layout.prepare()
    return root, app


def put(app, data, name="IMG_0001.HEIC", profile="main", taken="2026-03-05T10:00:00"):
    claim = UploadClaim(name, sha256=sha(data), taken_at=taken, profile=profile)
    return app.store.ingest(io.BytesIO(data), len(data), claim)


class LayoutTest(unittest.TestCase):
    def test_photos_go_to_person_year_month_folders_with_a_guide(self):
        root, app = make_app(self)
        record = put(app, b"photo").record
        self.assertEqual(record.rel_path, "Main/2026/2026-03/IMG_0001.heic")
        self.assertTrue((root / GUIDE).is_file())
        self.assertIn("Ayşe", (root / GUIDE).read_text(encoding="utf-8-sig"))

    def test_a_shared_photo_is_in_both_folders_but_stored_once(self):
        root, app = make_app(self)
        app.profiles.create("Ayşe")
        mine = put(app, b"shared").record
        hers = put(app, b"shared", profile="ayse").record
        self.assertEqual(hers.rel_path, "Ayşe/2026/2026-03/IMG_0001.heic")
        self.assertTrue((root / hers.rel_path).is_file())
        if os.name == "nt":
            self.assertTrue(os.path.samefile(root / mine.rel_path, root / hers.rel_path))
        self.assertEqual(put(app, b"shared", profile="ayse").status, "duplicate")

    def test_has_links_a_photo_the_pc_already_has_into_the_askers_folder(self):
        root, app = make_app(self)
        app.profiles.create("Ayşe")
        put(app, b"family photo")
        self.assertTrue(app.store.ensure_copy("ayse", sha(b"family photo")))
        self.assertEqual(len(list((root / "Ayşe").rglob("*.heic"))), 1)

    def test_renaming_a_person_renames_their_folder_and_keeps_every_path(self):
        root, app = make_app(self)
        app.profiles.create("Ayse")
        record = put(app, b"hers", profile="ayse").record
        app.layout.rename_person("ayse", "Ayşe Yılmaz")
        moved = app.store.locate(record.sha256, "ayse")
        self.assertEqual(moved[0], root / "Ayşe Yılmaz/2026/2026-03/IMG_0001.heic")
        self.assertFalse((root / "Ayse").exists())

    def test_renaming_into_a_folder_left_on_disk_uses_a_free_name(self):
        # A folder can exist without a profile: a deletion that failed, a copy made by hand.
        # Renaming onto it fails, so the name must be free only when the disk agrees.
        root, app = make_app(self)
        app.profiles.create("Ayse")
        put(app, b"hers", profile="ayse")
        (root / "Ayşe Yılmaz").mkdir()
        person = app.layout.rename_person("ayse", "Ayşe Yılmaz")
        self.assertEqual(person.folder, "Ayşe Yılmaz (2)")
        self.assertTrue((root / "Ayşe Yılmaz (2)").is_dir())
        self.assertFalse((root / "Ayse").exists())

    def test_a_new_person_does_not_inherit_a_folder_left_on_disk(self):
        # A leftover folder may hold untracked files the scanner would adopt; the new
        # person must get a fresh folder instead.
        root, app = make_app(self)
        stray = root / "Ayşe"
        stray.mkdir()
        (stray / "not-mine.jpg").write_bytes(b"someone else's")
        person = app.layout.create_person("Ayşe")
        app.layout.prepare()
        self.assertEqual(person.folder, "Ayşe (2)")
        self.assertFalse((root / person.folder / "not-mine.jpg").exists())

    def test_files_from_the_old_layout_move_into_place(self):
        root = Path(tempfile.mkdtemp(prefix="harbor_legacy_"))
        old = root / "photos" / "main" / "2025" / "07"
        old.mkdir(parents=True)
        (old / "a.jpg").write_bytes(b"old photo")
        db_dir = root / ".harbor"
        db_dir.mkdir()
        db = sqlite3.connect(db_dir / "catalog.sqlite3")
        db.executescript(
            "CREATE TABLE photos (sha256 TEXT PRIMARY KEY, rel_path TEXT NOT NULL UNIQUE,"
            " size INTEGER NOT NULL, original_name TEXT NOT NULL, media_type TEXT NOT NULL,"
            " taken_at TEXT, received_at TEXT NOT NULL, sort_time TEXT NOT NULL,"
            " profile TEXT NOT NULL DEFAULT 'main');"
            "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,"
            " kind TEXT NOT NULL, sha256 TEXT, detail TEXT, profile TEXT);"
            "CREATE TABLE profiles (id TEXT PRIMARY KEY, name TEXT NOT NULL, key TEXT NOT NULL"
            " UNIQUE, created_at TEXT NOT NULL);"
            "CREATE TABLE imported_files (source TEXT PRIMARY KEY, size INTEGER NOT NULL,"
            " mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL);"
            f"INSERT INTO photos VALUES ('{sha(b'old photo')}', 'main/2025/07/a.jpg', 9, 'a.jpg',"
            " 'image/jpeg', '2025-07-01T10:00:00', '2025-07-02T00:00:00', '2025-07-01T10:00:00',"
            " 'main'); PRAGMA user_version=3;")
        db.close()
        root, app = make_app(self, root)
        self.assertTrue((root / "Main/2025/2025-07/a.jpg").is_file())
        self.assertFalse((root / "photos").exists())
        self.assertTrue(app.store.verify(sha(b"old photo")))


class ScannerTest(unittest.TestCase):
    def test_files_added_moved_and_deleted_in_explorer_are_noticed(self):
        root, app = make_app(self)
        record = put(app, b"keep me").record
        gone = put(app, b"delete me", name="b.jpg").record
        (root / "Main/2026/Holiday").mkdir(parents=True)
        os.replace(root / record.rel_path, root / "Main/2026/Holiday/IMG_0001.heic")
        (root / gone.rel_path).unlink()
        (root / "Main/2026/2026-03/new.jpg").write_bytes(b"dropped in")
        (root / "Main/2026/2026-03/notes.txt").write_text("not media")
        report = app.scanner.reconcile()
        self.assertEqual((report.added, report.moved, report.removed), (1, 1, 1))
        self.assertEqual(app.store.locate(record.sha256, "main")[0],
                         root / "Main/2026/Holiday/IMG_0001.heic")
        self.assertIsNone(app.store.locate(gone.sha256))
        self.assertTrue(app.store.verify(sha(b"dropped in")))

    def test_a_vanished_drive_removes_nothing(self):
        root, app = make_app(self)
        for i in range(60):
            put(app, f"photo {i}".encode(), name=f"{i}.jpg")
        shutil.rmtree(root / "Main")
        report = app.scanner.reconcile()
        self.assertEqual((report.removed, report.held_back), (0, 60))
        self.assertEqual(app.store._catalog.stats().count, 60)

    def test_drive_loss_with_fewer_than_50_files_removes_nothing(self):
        root, app = make_app(self)
        for i in range(10):
            put(app, f"photo {i}".encode(), name=f"{i}.jpg")
        shutil.rmtree(root / "Main")
        report = app.scanner.reconcile()
        self.assertEqual((report.removed, report.held_back), (0, 10))
        self.assertEqual(app.store._catalog.stats().count, 10)

    def test_single_delete_in_small_library_still_allowed(self):
        root, app = make_app(self)
        for i in range(10):
            put(app, f"photo {i}".encode(), name=f"{i}.jpg")
        gone = sorted((root / "Main").rglob("*.jpg"))[0]
        gone.unlink()
        report = app.scanner.reconcile()
        self.assertEqual(report.removed, 1)
        self.assertEqual(report.held_back, 0)

    def test_the_file_check_reports_damage_without_deleting(self):
        root, app = make_app(self)
        record = put(app, b"original").record
        (root / record.rel_path).write_bytes(b"0riginal")
        result = app.scanner.check()
        self.assertEqual(result.damaged, (record.rel_path,))
        self.assertTrue((root / record.rel_path).exists())
