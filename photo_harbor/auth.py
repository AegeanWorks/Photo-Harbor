"""Who may talk to the server: devices on the home network that present the library key."""

import hmac
import ipaddress

from .errors import HarborError
from .messages import Reply, Request, json_reply

KEY_HEADER = "x-harbor-key"
KEY_COOKIE = "harbor_key"
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


class KeyGuard:
    def __init__(self, key: str) -> None:
        self._key = key.encode("utf-8")

    def admits(self, request: Request) -> bool:
        presented = request.header(KEY_HEADER) or request.cookies.get(KEY_COOKIE, "")
        return hmac.compare_digest(presented.strip().encode("utf-8"), self._key)

    def login(self, request: Request) -> Reply:
        """Trade the key for a long-lived cookie so the gallery need not ask again."""
        key = str(request.json().get("key", "")).strip()
        if not hmac.compare_digest(key.encode("utf-8"), self._key):
            raise HarborError("that key is not this library's key",
                              "the key did not match the one stored on the PC",
                              "copy the key that `python -m photo_harbor key` prints", status=401)
        cookie = (f"{KEY_COOKIE}={key}; Max-Age={COOKIE_DAYS * 86400}; Path=/; HttpOnly;"
                  " SameSite=Strict")
        return json_reply({"ok": True}, headers=(("Set-Cookie", cookie),))
