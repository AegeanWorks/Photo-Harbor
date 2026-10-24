"""The library as people see it in File Explorer: one folder per person, a year folder, a month
folder, and the original files with their own names. Harbor's own files stay in hidden .harbor."""

import ctypes
import os
from pathlib import Path

from .atomic_file import write_atomic
from .copies import CopyIndex
from .database import Database
from .errors import HarborError
from .naming import parse_taken
from .profiles import ProfileBook
from .records import Profile
from .store import PhotoStore

LEGACY = "photos"
GUIDE = "READ ME - Harbor.txt"
FILE_ATTRIBUTE_HIDDEN = 0x2

GUIDE_TEXT = """Harbor photo library
====================

Every person has a folder here, named after them:

    Ayşe\\2026\\2026-10\\IMG_1234.HEIC
    (person) (year) (month)  (the original file, untouched)

You can open, copy and back up these folders like any others; Harbor is not needed to see them.

- Photos and videos you put into a person's month folder are picked up by Harbor.
- Moving a file to another folder inside the same person's folder is fine.
- Deleting a file removes it from Harbor for that person.
- A photo that two people both have appears in both folders but takes space only once.
- The hidden ".harbor" folder belongs to Harbor (catalog, previews, settings). Leave it as it is.

----

Harbor fotoğraf arşivi
======================

Her kişinin burada kendi adıyla bir klasörü vardır:

    Ayşe\\2026\\2026-10\\IMG_1234.HEIC
    (kişi) (yıl) (ay)    (orijinal dosya, değiştirilmez)

Bu klasörleri diğer klasörler gibi açabilir, kopyalayabilir ve yedekleyebilirsiniz; görmek için
Harbor gerekmez.

- Bir kişinin ay klasörüne koyduğunuz fotoğraf ve videoları Harbor da görür.
- Dosyayı aynı kişinin klasörü içinde başka bir yere taşımak sorun değildir.
- Bir dosyayı silmek onu o kişi için Harbor'dan da kaldırır.
- İki kişide birden olan bir fotoğraf iki klasörde de görünür ama diskte bir kez yer kaplar.
- Gizli ".harbor" klasörü Harbor'a aittir (katalog, önizlemeler, ayarlar). Lütfen dokunmayın.
"""


def hide(path: Path) -> None:
    """Mark a folder hidden in File Explorer (Windows only; elsewhere the dot already hides it)."""
    if os.name == "nt" and path.exists():
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)


class LibraryLayout:
    def __init__(self, root: Path, db: Database, copies: CopyIndex, profiles: ProfileBook,
                 store: PhotoStore) -> None:
        self._root = root
        self._db = db
        self._copies = copies
        self._profiles = profiles
        self._store = store

    def prepare(self) -> int:
        """Guide file, hidden .harbor, a folder for everyone, and files from the old photos/
        layout moved into place. Returns how many files moved. Safe to run at every start."""
        guide = self._root / GUIDE
        if not guide.exists():
            write_atomic(guide, GUIDE_TEXT.replace("\n", "\r\n").encode("utf-8-sig"))
        hide(self._root / ".harbor")
        for profile in self._profiles.all():
            (self._root / profile.folder).mkdir(parents=True, exist_ok=True)
        return self._move_legacy()

    def rename_person(self, ident: str, name: str) -> Profile:
        """Rename a person and their folder; every catalogued path inside it follows."""
        person = self._profiles.get(ident)
        new_folder = self._profiles.free_folder(name, keep=ident)
        with self._store.lock:
            if new_folder != person.folder:
                old_dir, new_dir = self._root / person.folder, self._root / new_folder
                try:
                    if old_dir.exists():
                        os.replace(old_dir, new_dir)
                    else:
                        new_dir.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    raise HarborError(f"the folder {person.folder} could not be renamed",
                                      str(exc), "close any window or program using a file in "
                                      "that folder, then try again", status=409) from exc
                self._repoint(person.folder, new_folder)
            return self._profiles.update(ident, name=name, folder=new_folder)

    def _repoint(self, old: str, new: str) -> None:
        pattern = old.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "/%"
        with self._db.lock:
            for table in ("copies", "photos"):
                # substr is 1-based: skip "<old>/" and keep the rest of the path.
                self._db.conn.execute(
                    f"UPDATE {table} SET rel_path = ? || substr(rel_path, ?)"
                    " WHERE rel_path LIKE ? ESCAPE '!'",
                    (new + "/", len(old) + 2, pattern))

    def _move_legacy(self) -> int:
        """Move each file still under photos/ into its owner's folder, one at a time, so an
        interrupted run simply continues next time."""
        with self._db.lock:
            rows = self._db.conn.execute(
                "SELECT c.profile, c.sha256, c.rel_path, c.original_name, p.sort_time"
                " FROM copies c JOIN photos p ON p.sha256 = c.sha256 WHERE c.rel_path LIKE ?",
                (LEGACY + "/%",)).fetchall()
        moved = 0
        for row in rows:
            source = self._root / row["rel_path"]
            if not source.is_file():
                continue
            with self._store.lock:
                moment = parse_taken(row["sort_time"])
                target = next(self._store.candidate_paths(row["profile"], moment,
                                                          row["original_name"], row["sha256"]))
                os.replace(source, target)
                self._copies.move(row["rel_path"], target.relative_to(self._root).as_posix())
                moved += 1
        self._remove_empty(self._root / LEGACY)
        return moved

    @staticmethod
    def _remove_empty(folder: Path) -> None:
        if not folder.is_dir():
            return
        for directory in sorted((d for d in folder.rglob("*") if d.is_dir()),
                                key=lambda d: len(d.parts), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
        if not any(folder.iterdir()):
            folder.rmdir()
