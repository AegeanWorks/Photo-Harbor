"""Endpoints for personal albums and favorites; every write stays inside the caller's profile."""

from .albums import AlbumBook
from .catalog import Catalog
from .errors import HarborError
from .messages import Reply, Request, json_reply
from .selection import visible
from .store import normalise_sha


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
        if "cover" in body:
            cover = normalise_sha(str(body.get("cover") or ""))
            self._albums.set_cover(request.profile, ident, cover)
            return json_reply({"id": int(ident), "cover": cover})
        album = self._albums.rename(request.profile, ident, body.get("name"))
        return json_reply({"id": album.id, "name": album.name})

    def membership(self, request: Request) -> Reply:
        body = request.json()
        sha256s = visible(request, self._catalog, body)
        member = _flag(body, "member")
        album = body.get("album")
        changed = self._albums.add_many(request.profile, album, sha256s, member)
        return json_reply({"album": int(album), "member": member, "changed": changed,
                           "count": len(sha256s),
                           "sha256": sha256s[0] if len(sha256s) == 1 else None})

    def favorite(self, request: Request) -> Reply:
        body = request.json()
        sha256s = visible(request, self._catalog, body)
        favorite = _flag(body, "favorite")
        changed = self._albums.favorite_many(request.profile, sha256s, favorite)
        return json_reply({"favorite": favorite, "changed": changed, "count": len(sha256s),
                           "sha256": sha256s[0] if len(sha256s) == 1 else None})
