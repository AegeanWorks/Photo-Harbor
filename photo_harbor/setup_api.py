"""What the setup page shows: the address and key to type into the iPhone Shortcut."""

import socket

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
    def __init__(self, key: str, port: int, address=lan_address) -> None:
        self._key = key
        self._port = port
        self._address = address

    def details(self, request: Request) -> Reply:
        host = request.header("host") or f"{self._address()}:{self._port}"
        if host.startswith(("localhost", "127.")):
            host = f"{self._address()}:{self._port}"
        return json_reply({"server": f"http://{host}", "key": self._key})
