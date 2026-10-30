"""Wires one library's storage, APIs and web page into a Router."""

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .accounts import ITERATIONS, Passwords, Sessions
from .albums import AlbumBook
from .albums_api import AlbumsApi
from .auth import KeyGuard
from .autostart import Autostart
from .catalog import Catalog
from .copies import CopyIndex
from .config import Settings
from .database import Database
from .downloads import Downloads
from .downloads_api import DownloadsApi
from .errors import HarborError
from .importer import ImportLedger
from .layout import LibraryLayout
from .journal import SyncJournal
from .library_api import LibraryApi
from .messages import Reply, Request
from .profiles import ProfileBook
from .profiles_api import ProfilesApi
from .router import Router
from .scan import LibraryScanner, ScanSchedule
from .setup_api import SetupApi
from .store import PhotoStore, local_now
from .sync_api import SyncApi
from .thumbs import PreviewWarmer, Thumbnailer
from .trash import TrashBook
from .trash_api import TrashApi

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
                 now: Callable[[], datetime] = local_now,
                 autostart: Optional[Autostart] = None,
                 password_iterations: int = ITERATIONS,
                 android_dir: Optional[Path] = None) -> None:
        self.android_dir = android_dir or WEB_DIR / "android"
        self.db = Database(settings.state_dir / "catalog.sqlite3")
        catalog = Catalog(self.db)
        journal = SyncJournal(self.db)
        self.albums = AlbumBook(self.db, now)
        self.downloads = Downloads(settings.state_dir)
        self.profiles = ProfileBook(self.db, settings.key)
        self.copies = CopyIndex(self.db)
        self.store = PhotoStore(settings.library, catalog, self.copies,
                                folder_of=lambda profile: self.profiles.get(profile).folder, now=now)
        self.trash = TrashBook(self.db, settings.library, self.store, self.copies, now=now)
        thumbs = thumbs or Thumbnailer(settings.state_dir / "thumbs")
        self.previews = thumbs.enabled
        self.warmer = PreviewWarmer(thumbs, catalog, self.store) if thumbs.enabled else None
        if self.warmer is not None:
            self.store.on_stored = self.warmer.add
        self.imports = ImportLedger(self.db)
        self.passwords = Passwords(self.db, password_iterations)
        self.sessions = Sessions(self.db)
        self.layout = LibraryLayout(settings.library, self.db, self.copies, self.profiles,
                                    self.store)
        scanner = LibraryScanner(settings.library, self.db, catalog, self.copies, self.profiles,
                                 self.store, journal)
        self.scanner = scanner
        self.schedule = ScanSchedule(scanner, journal)
        self.guard = KeyGuard(self.profiles, self.passwords, self.sessions)
        self.router = Router()
        self._register(SyncApi(self.store, journal, self.profiles, now),
                       LibraryApi(self.store, catalog, journal, thumbs, self.albums, now),
                       ProfilesApi(self.profiles, catalog, journal, self.passwords,
                                   self.sessions, self.layout),
                       AlbumsApi(self.albums, catalog),
                       DownloadsApi(self.downloads, self.albums, catalog, self.store),
                       TrashApi(self.trash, catalog),
                       SetupApi(port, autostart or Autostart()))

    def android_page(self, request: Request) -> Reply:
        path = self.android_dir / "index.html"
        if not path.is_file():
            raise HarborError("the Android page is missing", str(path),
                              "restore photo_harbor/web/android/index.html", status=404)
        return Reply(200, content_type="text/html; charset=utf-8", headers=NO_CACHE, file=path)

    def android_apk(self, request: Request) -> Reply:
        path = self.android_dir / "Harbor.apk"
        if not path.is_file():
            raise HarborError("the Android app is not built yet",
                              "no Harbor.apk is in the server's android folder",
                              "run python android/build.py, then reload this page", status=404)
        return Reply(200, content_type="application/vnd.android.package-archive",
                     headers=(("Content-Disposition", 'attachment; filename="Harbor.apk"'),
                              ("Cache-Control", "no-cache")),
                     file=path)

    def android_apk_info(self, request: Request) -> Reply:
        path = self.android_dir / "Harbor.apk.json"
        if not path.is_file():
            raise HarborError("the Android build details are missing", str(path),
                              "run python android/build.py, then reload this page", status=404)
        return Reply(200, content_type="application/json; charset=utf-8",
                     headers=NO_CACHE, file=path)

    def _register(self, sync: SyncApi, library: LibraryApi, people: ProfilesApi,
                  albums: AlbumsApi, downloads: DownloadsApi, trash: TrashApi,
                  setup: SetupApi) -> None:
        add = self.router.add
        add("GET", "/", static_file, public=True)
        add("GET", "/static/", static_file, public=True)
        add("GET", "/android", self.android_page, public=True)
        self.router.add_exact("GET", "/android/", self.android_page, public=True)
        add("GET", "/android/Harbor.apk", self.android_apk, public=True)
        add("GET", "/android/Harbor.apk.json", self.android_apk_info, public=True)
        add("POST", "/api/login", self.guard.login, public=True)
        add("GET", "/api/people", self.guard.people, public=True)
        add("POST", "/api/logout", self.guard.logout, public=True)
        add("POST", "/api/password", self.guard.change_password)
        add("POST", "/api/sync/start", sync.start)
        add("POST", "/api/upload", sync.upload)
        add("POST", "/api/sync/done", sync.done)
        add("GET", "/api/has", sync.has)
        add("GET", "/api/status", library.status)
        add("GET", "/api/storage", library.storage)
        add("GET", "/api/photos/hashes", library.hashes)
        add("GET", "/api/photos", library.photos)
        add("GET", "/api/outline", library.outline)
        add("GET", "/api/setup", setup.details)
        add("POST", "/api/startup", setup.startup)
        add("GET", "/api/profiles", people.listing)
        add("POST", "/api/profiles", people.create)
        add("POST", "/api/profiles/", people.update)
        add("GET", "/api/albums", albums.listing)
        add("POST", "/api/albums", albums.create)
        add("POST", "/api/albums/", albums.update)
        add("POST", "/api/album-photos", albums.membership)
        add("POST", "/api/favorite", albums.favorite)
        add("POST", "/api/download", downloads.prepare)
        add("GET", "/api/download/", downloads.serve)
        add("GET", "/api/trash", trash.listing)
        add("POST", "/api/trash", trash.move)
        add("POST", "/api/trash/empty", trash.empty)
        add("POST", "/api/trash/", trash.update)
        add("GET", "/api/details/", library.details)
        add("GET", "/media/", library.media)
        add("GET", "/thumb/", library.thumb)

    def close(self) -> None:
        self.schedule.stop()
        if self.warmer is not None:
            self.warmer.stop()
        self.db.close()
