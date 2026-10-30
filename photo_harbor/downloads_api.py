"""Prepare one ZIP for a selection or album, then serve it once through a short token."""

from .albums import AlbumBook
from .catalog import Catalog
from .downloads import Downloads
from .errors import HarborError
from .messages import Reply, Request, json_reply
from .naming import safe_name
from .selection import check, visible
from .store import PhotoStore

ALBUM_LIMIT = 10_000


class DownloadsApi:
    def __init__(self, downloads: Downloads, albums: AlbumBook, catalog: Catalog,
                 store: PhotoStore) -> None:
        self._downloads = downloads
        self._albums = albums
        self._catalog = catalog
        self._store = store

    def prepare(self, request: Request) -> Reply:
        body = request.json()
        album = body.get("album")
        if album is not None:
            if not self._albums.owned(request.profile, album):
                raise HarborError(f"no album {album}", "it was deleted or belongs to someone else",
                                  "reload the gallery and try again", status=404)
            sha256s = check(request, self._catalog,
                            self._albums.members(request.profile, album), limit=ALBUM_LIMIT)
            _, albums = self._albums.summary(request.profile)
            found = next((item for item in albums if item.id == int(album)), None)
            label = found.name if found else "album"
        else:
            sha256s = visible(request, self._catalog, body)
            label = "selection"
        entries = []
        for sha256 in sha256s:
            found = self._store.locate(sha256, None if request.owner else request.profile)
            if found is None:
                raise HarborError("a photo disappeared before it could be zipped",
                                  "it was removed from this person's folder",
                                  "reload the gallery and try again", status=404)
            path, record = found
            entries.append((record, path))
        name = f"{safe_name(f'Harbor - {label}')}.zip"
        return json_reply(self._downloads.prepare(entries, name, request.profile))

    def serve(self, request: Request, token: str) -> Reply:
        item = self._downloads.take(token, request.profile)
        if item is None:
            raise HarborError("that download is gone", "the token expired or was already used",
                              "prepare the download again", status=404)
        path, name, _ = item
        header = name.encode("ascii", "replace").decode("ascii")
        return Reply(200, content_type="application/zip",
                     headers=(("Content-Disposition", f'attachment; filename="{header}"'),
                              ("Cache-Control", "no-store")),
                     file=path, delete_after=True)
