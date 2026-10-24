"""Starting with Windows, and the pieces that keep large libraries fast."""

import threading
import unittest
from pathlib import Path

from photo_harbor.autostart import Autostart, launch_command
from photo_harbor.errors import HarborError
from photo_harbor.importer import ImportLedger, import_folder
from photo_harbor.thumbs import PreviewWarmer
from tests.library_fixture import Library


class _FakeRunKey:
    def __init__(self):
        self.value = None

    def read(self):
        return self.value

    def write(self, command):
        self.value = command

    def delete(self):
        self.value = None


class AutostartTest(unittest.TestCase):
    def test_the_command_runs_the_launcher_windowless_at_startup(self):
        command = launch_command(Path("python") / "python.exe", Path("apps") / "Harbor.pyw")
        self.assertTrue(command.endswith('Harbor.pyw" --startup'))

    def test_on_and_off(self):
        registry = _FakeRunKey()
        start = Autostart(registry, "run harbor", supported=True)
        self.assertFalse(start.enabled())
        self.assertTrue(start.set(True))
        self.assertEqual(registry.value, "run harbor")
        self.assertFalse(start.set(False))

    def test_other_systems_say_so(self):
        start = Autostart(_FakeRunKey(), "run harbor", supported=False)
        self.assertFalse(start.enabled())
        with self.assertRaises(HarborError):
            start.set(True)


class ImportLedgerTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(self)
        self.ledger = ImportLedger(self.lib.db)
        self.source = Path(str(self.lib.root) + "_src")
        self.source.mkdir()
        self.addCleanup(__import__("shutil").rmtree, self.source, True)
        (self.source / "a.jpg").write_bytes(b"photo a")
        (self.source / "b.jpg").write_bytes(b"photo b")

    def reads(self):
        """Run an import and return how many source files were actually opened."""
        opened = []
        real = self.lib.store.ingest

        def counting(stream, length, claim):
            opened.append(claim.original_name)
            return real(stream, length, claim)

        self.lib.store.ingest = counting
        report = import_folder(self.lib.store, self.source, self.lib.root, "main", ledger=self.ledger)
        self.lib.store.ingest = real
        return report, opened

    def test_unchanged_files_are_not_read_again(self):
        first, opened = self.reads()
        self.assertEqual((first.stored, len(opened)), (2, 2))
        again, opened = self.reads()
        self.assertEqual((again.duplicate, opened), (2, []))

    def test_a_changed_file_or_a_lost_copy_is_read_again(self):
        report, _ = self.reads()
        (self.source / "a.jpg").write_bytes(b"photo a, edited")
        lost = next(r for r in self.lib.catalog.page(0, 10) if r.original_name == "b.jpg")
        (self.lib.root / lost.rel_path).unlink()
        _, opened = self.reads()
        self.assertEqual(sorted(opened), ["a.jpg", "b.jpg"])


class _CountingThumbs:
    enabled = True

    def __init__(self):
        self.made = []
        self.done = threading.Event()

    def preview(self, record, original):
        self.made.append(record.original_name)
        if len(self.made) >= 3:
            self.done.set()
        return original


class WarmerTest(unittest.TestCase):
    def test_backfills_old_photos_and_takes_new_ones_skipping_videos(self):
        lib = Library(self)
        lib.put(b"old 1", name="old1.jpg")
        lib.put(b"old 2", name="old2.jpg")
        lib.put(b"clip", name="clip.mov")
        thumbs = _CountingThumbs()
        warmer = PreviewWarmer(thumbs, lib.catalog, lib.store, page=1)
        lib.store.on_stored = warmer.add
        warmer.start()
        self.addCleanup(warmer.stop)
        lib.put(b"new", name="new.jpg")
        self.assertTrue(thumbs.done.wait(5))
        warmer.stop()
        self.assertEqual(sorted(set(thumbs.made)), ["new.jpg", "old1.jpg", "old2.jpg"])


class ImportForAnotherPersonTest(unittest.TestCase):
    def test_a_folder_imported_for_one_person_still_reaches_the_next(self):
        from tests.test_folders import make_app
        root, app = make_app(self)
        app.profiles.create("Ayşe")
        source = Path(str(root) + "_src")
        source.mkdir()
        self.addCleanup(__import__("shutil").rmtree, source, True)
        (source / "a.jpg").write_bytes(b"family photo")
        import_folder(app.store, source, root, "main", ledger=app.imports)
        report = import_folder(app.store, source, root, "ayse", ledger=app.imports)
        self.assertEqual(report.stored, 1)
        self.assertIsNotNone(app.store.locate(__import__("hashlib").sha256(b"family photo").hexdigest(), "ayse"))


class ScanScheduleTest(unittest.TestCase):
    def test_a_failing_pass_is_logged_and_the_thread_keeps_going(self):
        import sqlite3
        from photo_harbor.scan import ScanSchedule

        class Broken:
            calls = 0

            def reconcile(self, stop=None):
                Broken.calls += 1
                raise sqlite3.OperationalError("disk I/O error")

        logged = []
        schedule = ScanSchedule(Broken(), journal=None, log=logged.append)
        schedule.start()
        self.addCleanup(schedule.stop)
        schedule.run_now()
        for _ in range(100):
            if Broken.calls >= 2:
                break
            threading.Event().wait(0.01)
        schedule.stop()
        self.assertGreaterEqual(Broken.calls, 2)
        self.assertIn("disk I/O error", logged[0])


class SessionCleanupTest(unittest.TestCase):
    def test_expired_sessions_are_removed(self):
        from datetime import timedelta
        from photo_harbor.accounts import Sessions
        from tests.library_fixture import FIXED_NOW
        lib = Library(self)
        moment = [FIXED_NOW]
        sessions = Sessions(lib.db, now=lambda: moment[0])
        old = sessions.start("main")
        moment[0] = FIXED_NOW + timedelta(days=400)
        self.assertIsNone(sessions.find(old))
        sessions.start("main")
        count = lib.db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        self.assertEqual(count, 1)
