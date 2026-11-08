"""Endpoints for personal tags; every write stays inside the caller's profile."""

from .catalog import Catalog
from .errors import HarborError
from .messages import Reply, Request, json_reply
from .selection import visible
from .store import normalise_sha
from .tags import TagBook


def _flag(body: dict, name: str) -> bool:
    value = body.get(name)
    if not isinstance(value, bool):
        raise HarborError(f"{name} must be true or false", f"got {value!r}",
                          f"send {{\"{name}\": true}}", status=400)
    return value


def _sha_arg(request: Request):
    value = request.arg("sha256") or None
    if value is None:
        return None
    sha256 = normalise_sha(value)
    if sha256 is None:
        raise HarborError("that is not a photo hash", f"{value!r} is empty",
                          "reload the gallery and try again", status=400)
    return sha256


class TagApi:
    def __init__(self, tags: TagBook, catalog: Catalog) -> None:
        self._tags = tags
        self._catalog = catalog

    def listing(self, request: Request) -> Reply:
        """Every tag and, when ?sha256= is present, whether it is on that photo."""
        summary = self._tags.summary(request.profile)
        sha256 = _sha_arg(request)
        members = set(self._tags.members(request.profile, sha256)) if sha256 else set()
        return json_reply({
            "sha256": sha256,
            "tags": [{"id": tag.id, "name": tag.name, "count": tag.count,
                      "member": tag.id in members} for tag in summary],
        })

    def create(self, request: Request) -> Reply:
        body = request.json()
        tag = self._tags.create(request.profile, body.get("name"))
        changed = 0
        count = 0
        if "sha256" in body or "sha256s" in body:
            sha256s = visible(request, self._catalog, body)
            changed = self._tags.add_many(request.profile, tag.id, sha256s, True)
            count = len(sha256s)
        return json_reply({"id": tag.id, "name": tag.name, "changed": changed, "count": count},
                          status=201)

    def update(self, request: Request, ident: str) -> Reply:
        body = request.json()
        if body.get("delete") is True:
            self._tags.delete(request.profile, ident)
            return json_reply({"deleted": True})
        tag = self._tags.rename(request.profile, ident, body.get("name"))
        return json_reply({"id": tag.id, "name": tag.name})

    def membership(self, request: Request) -> Reply:
        body = request.json()
        sha256s = visible(request, self._catalog, body)
        member = _flag(body, "member")
        tag = body.get("tag")
        changed = self._tags.add_many(request.profile, tag, sha256s, member)
        return json_reply({"tag": int(tag), "member": member, "changed": changed,
                           "count": len(sha256s),
                           "sha256": sha256s[0] if len(sha256s) == 1 else None})
