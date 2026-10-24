"""Wires one library's storage, APIs and web page into a Router."""

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .auth import KeyGuard
from .catalog import Catalog
from .config import Settings
from .database import Database
from .errors import HarborError
from .journal import SyncJournal
from .library_api import LibraryApi
from .messages import Reply, Request
from .router import Router
from .setup_api import SetupApi
from .store import PhotoStore, local_now
from .sync_api import SyncApi
from .thumbs import Thumbnailer

WEB_DIR = Path(__file__).parent / "web"
STATIC_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "app.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "icon.svg": "image/svg+xml",
    "manifest.webmanifest": "application/manifest+json",
}
NO_CACHE = (("Cache-Control", "no-cache"),)


def static_file(request: Request, name: str = "index.html") -> Reply:
    if name not in STATIC_TYPES:
        raise HarborError(f"no file {name}", "the gallery has no such asset", "open /", status=404)
    return Reply(200, content_type=STATIC_TYPES[name], headers=NO_CACHE, file=WEB_DIR / name)


class HarborApp:
    """Owns the database connection; ``close`` releases it."""

    def __init__(self, settings: Settings, port: int, thumbs: Optional[Thumbnailer] = None,
                 now: Callable[[], datetime] = local_now) -> None:
        self.db = Database(settings.state_dir / "catalog.sqlite3")
        catalog = Catalog(self.db)
        journal = SyncJournal(self.db)
        store = PhotoStore(settings.library, catalog, now)
        thumbs = thumbs or Thumbnailer(settings.state_dir / "thumbs")
        self.previews = thumbs.enabled
        self.guard = KeyGuard(settings.key)
        self.router = Router()
        self._register(SyncApi(store, journal, now), LibraryApi(store, catalog, journal, thumbs, now),
                       SetupApi(settings.key, port))

    def _register(self, sync: SyncApi, library: LibraryApi, setup: SetupApi) -> None:
        add = self.router.add
        add("GET", "/", static_file, public=True)
        add("GET", "/static/", static_file, public=True)
        add("POST", "/api/login", self.guard.login, public=True)
        add("POST", "/api/sync/start", sync.start)
        add("POST", "/api/upload", sync.upload)
        add("POST", "/api/sync/done", sync.done)
        add("GET", "/api/has", sync.has)
        add("GET", "/api/status", library.status)
        add("GET", "/api/photos", library.photos)
        add("GET", "/api/outline", library.outline)
        add("GET", "/api/setup", setup.details)
        add("GET", "/media/", library.media)
        add("GET", "/thumb/", library.thumb)

    def close(self) -> None:
        self.db.close()
