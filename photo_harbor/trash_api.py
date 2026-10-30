"""Endpoints for the per-person trash: list, move, restore, delete and empty."""

from .errors import HarborError
from .messages import Reply, Request, json_reply
from .selection import visible
from .trash import TrashBook


def _item_json(item) -> dict:
    return {"id": item.id, "sha256": item.sha256, "name": item.name, "size": item.size,
            "type": item.media_type, "taken": item.taken_at, "trashed": item.trashed_at}


class TrashApi:
    def __init__(self, trash: TrashBook, catalog) -> None:
        self._trash = trash
        self._catalog = catalog

    def listing(self, request: Request) -> Reply:
        return json_reply({"items": [_item_json(item)
                                     for item in self._trash.listing(request.profile)]})

    def move(self, request: Request) -> Reply:
        sha256s = visible(request, self._catalog, request.json())
        copies = self._catalog.copies_of(request.profile, sha256s)
        if any(sha256 not in copies for sha256 in sha256s):
            raise HarborError("some of those photos are not in your library",
                              "the main profile can only trash its own copies",
                              "select the person whose photo it is, or sign in as them",
                              status=400)
        ids = [self._trash.move(request.profile, sha256) for sha256 in sha256s]
        return json_reply({"moved": len(ids), "ids": ids})

    def update(self, request: Request, ident: str) -> Reply:
        body = request.json()
        if body.get("restore") is True:
            result = self._trash.restore(request.profile, ident)
            return json_reply({"restored": True, "id": int(ident), "status": result.status})
        if body.get("delete") is True:
            self._trash.delete(request.profile, ident)
            return json_reply({"deleted": True})
        raise HarborError("say restore or delete", "neither was true",
                          "send {\"restore\": true} or {\"delete\": true}", status=400)

    def empty(self, request: Request) -> Reply:
        count = self._trash.empty(request.profile)
        return json_reply({"deleted": count})
