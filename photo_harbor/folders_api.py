"""Read-only folder tree from the per-person year/month library layout."""

from .catalog import Catalog
from .messages import Reply, Request, json_reply
from .profiles import ProfileBook


class FoldersApi:
    def __init__(self, profiles: ProfileBook, catalog: Catalog) -> None:
        self._profiles = profiles
        self._catalog = catalog

    def listing(self, request: Request) -> Reply:
        folders = []
        for person in self._profiles.all():
            if not request.owner and person.id != request.profile:
                continue
            outline = self._catalog.outline(person.id, viewer=request.profile)
            if not outline.months:
                continue
            root = person.folder or person.id
            folders.append({
                "profile": person.id,
                "name": person.name,
                "folder": person.folder,
                "months": [{"month": month, "count": count,
                            "path": f"{root}/{month[:4]}/{month}"}
                           for month, count in outline.months],
            })
        return json_reply({"folders": folders})
