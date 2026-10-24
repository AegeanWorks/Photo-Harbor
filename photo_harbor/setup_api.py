"""What the setup page shows: the address and key to type into the iPhone Shortcut."""

import socket

from .autostart import Autostart
from .errors import HarborError
from .messages import Reply, Request, json_reply

PROBE_ADDRESS = ("10.255.255.255", 1)


def lan_address() -> str:
    """The PC's address on the home network; connecting a UDP socket sends no packet."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(PROBE_ADDRESS)
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


class SetupApi:
    """The address and this PC's startup setting; each person's key comes from /api/profiles."""

    def __init__(self, port: int, autostart: Autostart, address=lan_address) -> None:
        self._port = port
        self._autostart = autostart
        self._address = address

    def details(self, request: Request) -> Reply:
        host = request.header("host") or f"{self._address()}:{self._port}"
        if host.startswith(("localhost", "127.")):
            host = f"{self._address()}:{self._port}"
        return json_reply({"server": f"http://{host}",
                           "startup": {"supported": self._autostart.supported,
                                       "enabled": self._autostart.enabled()}})

    def startup(self, request: Request) -> Reply:
        """Owner only: JSON ``{"enabled": true|false}`` turns starting with Windows on or off."""
        if request.identity is None or not request.identity.owner:
            raise HarborError("only the main profile can change how this PC starts Harbor",
                              "this browser is signed in with another person's key",
                              "sign in with the library key", status=403)
        enabled = request.json().get("enabled")
        if not isinstance(enabled, bool):
            raise HarborError("enabled must be true or false", f"got {enabled!r}",
                              'send {"enabled": true}')
        return json_reply({"enabled": self._autostart.set(enabled)})
