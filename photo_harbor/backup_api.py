"""Owner-only view of the daily mirror: target, last attempt and result."""

from typing import Callable, Optional

from .backup import DailyBackup
from .errors import HarborError
from .messages import Reply, Request, json_reply


class BackupApi:
    def __init__(self, backup: Callable[[], Optional[DailyBackup]]) -> None:
        self._backup = backup

    def status(self, request: Request) -> Reply:
        if not request.owner:
            raise HarborError("only the main profile can see the backup",
                              f"you are signed in as {request.profile!r}",
                              "sign in as the main profile", status=403)
        backup = self._backup()
        if backup is None:
            return json_reply({"configured": False})
        status = backup.status()
        return json_reply({
            "configured": True,
            "target": str(status.target),
            "last_at": status.last_at,
            "copied": status.copied,
            "unchanged": status.unchanged,
            "bytes": status.bytes_copied,
            "error": status.error,
        })
