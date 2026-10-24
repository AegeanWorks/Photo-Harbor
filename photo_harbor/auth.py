"""Who is asking: a phone's Shortcut presents its key; a browser signs in with a name and password."""

import ipaddress
from typing import Optional

from .accounts import LoginBrake, Passwords, Sessions
from .database import OWNER_PROFILE
from .errors import HarborError
from .messages import Reply, Request, json_reply
from .profiles import ProfileBook
from .records import Identity

KEY_HEADER = "x-harbor-key"
KEY_COOKIE = "harbor_key"          # older galleries signed in with the key itself
SESSION_COOKIE = "harbor_session"
COOKIE_DAYS = 365


def is_home_network(address: str) -> bool:
    """Private, loopback and link-local addresses; the internet is refused even if port-forwarded."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local


def _cookie(name: str, value: str, days: int = COOKIE_DAYS) -> tuple:
    return ("Set-Cookie", f"{name}={value}; Max-Age={days * 86400}; Path=/; HttpOnly; SameSite=Strict")


def _identity(profile_id: str) -> Identity:
    return Identity(profile=profile_id, owner=profile_id == OWNER_PROFILE)


class KeyGuard:
    def __init__(self, profiles: ProfileBook, passwords: Passwords, sessions: Sessions,
                 brake: Optional[LoginBrake] = None) -> None:
        self._profiles = profiles
        self._passwords = passwords
        self._sessions = sessions
        self._brake = brake or LoginBrake()

    def identify(self, request: Request) -> Optional[Identity]:
        """Shortcut key header first, then a signed-in browser's session, then an old key cookie."""
        key = request.header(KEY_HEADER).strip()  # aikit:allow-secret read from the request
        if key:
            profile = self._profiles.by_key(key)
            return _identity(profile.id) if profile else None
        session = self._sessions.find(request.cookies.get(SESSION_COOKIE, ""))
        if session is not None:
            return _identity(session)
        profile = self._profiles.by_key(request.cookies.get(KEY_COOKIE, "").strip())
        return _identity(profile.id) if profile else None

    def people(self, request: Request) -> Reply:
        """Public: the names for the sign-in screen (this is a home network, not the internet)."""
        return json_reply({"profiles": [
            {"id": p.id, "name": p.name, "has_password": self._passwords.has_password(p.id)}
            for p in self._profiles.all()]})

    def login(self, request: Request) -> Reply:
        """JSON ``{"profile", "password"}``, or ``{"key"}`` for someone without a password yet."""
        self._brake.check(request.client)
        body = request.json()
        profile = None
        if body.get("key"):
            profile = self._profiles.by_key(str(body["key"]).strip())
        elif body.get("profile"):
            candidate = str(body["profile"])
            if self._passwords.matches(candidate, str(body.get("password", ""))):
                profile = self._profiles.get(candidate)
        if profile is None:
            self._brake.failed(request.client)
            raise HarborError("that did not match", "the name and password, or the key, are wrong",
                              "check the password, or sign in with the key from the Harbor window",
                              status=401)
        self._brake.passed(request.client)
        token = self._sessions.start(profile.id)
        return json_reply({"ok": True, "profile": profile.id, "name": profile.name,
                           "has_password": self._passwords.has_password(profile.id)},
                          headers=(_cookie(SESSION_COOKIE, token), _cookie(KEY_COOKIE, "", 0)))

    def logout(self, request: Request) -> Reply:
        self._sessions.close(token=request.cookies.get(SESSION_COOKIE))  # aikit:allow-secret read from the request
        return json_reply({"ok": True}, headers=(_cookie(SESSION_COOKIE, "", 0),
                                                 _cookie(KEY_COOKIE, "", 0)))

    def change_password(self, request: Request) -> Reply:
        """Your own password: JSON ``{"current", "new"}`` (``current`` only if one is set).
        Other browsers signed in as you are signed out; this one stays signed in."""
        me = request.profile
        body = request.json()
        if self._passwords.has_password(me):
            self._brake.check(request.client)
            if not self._passwords.matches(me, str(body.get("current", ""))):
                self._brake.failed(request.client)
                raise HarborError("the current password is wrong", "it did not match",
                                  "type your current password again", status=403)
        self._passwords.set(me, body.get("new"))
        self._sessions.close(profile=me, keep=request.cookies.get(SESSION_COOKIE))
        return json_reply({"ok": True})
