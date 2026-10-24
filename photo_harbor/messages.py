"""Transport-free request and reply values, so the API can be tested without sockets."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Optional

from .errors import HarborError

MAX_JSON_BYTES = 64 * 1024


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)
    body: Optional[BinaryIO] = None
    length: Optional[int] = 0  # None: chunked, read until the body ends

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)

    def arg(self, name: str, default: str = "") -> str:
        return self.query.get(name, default)

    def json(self) -> dict:
        """The body as a JSON object, or HarborError for anything else."""
        want = MAX_JSON_BYTES + 1 if self.length is None else self.length
        raw = self.body.read(want) if self.body is not None and want <= MAX_JSON_BYTES + 1 else None
        if raw is None or len(raw) > MAX_JSON_BYTES:
            raise HarborError("the request body was refused",
                              f"a JSON body must be at most {MAX_JSON_BYTES} bytes",
                              "send a small JSON object as the request body", status=413)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if not isinstance(data, dict):
            raise HarborError("the request body is not a JSON object",
                              "the server could not read it as {\"name\": value} pairs",
                              "set the Shortcut's Request Body to JSON")
        return data


@dataclass(frozen=True)
class Reply:
    status: int
    body: bytes = b""
    content_type: str = "application/json; charset=utf-8"
    headers: tuple = ()
    file: Optional[Path] = None


def json_reply(data, status: int = 200, headers: tuple = ()) -> Reply:
    return Reply(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), headers=headers)


def error_reply(error: HarborError) -> Reply:
    return json_reply(error.as_dict(), status=error.status)


def parse_range(value: Optional[str], size: int) -> Optional[tuple]:
    """``(first, last)`` for one satisfiable ``bytes=`` range, else None for the whole file."""
    if not value or not value.startswith("bytes=") or "," in value or size == 0:
        return None
    first_text, _, last_text = value[6:].strip().partition("-")
    try:
        if first_text == "":
            first, last = max(size - int(last_text), 0), size - 1
        else:
            first = int(first_text)
            last = min(int(last_text), size - 1) if last_text else size - 1
    except ValueError:
        return None
    if first < 0 or first > last:
        return None
    return first, last
