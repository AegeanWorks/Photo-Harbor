"""The library's settings file: format version and the upload key the phone presents."""

import json
import secrets
from dataclasses import dataclass
from pathlib import Path

from .atomic_file import write_atomic
from .errors import HarborError

CONFIG_VERSION = 1
DEFAULT_LIBRARY = Path.home() / "Pictures" / "Harbor"


@dataclass(frozen=True)
class Settings:
    library: Path
    key: str

    @property
    def state_dir(self) -> Path:
        return self.library / ".harbor"


def _config_path(library: Path) -> Path:
    return library / ".harbor" / "config.json"


def _parse(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != CONFIG_VERSION:
        raise HarborError(f"{path} has settings format {data.get('version')!r}",
                          f"this photo-harbor reads format {CONFIG_VERSION} only",
                          "run the photo-harbor version that created this library")
    key = data.get("key")
    if not isinstance(key, str) or len(key) < 16:
        raise ValueError("key missing or too short")
    return key


def load_or_create(library: Path) -> Settings:
    """Read the settings, restoring ``.bak`` if the file is damaged; create them on first run."""
    path = _config_path(library)
    if not path.exists():
        return rotate_key(library)
    try:
        return Settings(library, _parse(path))
    except (ValueError, json.JSONDecodeError):
        backup = path.with_name(path.name + ".bak")
        path.replace(path.with_name(path.name + ".corrupt"))
        try:
            key = _parse(backup)
        except (OSError, ValueError, json.JSONDecodeError):
            key = None
        if key is not None:
            write_atomic(path, backup.read_bytes())
            return Settings(library, key)
        raise HarborError(f"{path} is damaged and has no backup",
                          "the upload key cannot be read, so the phone could not be recognised",
                          "run `python -m photo_harbor key --new` and update the Shortcut",
                          status=500)


def rotate_key(library: Path) -> Settings:
    """Write a fresh random key; a phone holding the old key is refused from now on."""
    key = secrets.token_urlsafe(24)  # aikit:allow-secret generated at runtime, not a stored value
    payload = json.dumps({"version": CONFIG_VERSION, "key": key}, indent=2).encode("utf-8")
    write_atomic(_config_path(library), payload, keep_backup=True)
    return Settings(library, key)
