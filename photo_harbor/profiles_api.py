"""Listing people and, for the library owner, adding, renaming and re-keying them."""

from .accounts import Passwords, Sessions
from .catalog import Catalog
from .layout import LibraryLayout
from .errors import HarborError
from .journal import SyncJournal
from .messages import Reply, Request, json_reply
from .profiles import ProfileBook


def _require_owner(request: Request) -> None:
    if request.identity is None or not request.identity.owner:
        raise HarborError("only the main profile can manage people",
                          f"you are signed in as {request.profile!r}",
                          "sign in as the main profile", status=403)


class ProfilesApi:
    def __init__(self, book: ProfileBook, catalog: Catalog, journal: SyncJournal,
                 passwords: Passwords, sessions: Sessions, layout: LibraryLayout) -> None:
        self._book = book
        self._catalog = catalog
        self._journal = journal
        self._passwords = passwords
        self._sessions = sessions
        self._layout = layout

    def listing(self, request: Request) -> Reply:
        """The owner sees everyone; anyone else sees only themselves (with their own key)."""
        me = request.identity
        people = []
        for profile in self._book.all():
            if me is None or not (me.owner or me.profile == profile.id):
                continue
            stats = self._catalog.stats(profile.id)
            people.append({"id": profile.id, "name": profile.name, "folder": profile.folder,
                           "key": profile.key, "count": stats.count, "bytes": stats.total_bytes,
                           "last_sync": self._journal.last_sync(profile.id),
                           "has_password": self._passwords.has_password(profile.id)})
        return json_reply({"me": me.profile if me else None, "owner": bool(me and me.owner),
                           "profiles": people})

    def create(self, request: Request) -> Reply:
        _require_owner(request)
        body = request.json()
        profile = self._book.create(str(body.get("name", "")))
        self._layout.prepare()
        if body.get("password"):
            self._passwords.set(profile.id, body["password"])
        return json_reply({"id": profile.id, "name": profile.name, "key": profile.key})

    def update(self, request: Request, ident: str) -> Reply:
        """JSON ``{"name": "..."}`` renames (and renames their folder); ``{"new_key": true}``
        replaces the Shortcut key; ``{"password": "..."}`` sets a new password and signs that
        person out everywhere."""
        _require_owner(request)
        body = request.json()
        if body.get("name") is not None:
            self._layout.rename_person(ident, str(body["name"]))
        if body.get("password") is not None:
            self._passwords.set(self._book.get(ident).id, body["password"])
            self._sessions.close(profile=ident)
        profile = self._book.update(ident, new_key=body.get("new_key") is True)
        return json_reply({"id": profile.id, "name": profile.name, "key": profile.key})
