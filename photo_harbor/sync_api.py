"""The endpoints the iPhone Shortcut calls: start, upload, done, and the cleanup's "has" check."""

from datetime import datetime, timedelta
from typing import Callable
from urllib.parse import unquote

from . import journal as kinds
from .errors import HarborError
from .journal import SyncJournal
from .messages import Reply, Request, json_reply
from .naming import parse_taken
from .records import UploadClaim
from .store import PhotoStore, local_now, normalise_sha

FIRST_SYNC_SINCE = "2000-01-01T00:00:00"
CLOCK_SLACK = timedelta(minutes=10)


def _stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class SyncApi:
    def __init__(self, store: PhotoStore, journal: SyncJournal,
                 now: Callable[[], datetime] = local_now) -> None:
        self._store = store
        self._journal = journal
        self._now = now

    def start(self, request: Request) -> Reply:
        """Tell the phone which photos to send: those created after the last finished sync."""
        last = parse_taken(self._journal.last_sync())
        since = _stamp(last - CLOCK_SLACK) if last else FIRST_SYNC_SINCE
        return json_reply({"since": since, "started_at": _stamp(self._now())})

    def upload(self, request: Request) -> Reply:
        # Browsers percent-encode the name because header values must be Latin-1.
        claim = UploadClaim(original_name=unquote(request.header("x-name", "photo")),
                            sha256=request.header("x-sha256") or None,
                            taken_at=request.header("x-taken") or None,
                            modified_at=request.header("x-modified") or None)
        try:
            result = self._store.ingest(request.body, request.length, claim)
        except HarborError as error:
            self._journal.record(_stamp(self._now()), kinds.REJECTED, None,
                                 f"{claim.original_name}: {error.message}")
            raise
        self._journal.record(_stamp(self._now()), result.status, result.record.sha256,
                             result.record.original_name)
        return json_reply({"status": result.status, "sha256": result.record.sha256,
                           "answer": "yes"})

    def has(self, request: Request) -> Reply:
        """``answer`` is ``yes`` only after the PC re-hashes its copy; with ``report=1`` (the
        cleanup) a ``no`` is logged as a photo the phone holds and the PC lacks."""
        sha256 = normalise_sha(request.arg("sha256"))
        if sha256 is None:
            raise HarborError("no hash was given", "the check needs ?sha256=<64 hex characters>",
                              "pass the Generate Hash result in the URL")
        present = self._store.verify(sha256)
        if not present and request.arg("report") == "1":
            self._journal.record(_stamp(self._now()), kinds.MISSING, sha256,
                                 request.arg("name", "")[:255] or None)
        return json_reply({"present": present, "answer": "yes" if present else "no"})

    def done(self, request: Request) -> Reply:
        started = str(request.json().get("started_at", ""))
        if parse_taken(started) is None:
            raise HarborError("the sync's start time is missing",
                              "`done` needs the started_at value that `start` returned",
                              "send {\"started_at\": <value from start>} as JSON")
        self._journal.record(_stamp(self._now()), kinds.SYNC_DONE, None, started)
        return json_reply({"ok": True})
