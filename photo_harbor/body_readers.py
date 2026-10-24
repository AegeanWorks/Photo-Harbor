"""Request-body readers that know when the body is used up, so a keep-alive connection is only
reused once nothing of the previous request is left unread."""

from typing import BinaryIO

from .errors import HarborError

MAX_CHUNK_LINE = 1024


class LengthReader:
    """At most ``length`` bytes of a ``Content-Length`` body."""

    def __init__(self, raw: BinaryIO, length: int) -> None:
        self._raw = raw
        self._left = length

    @property
    def exhausted(self) -> bool:
        return self._left == 0

    def read(self, size: int = -1) -> bytes:
        want = self._left if size < 0 else min(size, self._left)
        data = self._raw.read(want) if want else b""
        self._left -= len(data)
        if want and not data:
            self._left = -1
        return data


class ChunkedReader:
    """The decoded bytes of a ``Transfer-Encoding: chunked`` body."""

    def __init__(self, raw: BinaryIO) -> None:
        self._raw = raw
        self._left = 0
        self._done = False

    @property
    def exhausted(self) -> bool:
        return self._done

    def read(self, size: int = -1) -> bytes:
        """Up to ``size`` decoded bytes; b"" once the terminating chunk is reached."""
        if self._done:
            return b""
        if self._left == 0:
            self._left = self._next_size()
            if self._left == 0:
                self._finish()
                return b""
        want = self._left if size < 0 else min(size, self._left)
        data = self._raw.read(want)
        if not data:
            raise HarborError("the upload stopped mid-chunk", "the connection closed early",
                              "keep the phone on Wi-Fi; the next sync sends it again")
        self._left -= len(data)
        if self._left == 0:
            self._raw.readline(MAX_CHUNK_LINE)
        return data

    def _next_size(self) -> int:
        line = self._raw.readline(MAX_CHUNK_LINE).split(b";", 1)[0].strip()
        try:
            return int(line, 16)
        except ValueError as exc:
            raise HarborError("the upload's chunk framing is broken", f"bad chunk size {line!r}",
                              "send the file with a Content-Length instead") from exc

    def _finish(self) -> None:
        self._done = True
        while self._raw.readline(MAX_CHUNK_LINE).strip():
            pass
