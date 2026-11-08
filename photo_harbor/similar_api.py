"""Read-only Similar review: perceptual hashes, no automatic deletion."""

from .catalog import Catalog
from .errors import HarborError
from .library_api import photo_json
from .messages import Reply, Request, json_reply
from .phash import read_dhash
from .store import PhotoStore

SCAN_DEFAULT = 50
SCAN_MAX = 200


class SimilarApi:
    def __init__(self, catalog: Catalog, store: PhotoStore, dhash=read_dhash) -> None:
        self._catalog = catalog
        self._store = store
        self._dhash = dhash

    def _profile(self, request: Request):
        return None if request.owner else request.profile

    def _status(self, request: Request) -> dict:
        return self._catalog.similar_status(self._profile(request), viewer=request.profile)

    def listing(self, request: Request) -> Reply:
        profile = self._profile(request)
        groups = self._catalog.similar_groups(profile, viewer=request.profile)
        return json_reply({
            "status": self._status(request),
            "groups": [{"hash": dhash, "count": len(records),
                        "photos": [photo_json(record) for record in records]}
                       for dhash, records in groups],
        })

    def scan(self, request: Request) -> Reply:
        body = request.json()
        try:
            limit = int(body.get("limit", SCAN_DEFAULT))
        except (TypeError, ValueError) as exc:
            raise HarborError("limit must be a whole number", str(exc),
                              "use {\"limit\": 50}") from exc
        if limit < 1 or limit > SCAN_MAX:
            raise HarborError(f"scan at most {SCAN_MAX} photos at once", f"got {limit}",
                              "press Scan again for the rest", status=400)
        profile = self._profile(request)
        hashes = self._catalog.missing_hashes(profile, viewer=request.profile, limit=limit)
        indexed = skipped = 0
        for sha256 in hashes:
            located = self._store.locate(sha256, None if request.owner else request.profile)
            value = self._dhash(located[0]) if located is not None else None
            if value is None:
                self._catalog.set_hash(sha256, "skip")
                skipped += 1
            else:
                self._catalog.set_hash(sha256, value)
                indexed += 1
        return json_reply({"processed": len(hashes), "indexed": indexed,
                           "skipped": skipped, "status": self._status(request)})
