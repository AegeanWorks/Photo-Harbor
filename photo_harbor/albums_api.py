"""Endpoints for personal albums and favorites; every write stays inside the caller's profile."""

from .albums import AlbumBook
from .catalog import Catalog
from .errors import HarborError
from .messages import Reply, Request, json_reply
from .store import normalise_sha


def _photo(request: Request, catalog: Catalog, value) -> str:
    sha256 = normalise_sha(str(value or ""))
    visible = sha256 is not None and catalog.get(sha256) is not None
    if visible and not request.owner:
        visible = catalog.has_copy(request.profile, sha256)
    if not visible:
        raise HarborError("no photo with that hash on this PC",
                          "it was never received, was removed, or belongs to someone else",
                          "reload the gallery and try again", status=404)
    return sha256


def _flag(body: dict, name: str) -> bool:
    value = body.get(name)
    if not isinstance(value, bool):
        raise HarborError(f"{name} must be true or false", f"got {value!r}",
                          f"send {{\"{name}\": true}}", status=400)
    return value


class AlbumsApi:
    def __init__(self, albums: AlbumBook, catalog: Catalog) -> None:
        self._albums = albums
        self._catalog = catalog

    def listing(self, request: Request) -> Reply:
        favorites, albums = self._albums.summary(request.profile)
        return json_reply({
            "favorites": favorites,
            "albums": [{"id": album.id, "name": album.name, "count": album.count,
                        "cover": f"/thumb/{album.cover}" if album.cover else None}
                       for album in albums],
        })

    def create(self, request: Request) -> Reply:
        album = self._albums.create(request.profile, request.json().get("name"))
        return json_reply({"id": album.id, "name": album.name, "count": 0, "cover": None},
                          status=201)

    def update(self, request: Request, ident: str) -> Reply:
        body = request.json()
        if body.get("delete") is True:
            self._albums.delete(request.profile, ident)
            return json_reply({"deleted": True})
        album = self._albums.rename(request.profile, ident, body.get("name"))
        return json_reply({"id": album.id, "name": album.name})

    def membership(self, request: Request) -> Reply:
        body = request.json()
        sha256 = _photo(request, self._catalog, body.get("sha256"))
        member = _flag(body, "member")
        album = body.get("album")
        changed = self._albums.add(request.profile, album, sha256, member)
        return json_reply({"album": int(album), "sha256": sha256, "member": member,
                           "changed": changed})

    def favorite(self, request: Request) -> Reply:
        body = request.json()
        sha256 = _photo(request, self._catalog, body.get("sha256"))
        favorite = _flag(body, "favorite")
        changed = self._albums.favorite(request.profile, sha256, favorite)
        return json_reply({"sha256": sha256, "favorite": favorite, "changed": changed})
