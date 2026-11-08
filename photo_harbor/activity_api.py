"""Read-only recent journal events for the Activity view."""

from .errors import HarborError
from .journal import SyncJournal
from .messages import Reply, Request, json_reply

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


class ActivityApi:
    def __init__(self, journal: SyncJournal) -> None:
        self._journal = journal

    def listing(self, request: Request) -> Reply:
        try:
            limit = int(request.arg("limit", str(DEFAULT_LIMIT)))
        except ValueError as exc:
            raise HarborError("limit must be a whole number", str(exc),
                              "use ?limit=100") from exc
        if limit < 1 or limit > MAX_LIMIT:
            raise HarborError(f"limit must be 1 to {MAX_LIMIT}", f"got {limit}",
                              "use ?limit=100", status=400)
        profile = None if request.owner else request.profile
        return json_reply({"events": self._journal.recent(limit, profile)})
