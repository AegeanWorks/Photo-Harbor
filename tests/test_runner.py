"""The background server the Harbor window and `serve` use, and the window's saved settings."""

import http.client
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from photo_harbor.control_panel import load_prefs, mask, save_prefs
from photo_harbor.errors import HarborError
from photo_harbor.runner import ServerRunner


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="harbor_runner_"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_start_serves_and_stop_frees_everything(self):
        runner = ServerRunner(self.root / "lib", 0, host="127.0.0.1", verbose=False)
        running = runner.start()
        self.addCleanup(runner.stop)
        conn = http.client.HTTPConnection("127.0.0.1", running.port, timeout=5)
        conn.request("GET", "/")
        self.assertEqual(conn.getresponse().status, 200)
        conn.close()
        with self.assertRaises(HarborError):
            runner.start()
        runner.stop()
        self.assertFalse(runner.running)
        runner.stop()

    def test_a_busy_port_is_a_clear_error(self):
        first = ServerRunner(self.root / "a", 0, host="127.0.0.1", verbose=False)
        port = first.start().port
        self.addCleanup(first.stop)
        second = ServerRunner(self.root / "b", port, host="127.0.0.1", verbose=False)
        with self.assertRaises(HarborError):
            second.start()
        self.assertFalse(second.running)

    def test_wait_returns_immediately_when_never_started(self):
        runner = ServerRunner(self.root / "idle", 0, host="127.0.0.1", verbose=False)
        runner.wait()

    def test_wait_unblocks_after_stop(self):
        import threading
        runner = ServerRunner(self.root / "lib", 0, host="127.0.0.1", verbose=False)
        runner.start()
        self.addCleanup(runner.stop)
        done = threading.Event()
        watcher = threading.Thread(target=lambda: (runner.wait(), done.set()), daemon=True)
        watcher.start()
        runner.stop()
        self.assertTrue(done.wait(timeout=10))

    def test_prepare_failure_closes_the_library(self):
        import photo_harbor.runner as runmod
        from unittest.mock import patch
        runner = ServerRunner(self.root / "lib", 0, host="127.0.0.1", verbose=False,
                              log=lambda text: None)
        with patch.object(runmod, "HarborApp") as mock_app_cls:
            inst = mock_app_cls.return_value
            inst.layout.prepare.side_effect = RuntimeError("prepare boom")
            with self.assertRaises(RuntimeError):
                runner.start()
            inst.close.assert_called_once_with()
        self.assertFalse(runner.running)

    def test_a_failed_post_bind_setup_leaves_nothing_running(self):
        # The socket is already bound when the warmer and schedule start, so a failure there
        # would otherwise leave `running` True with a dead server and only stop() to fix it.
        import photo_harbor.runner as runmod
        from unittest.mock import patch
        runner = ServerRunner(self.root / "lib", 0, host="127.0.0.1", verbose=False,
                              log=lambda text: None)
        with patch.object(runmod, "HarborApp") as mock_app_cls:
            inst = mock_app_cls.return_value
            inst.layout.prepare.return_value = 0
            inst.previews = False
            inst.warmer = None
            inst.schedule.start.side_effect = RuntimeError("schedule boom")
            with self.assertRaises(RuntimeError):
                runner.start()
            inst.close.assert_called_once_with()
        self.assertFalse(runner.running)
        # A second start must be possible: nothing is left holding the port.
        runner.start()
        self.addCleanup(runner.stop)
        self.assertTrue(runner.running)


class PrefsTest(unittest.TestCase):
    def test_round_trip_and_fallbacks(self):
        root = Path(tempfile.mkdtemp(prefix="harbor_prefs_"))
        self.addCleanup(shutil.rmtree, root, True)
        path = root / "panel.json"
        self.assertEqual(load_prefs(path, root)["port"], 8642)
        save_prefs(path, {"library": "D:\\Fotos", "backup": "", "port": 9000, "autostart": True})
        self.assertEqual(load_prefs(path, root)["port"], 9000)
        path.write_text(json.dumps({"version": 99, "port": 1}), encoding="utf-8")
        self.assertEqual(load_prefs(path, root)["port"], 8642)
        path.write_text("{", encoding="utf-8")
        self.assertEqual(load_prefs(path, root)["library"], str(root))

    def test_mask_shows_only_the_last_four(self):
        self.assertEqual(mask("abcdefgh1234"), "••••••••1234")
