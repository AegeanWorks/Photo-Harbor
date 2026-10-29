"""The endpoints the gallery reads: status, the photo list, originals and previews."""

import re
import shutil
from datetime import datetime, timedelta
from typing import Callable

from .catalog import Catalog
from .errors import HarborError
from .journal import SyncJournal
from .messages import Reply, Request, json_reply
from .records import PhotoFilter, PhotoRecord
from .store import PhotoStore, local_now, normalise_sha
from .thumbs import Thumbnailer

PAGE_MAX = 200
IMMUTABLE = (("Cache-Control", "private, max-age=31536000, immutable"),)
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MAX_QUERY = 100
LOW_DISK_BYTES = 20 * 1024 ** 3     # warn under 20 GB free...
LOW_DISK_SHARE = 0.10               # ...or under 10 % of the drive, whichever is larger
PROFILE_ID = re.compile(r"^[a-z0-9-]{1,40}$")


def _not_found(sha256: str) -> HarborError:
    return HarborError(f"no photo {sha256[:12]}… on this PC",
                       "it was never received or its file was removed",
                       "reload the gallery", status=404)


def _displayable(kind: str) -> bool:
    """Images and videos show inline; anything else (HTML, SVG with scripts) only downloads."""
    return kind.startswith("video/") or (kind.startswith("image/") and kind != "image/svg+xml")


def photo_json(record: PhotoRecord) -> dict:
    return {"sha256": record.sha256, "name": record.original_name, "type": record.media_type,
            "video": record.is_video, "size": record.size, "taken": record.taken_at,
            "received": record.received_at, "time": record.sort_time,
            "media": f"/media/{record.sha256}", "thumb": f"/thumb/{record.sha256}"}


def _profile_arg(request: Request):
    profile = request.arg("profile") or None
    if profile is not None and not PROFILE_ID.match(profile):
        raise HarborError(f"{profile!r} is not a profile id",
                          "profile ids are lower-case letters, digits and dashes",
                          "use ?profile=main, or leave it out for everyone")
    return profile


def _visible_profile(request: Request):
    """The owner may look at anyone (or, with no ?profile=, everyone); others see only
    themselves, whatever they ask for."""
    asked = _profile_arg(request)
    if request.owner:
        return asked
    if asked is not None and asked != request.profile:
        raise HarborError("those photos are not yours", f"you are signed in as {request.profile!r}",
                          "sign in as that person to see their photos", status=403)
    return request.profile


def _narrowing(request: Request) -> PhotoFilter:
    month = request.arg("month") or None
    kind = request.arg("kind") or None
    query = request.arg("q").strip()[:MAX_QUERY] or None
    if month is not None and not MONTH.match(month):
        raise HarborError(f"{month!r} is not a month", "months are written YYYY-MM",
                          "use ?month=2026-10")
    if kind not in (None, "photo", "video"):
        raise HarborError(f"{kind!r} is not a kind", "kind is photo or video",
                          "use ?kind=video, or leave it out")
    return PhotoFilter(month=month, query=query, kind=kind, profile=_visible_profile(request))


class LibraryApi:
    def __init__(self, store: PhotoStore, catalog: Catalog, journal: SyncJournal,
                 thumbs: Thumbnailer, now: Callable[[], datetime] = local_now) -> None:
        self._store = store
        self._catalog = catalog
        self._journal = journal
        self._thumbs = thumbs
        self._now = now

    def status(self, request: Request) -> Reply:
        profile = _visible_profile(request)
        stats = self._catalog.stats(profile)
        day_ago = (self._now() - timedelta(days=1)).isoformat(timespec="seconds")
        return json_reply({"count": stats.count, "bytes": stats.total_bytes,
                           "last_received": stats.last_received,
                           "last_sync": self._journal.last_sync(profile),
                           "last_day": self._journal.counts_since(day_ago, profile),
                           "missing": self._journal.missing(profile=profile),
                           "disk": self._disk(),
                           "previews": self._thumbs.enabled})

    def photos(self, request: Request) -> Reply:
        try:
            offset = max(int(request.arg("offset", "0")), 0)
            limit = min(max(int(request.arg("limit", "120")), 1), PAGE_MAX)
        except ValueError as exc:
            raise HarborError("offset and limit must be whole numbers", str(exc),
                              "use ?offset=0&limit=120") from exc
        records = self._catalog.page(offset, limit, _narrowing(request))
        return json_reply({"photos": [photo_json(r) for r in records],
                           "next": offset + len(records) if len(records) == limit else None})

    def outline(self, request: Request) -> Reply:
        """Months with photos, newest first, for the browser sidebar."""
        outline = self._catalog.outline(_visible_profile(request))
        return json_reply({"months": [{"month": m, "count": n} for m, n in outline.months],
                           "videos": outline.videos})

    def _disk(self) -> dict:
        usage = shutil.disk_usage(self._store.root)
        return {"free": usage.free, "total": usage.total,
                "low": usage.free < max(LOW_DISK_BYTES, usage.total * LOW_DISK_SHARE)}

    def media(self, request: Request, sha256: str) -> Reply:
        found = self._store.locate(normalise_sha(sha256) or "",
                                   None if request.owner else request.profile)
        if found is None:
            raise _not_found(sha256)
        path, record = found
        if _displayable(record.media_type):
            return Reply(200, content_type=record.media_type, headers=IMMUTABLE, file=path)
        return Reply(200, content_type="application/octet-stream", file=path,
                     headers=IMMUTABLE + (("Content-Disposition", "attachment"),))

    def thumb(self, request: Request, sha256: str) -> Reply:
        found = self._store.locate(normalise_sha(sha256) or "",
                                   None if request.owner else request.profile)
        if found is None:
            raise _not_found(sha256)
        preview = self._thumbs.preview(found[1], found[0])
        if preview is None:
            return json_reply({"preview": None}, status=404)
        return Reply(200, content_type="image/jpeg", headers=IMMUTABLE, file=preview)
