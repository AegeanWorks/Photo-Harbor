"""The socket side: turns HTTP into a Request, runs the matched endpoint and sends its Reply."""

import dataclasses
import os
import sys
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, unquote, urlsplit

from .auth import KeyGuard, is_home_network
from .body_readers import ChunkedReader, LengthReader
from .errors import HarborError
from .messages import Reply, Request, error_reply, parse_range
from .router import Router

COPY_CHUNK = 1 << 20
SOCKET_TIMEOUT = 120
BASE_HEADERS = (("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"))
HTML_POLICY = ("default-src 'self'; img-src 'self' blob: data:; media-src 'self'; "
               "style-src 'self'; script-src 'self'; frame-ancestors 'none'")


def _refusal(status: int, message: str, why: str, fix: str) -> Reply:
    return error_reply(HarborError(message, why, fix, status=status))


class HarborHandler(BaseHTTPRequestHandler):
    """Built per connection by ThreadingHTTPServer; ``router`` and ``guard`` come from the server."""

    protocol_version = "HTTP/1.1"
    server_version = "photo-harbor"
    timeout = SOCKET_TIMEOUT

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def log_request(self, code="-", size="-") -> None:
        if self.server.verbose and (self.command != "GET" or str(code)[:1] in ("4", "5")):
            super().log_request(code, size)

    def log_error(self, format, *args) -> None:
        if self.server.verbose:
            super().log_error(format, *args)

    def _dispatch(self, method: str) -> None:
        self._body = None
        url = urlsplit(self.path)
        path = unquote(url.path)
        if not is_home_network(self.client_address[0]):
            self._send(_refusal(403, "only devices on the home network may connect",
                                f"{self.client_address[0]} is not a private address",
                                "connect the phone to the same Wi-Fi as the PC"))
            return
        route = self.server.router.match(method, path)
        if route is None:
            self._send(_refusal(404, f"nothing at {path}", "the address is not one photo-harbor serves",
                                "open the gallery at /"))
            return
        try:
            request = self._request(method, path, url.query)
            identity = self.server.guard.identify(request)
            if not route.public and identity is None:
                raise HarborError("the key is missing or wrong",
                                  "every call except the gallery page needs a profile's key",
                                  "send the X-Harbor-Key header, or sign in on the gallery",
                                  status=401)
            request = dataclasses.replace(request, identity=identity,
                                          client=self.client_address[0])
            reply = route.handler(request, route.param) if route.param else route.handler(request)
        except HarborError as error:
            reply = error_reply(error)
        except Exception:  # hygiene: allow last-resort guard so one bad request never stops the server
            traceback.print_exc(file=sys.stderr)
            reply = _refusal(500, "the server hit an unexpected problem",
                             "details are in the server window", "try again; report it if it repeats")
        self._send(reply)

    def _request(self, method: str, path: str, query: str) -> Request:
        headers = {key.lower(): value for key, value in self.headers.items()}
        cookies = {name: morsel.value for name, morsel in SimpleCookie(headers.get("cookie", "")).items()}
        length = None
        if "chunked" in headers.get("transfer-encoding", "").lower():
            self._body = ChunkedReader(self.rfile)
        else:
            try:
                length = int(headers.get("content-length", "0"))
            except ValueError as exc:
                raise HarborError("the Content-Length header is not a number", str(exc),
                                  "send a numeric Content-Length") from exc
            if length < 0:
                raise HarborError("the Content-Length header is negative", str(length),
                                  "send a non-negative Content-Length")
            self._body = LengthReader(self.rfile, length)
        return Request(method, path, dict(parse_qsl(query)), headers, cookies, self._body, length)

    def _send(self, reply: Reply) -> None:
        if self._body is None or not self._body.exhausted:
            self.close_connection = True
        if reply.file is not None:
            self._send_file(reply)
            return
        self.send_response(reply.status)
        self._headers(reply, len(reply.body))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(reply.body)

    def _send_file(self, reply: Reply) -> None:
        try:
            size = reply.file.stat().st_size
            span = parse_range(self.headers.get("Range"), size)
            first, last = span if span else (0, size - 1)
            self.send_response(206 if span else 200)
            self._headers(reply, last - first + 1)
            self.send_header("Accept-Ranges", "bytes")
            if span:
                self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
            self.end_headers()
            with open(reply.file, "rb") as handle:
                handle.seek(first)
                remaining = last - first + 1
                while remaining > 0:
                    block = handle.read(min(COPY_CHUNK, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        finally:
            if reply.delete_after:
                try:
                    reply.file.unlink(missing_ok=True)
                except OSError:  # hygiene: allow locked temp download must not break the response
                    pass

    def _headers(self, reply: Reply, length: int) -> None:
        self.send_header("Content-Type", reply.content_type)
        self.send_header("Content-Length", str(length))
        for name, value in BASE_HEADERS + reply.headers:
            self.send_header(name, value)
        if reply.content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", HTML_POLICY)
        if self.close_connection:
            self.send_header("Connection", "close")


class HarborServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second server bind the same port without an error.
    allow_reuse_address = os.name != "nt"

    def __init__(self, address: tuple, router: Router, guard: KeyGuard, verbose: bool = True) -> None:
        self.router = router
        self.guard = guard
        self.verbose = verbose
        super().__init__(address, HarborHandler)

    def handle_error(self, request, client_address) -> None:
        """A client closing its connection is normal (Windows reports an idle keep-alive closing
        as ConnectionAbortedError); anything else is still printed."""
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)
