"""Starts and stops one server in the background, for the command line and the Harbor window."""

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .app import HarborApp
from .backup import DailyBackup
from .config import load_or_create
from .errors import HarborError
from .http_server import HarborServer
from .setup_api import lan_address


@dataclass(frozen=True)
class RunningServer:
    port: int
    local_url: str
    lan_url: str
    library: Path
    previews: bool


class ServerRunner:
    def __init__(self, library: Path, port: int, host: str = "0.0.0.0",
                 backup_to: Optional[Path] = None, log: Callable[[str], None] = print,
                 verbose: bool = True) -> None:
        self._library = library
        self._port = port
        self._host = host
        self._backup_to = backup_to
        self._log = log
        self._verbose = verbose
        self._lock = threading.Lock()
        self.app: Optional[HarborApp] = None
        self._server: Optional[HarborServer] = None
        self._thread: Optional[threading.Thread] = None
        self._backup: Optional[DailyBackup] = None

    @property
    def running(self) -> bool:
        return self._server is not None

    def start(self) -> RunningServer:
        """Open the library and serve it on a background thread; HarborError if the port is busy."""
        with self._lock:
            if self._server is not None:
                raise HarborError("the server is already running", "Start was pressed twice",
                                  "press Stop first")
            app = HarborApp(load_or_create(self._library), self._port)
            moved = app.layout.prepare()
            if moved:
                self._log(f"Moved {moved} photos into the per-person folders.")
            try:
                server = HarborServer((self._host, self._port), app.router, app.guard,
                                      verbose=self._verbose)
            except OSError as exc:
                app.close()
                raise HarborError(f"port {self._port} is not available", str(exc),
                                  "close the other Harbor window, or choose another port") from exc
            self.app, self._server = app, server
            self._thread = threading.Thread(target=server.serve_forever, name="harbor-server",
                                            kwargs={"poll_interval": 0.25}, daemon=True)
            self._thread.start()
            if app.warmer is not None:
                app.warmer.start()
            app.schedule.log = self._log  # scan results reach the window's Activity log
            app.schedule.start()
            if self._backup_to is not None:
                self._backup = DailyBackup(self._library, self._backup_to, self._log)
                app.backup = self._backup
                self._backup.start()
            port = server.server_address[1]
            return RunningServer(port, f"http://localhost:{port}", f"http://{lan_address()}:{port}",
                                 self._library, app.previews)

    def stop(self) -> None:
        with self._lock:
            if self._server is None:
                return
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5)
            if self._backup is not None:
                self._backup.stop()
            self.app.close()
            self.app = self._server = self._thread = self._backup = None

    def wait(self) -> None:
        """Block until the server stops (Ctrl+C in a console stops it)."""
        while self._thread is not None and self._thread.is_alive():
            self._thread.join(0.5)
