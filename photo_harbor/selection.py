"""Validate the photos a bulk request names, so a batch is all or nothing."""

from .catalog import Catalog
from .errors import HarborError
from .messages import Request
from .store import normalise_sha

MAX_BATCH = 500


def named(body: dict, limit: int = MAX_BATCH) -> list:
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
    if len(values) > limit:
        raise HarborError(f"at most {limit} photos at once", f"got {len(values)}",
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


def check(request: Request, catalog: Catalog, sha256s: list,
          limit: int = MAX_BATCH) -> list:
    """Validate a known list of hashes before any write."""
    if not sha256s:
        raise HarborError("no photos were named", "the list was empty",
                          "select at least one photo", status=400)
    if len(sha256s) > limit:
        raise HarborError(f"at most {limit} photos at once", f"got {len(sha256s)}",
                          "select fewer photos and try again", status=400)
    sha256s = list(dict.fromkeys(sha256s))
    known = catalog.known(sha256s)
    if any(sha256 not in known for sha256 in sha256s):
        raise HarborError("some of those photos are not on this PC",
                          "one was never received, was removed, or belongs to someone else",
                          "reload the gallery and try again", status=404)
    if not request.owner:
        copies = catalog.copies_of(request.profile, sha256s)
        if any(sha256 not in copies for sha256 in sha256s):
            raise HarborError("some of those photos are not yours",
                              "one was never received, was removed, or belongs to someone else",
                              "reload the gallery and try again", status=404)
    return sha256s


def visible(request: Request, catalog: Catalog, body: dict,
            limit: int = MAX_BATCH) -> list:
    """Validate the photos a request body names before any write."""
    return check(request, catalog, named(body, limit), limit)
