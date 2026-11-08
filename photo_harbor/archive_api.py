"""Endpoint for the per-person archive: hide or restore a validated batch."""

from .archive import ArchiveBook
from .catalog import Catalog
from .errors import HarborError
from .messages import Reply, Request, json_reply
from .selection import visible


class ArchiveApi:
    def __init__(self, archive: ArchiveBook, catalog: Catalog) -> None:
        self._archive = archive
        self._catalog = catalog

    def update(self, request: Request) -> Reply:
        body = request.json()
        sha256s = visible(request, self._catalog, body)
        archived = body.get("archived")
        if not isinstance(archived, bool):
            raise HarborError("archived must be true or false", f"got {archived!r}",
                              'send {"archived": true}', status=400)
        changed = self._archive.set_many(request.profile, sha256s, archived)
        return json_reply({"archived": archived, "changed": changed, "count": len(sha256s)})
