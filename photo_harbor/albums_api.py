"""Endpoints for personal albums and favorites; every write stays inside the caller's profile."""

from .albums import AlbumBook
from .catalog import Catalog
from .errors import HarborError
from .messages import Reply, Request, json_reply
from .store import normalise_sha

MAX_BATCH = 500


def _named(body: dict) -> list:
    """The hashes in ``sha256`` or ``sha256s``, de-duplicated and bounded."""
    values = body.get("sha256s")
    if values is None:
        values = [body.get("sha256")]
    if not isinstance(values, list):
        raise HarborError("sha256s must be a list of hashes", f"got {type(values).__name__}",
                          "send {\"sha256s\": [\"...\"]}", status=400)
    if not values:
        raise HarborError("no photos were named", "the list was empty",
                          "select at least one photo", status=400)
    if len(values) > MAX_BATCH:
        raise HarborError(f"at most {MAX_BATCH} photos at once", f"got {len(values)}",
                          "select fewer photos and try again", status=400)
    sha256s = []
    for value in values:
        sha256 = normalise_sha(str(value or ""))
        if sha256 is None:
            raise HarborError("that is not a photo hash", f"{value!r} is empty",
                              "reload the gallery and try again", status=400)
        if sha256 not in sha256s:
            sha256s.append(sha256)
    return sha256s


def _photos(request: Request, catalog: Catalog, body: dict) -> list:
    """Validate every named photo before any write, so a batch is all or nothing."""
    sha256s = _named(body)
    known = catalog.known(sha256s)
    missing = [sha256 for sha256 in sha256s if sha256 not in known]
    if missing:
        raise HarborError("some of those photos are not on this PC",
                          "one was never received, was removed, or belongs to someone else",
                          "reload the gallery and try again", status=404)
    if not request.owner:
        visible = catalog.copies_of(request.profile, sha256s)
        if any(sha256 not in visible for sha256 in sha256s):
            raise HarborError("some of those photos are not yours",
                              "one was never received, was removed, or belongs to someone else",
                              "reload the gallery and try again", status=404)
    return sha256s


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
        sha256s = _photos(request, self._catalog, body)
        member = _flag(body, "member")
        album = body.get("album")
        changed = self._albums.add_many(request.profile, album, sha256s, member)
        return json_reply({"album": int(album), "member": member, "changed": changed,
                           "count": len(sha256s),
                           "sha256": sha256s[0] if len(sha256s) == 1 else None})

    def favorite(self, request: Request) -> Reply:
        body = request.json()
        sha256s = _photos(request, self._catalog, body)
        favorite = _flag(body, "favorite")
        changed = self._albums.favorite_many(request.profile, sha256s, favorite)
        return json_reply({"favorite": favorite, "changed": changed, "count": len(sha256s),
                           "sha256": sha256s[0] if len(sha256s) == 1 else None})
