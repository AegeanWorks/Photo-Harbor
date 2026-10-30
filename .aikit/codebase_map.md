# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `59`
- **Total Classes**: `109`
- **Total Top-Level Functions**: `92`
- **Total Class Methods**: `414`
- **Total Source Lines**: `6826`

---

## 📦 Modules & Exported Symbols

### [`photo_harbor/__init__.py`](photo_harbor/__init__.py)
> *photo-harbor: a self-hosted photo server that an iPhone feeds through Apple Shortcuts.*

**Size**: `3` lines (`116` bytes)

---

### [`photo_harbor/__main__.py`](photo_harbor/__main__.py)
> *Command line: ``python -m photo_harbor serve | panel | key | profiles | import | backup``.*

**Size**: `143` lines (`6151` bytes)

**Functions:**
- `def _parser()`
- `def _serve(args, library)`
- `def _with_app(library, action)` - *Run ``action(app)`` against the library without serving it.*
- `def _profiles(args, app)`
- `def _import(args, library, app)`
- `def main(argv)`

---

### [`photo_harbor/accounts.py`](photo_harbor/accounts.py)
> *Signing in with a name and a password: password hashes, sessions, and a brake on guessing.*

**Size**: `149` lines (`6027` bytes)

**Classes:**
- `class Passwords`
  - Method `.__init__(db, iterations)`
  - Method `.has_password(profile)`
  - Method `.set(profile, password)`
  - Method `.matches(profile, password)`
- `class Sessions` - *A signed-in browser holds a random token; only its SHA-256 is stored.*
  - Method `.__init__(db, now)`
  - Method `.start(profile)`
  - Method `.find(token)`
  - Method `.close(token, profile, keep)` - *End one session (``token``), or all of ``profile``'s except ``keep``.*
- `class LoginBrake` - *After 5 wrong passwords from one address, that address waits 5 minutes.*
  - Method `.__init__(clock)`
  - Method `.check(address)`
  - Method `.failed(address)`
  - Method `.passed(address)`

**Functions:**
- `def hash_password(password, iterations, salt)` - *``pbkdf2_sha256$<iterations>$<salt>$<hash>``: the password itself is never stored.*
- `def password_matches(password, stored)`
- `def check_new_password(password)`
- `def _token_hash(token)`
- `def _stamp(moment)`

---

### [`photo_harbor/albums.py`](photo_harbor/albums.py)
> *Personal albums and favorites: named collections that never move or copy a file.*

**Size**: `175` lines (`8008` bytes)

**Classes:**
- `class AlbumBook` - *Albums belong to one person; favorites are that person's own mark on a photo.*
  - Method `.__init__(db, now)`
  - Method `.summary(profile)` - *``(favorite count, [Album, ...])`` for the signed-in person, names in A-Z order.*
  - Method `.create(profile, name)`
  - Method `.rename(profile, ident, name)`
  - Method `.delete(profile, ident)`
  - Method `.owned(profile, ident)` - *Whether this person owns the album; a bad id is a 400, a missing one is False.*
  - Method `.members(profile, ident)` - *The hashes in one owned album, newest photo first.*
  - Method `.add(profile, ident, sha256, member)` - *Put a photo in an album or take it out; True when the album changed.*
  - Method `.add_many(profile, ident, sha256s, member)` - *Add or remove several photos in one lock; returns how many rows changed.*
  - Method `.favorite(profile, sha256, favorite)` - *Mark or unmark one photo for one person; True when the mark changed.*
  - Method `.favorite_many(profile, sha256s, favorite)` - *Mark or unmark several photos in one lock; returns how many rows changed.*
  - Method `._owned(profile, album)`

**Functions:**
- `def _clean_name(value)`
- `def _album_id(value)`

---

### [`photo_harbor/albums_api.py`](photo_harbor/albums_api.py)
> *Endpoints for personal albums and favorites; every write stays inside the caller's profile.*

**Size**: `61` lines (`2675` bytes)

**Classes:**
- `class AlbumsApi`
  - Method `.__init__(albums, catalog)`
  - Method `.listing(request)`
  - Method `.create(request)`
  - Method `.update(request, ident)`
  - Method `.membership(request)`
  - Method `.favorite(request)`

**Functions:**
- `def _flag(body, name)`

---

### [`photo_harbor/app.py`](photo_harbor/app.py)
> *Wires one library's storage, APIs and web page into a Router.*

**Size**: `136` lines (`6304` bytes)

**Classes:**
- `class HarborApp` - *Owns the database connection; ``close`` releases it.*
  - Method `.__init__(settings, port, thumbs, now, autostart, password_iterations)`
  - Method `._register(sync, library, people, albums, downloads, trash, setup)`
  - Method `.close()`

**Functions:**
- `def static_file(request, name)`

---

### [`photo_harbor/atomic_file.py`](photo_harbor/atomic_file.py)
> *Crash-safe file placement: temp file, fsync, atomic replace, directory fsync.*

**Size**: `45` lines (`1420` bytes)

**Functions:**
- `def write_atomic(path, data, keep_backup)` - *Replace ``path`` with ``data`` so a power cut leaves the old or the new file, never half.*
- `def replace_with_retry(src, dst)` - *os.replace, retried because Windows briefly locks files that a scanner has open.*
- `def fsync_dir(directory)` - *Persist a directory entry; Windows cannot open a directory, and NTFS journals it anyway.*

---

### [`photo_harbor/auth.py`](photo_harbor/auth.py)
> *Who is asking: a phone's Shortcut presents its key; a browser signs in with a name and password.*

**Size**: `104` lines (`4976` bytes)

**Classes:**
- `class KeyGuard`
  - Method `.__init__(profiles, passwords, sessions, brake)`
  - Method `.identify(request)` - *Shortcut key header first, then a signed-in browser's session, then an old key cookie.*
  - Method `.people(request)` - *Public: the names for the sign-in screen (this is a home network, not the internet).*
  - Method `.login(request)` - *JSON ``{"profile", "password"}``, or ``{"key"}`` for someone without a password yet.*
  - Method `.logout(request)`
  - Method `.change_password(request)` - *Your own password: JSON ``{"current", "new"}`` (``current`` only if one is set).*

**Functions:**
- `def is_home_network(address)` - *Private, loopback and link-local addresses; the internet is refused even if port-forwarded.*
- `def _cookie(name, value, days)`
- `def _identity(profile_id)`

---

### [`photo_harbor/autostart.py`](photo_harbor/autostart.py)
> *Starting Harbor when the user signs in to Windows, through the per-user Run registry key.*

**Size**: `72` lines (`2958` bytes)

**Classes:**
- `class WindowsRunKey` - *HKEY_CURRENT_USER's Run key: no administrator rights needed, and only this user is affected.*
  - Method `.read()`
  - Method `.write(command)`
  - Method `.delete()`
- `class Autostart`
  - Method `.__init__(registry, command, supported)`
  - Method `.enabled()`
  - Method `.set(enabled)` - *Turn starting with Windows on or off; returns the new state.*

**Functions:**
- `def launch_command(python, launcher)` - *``pythonw.exe`` (no console window) running ``Harbor.pyw --startup``.*

---

### [`photo_harbor/backup.py`](photo_harbor/backup.py)
> *A second copy of the library's originals on another drive, so one disk failure loses nothing.*

**Size**: `145` lines (`4946` bytes)

**Classes:**
- `class BackupReport`
- `class VerifyReport`
  - Property `.ok`
- `class DailyBackup` - *Mirrors at start-up and every 24 hours on a background thread while the server runs.*
  - Method `.__init__(source, target, log)`
  - Method `.start()`
  - Method `.stop()`
  - Method `._run()`

**Functions:**
- `def _refuse_inside(source, target)`
- `def _files(root)` - *Every visible file below ``root``, skipping Harbor's dot folders.*
- `def _digest(path)`
- `def verify(source, target)` - *Re-hash every source original against its backup copy; extras there are reported only.*
- `def mirror(source, target)` - *Copy each original missing from ``target`` or differing in size; never deletes there.*

---

### [`photo_harbor/body_readers.py`](photo_harbor/body_readers.py)
> *Request-body readers that know when the body is used up, so a keep-alive connection is only*

**Size**: `73` lines (`2361` bytes)

**Classes:**
- `class LengthReader` - *At most ``length`` bytes of a ``Content-Length`` body.*
  - Method `.__init__(raw, length)`
  - Property `.exhausted`
  - Method `.read(size)`
- `class ChunkedReader` - *The decoded bytes of a ``Transfer-Encoding: chunked`` body.*
  - Method `.__init__(raw)`
  - Property `.exhausted`
  - Method `.read(size)` - *Up to ``size`` decoded bytes; b"" once the terminating chunk is reached.*
  - Method `._next_size()`
  - Method `._finish()`

---

### [`photo_harbor/catalog.py`](photo_harbor/catalog.py)
> *The index of stored originals: one row per distinct file, keyed by SHA-256.*

**Size**: `227` lines (`11414` bytes)

**Classes:**
- `class Catalog`
  - Method `.__init__(db)`
  - Method `.add(record)` - *Insert ``record``; False when its hash is already catalogued. A path another record*
  - Method `.get(sha256)`
  - Method `.known(sha256s)` - *The hashes in ``sha256s`` that the catalog holds, in one query.*
  - Method `.copies_of(profile, sha256s)` - *The hashes in ``sha256s`` that sit in ``profile``'s folder, in one query.*
  - Method `.page(offset, limit, narrow)` - *Records in the requested order, newest first by default (taken time, then received).*
  - Method `.outline(profile, viewer)` - *Months and video count, for one profile or (None) everyone, plus the viewer's*
  - Method `.stats(profile)`
  - Method `.storage(profile)` - *Disk use and the ten largest files; one person's share or the whole library.*

**Functions:**
- `def _to_record(row)`
- `def _source(narrow)` - *``(FROM clause, columns, alias of the owner side)``. One person's view reads their own*
- `def _where(narrow, owner)`
- `def _totals_source(profile)`

---

### [`photo_harbor/config.py`](photo_harbor/config.py)
> *The library's settings file: format version and the upload key the phone presents.*

**Size**: `69` lines (`2525` bytes)

**Classes:**
- `class Settings`
  - Property `.state_dir`

**Functions:**
- `def _config_path(library)`
- `def _parse(path)`
- `def load_or_create(library)` - *Read the settings, restoring ``.bak`` if the file is damaged; create them on first run.*
- `def rotate_key(library)` - *Write a fresh random key; a phone holding the old key is refused from now on.*

---

### [`photo_harbor/control_panel.py`](photo_harbor/control_panel.py)
> *The Harbor window: Start/Stop the server, open the photo browser, manage people, import folders.*

**Size**: `568` lines (`27217` bytes)

**Classes:**
- `class ControlPanel` - *Builds the window; background work reports back through ``_inbox`` on the Tk thread.*
  - Method `.__init__(root, prefs_path, default_library, startup, autostart)` - *``startup``: launched by Windows at sign-in, so start serving at once, minimised.*
  - Method `._style()`
  - Method `._card(parent, title)`
  - Method `._build()`
  - Method `._folder_row(parent, row, label, variable)`
  - Method `.toggle_server()`
  - Method `._start_and_maybe_browse()`
  - Method `._set_windows_start()`
  - Method `.open_browser()`
  - Method `.add_person()`
  - Method `.open_folder(folder)` - *Open the library, or one person's folder, in File Explorer.*
  - Method `.check_files()`
  - Method `.check_backup()`
  - Method `._verify_worker(source, target)`
  - Method `.set_password(ident, name)`
  - Method `.rename(ident, name)`
  - Method `._person_menu(profile)`
  - Method `._show_space()` - *Free space on the library's drive; a warning under 20 GB or 10 %.*
  - Method `.new_key(ident, name)`
  - Method `.import_folder()`
  - Method `._import_worker(app, folder, library, profile)`
  - Method `.copy(text)`
  - Method `.log(text, error)`
  - Method `.close()`
  - Method `._save()`
  - Method `._set_running_ui()`
  - Method `._refresh_people()`
  - Method `._drain()` - *Apply messages from background threads; Tk widgets may only be touched here.*

**Functions:**
- `def load_prefs(path, default_library)` - *Saved window choices; defaults when the file is missing, damaged or from another version.*
- `def save_prefs(path, prefs)`
- `def mask(key)`
- `def main(library, startup)` - *Open the window; returns when it is closed. ``startup``: launched at Windows sign-in.*

---

### [`photo_harbor/copies.py`](photo_harbor/copies.py)
> *Whose folder holds which photo. One file can sit in several people's folders (hard links).*

**Size**: `68` lines (`3294` bytes)

**Classes:**
- `class CopyIndex`
  - Method `.__init__(db)`
  - Method `.add(profile, photo, rel_path, original_name, added_at)` - *Record ``profile``'s copy of ``photo``; False when that person already has it.*
  - Method `.path_for(profile, sha256)`
  - Method `.paths_of(sha256)` - *``[(profile, rel_path), ...]`` for every copy of one photo, oldest first.*
  - Method `.move(old, new)` - *A file moved inside the library (reorganised, renamed folder, moved in Explorer).*
  - Method `.forget(profile, sha256)` - *Drop one person's copy (they deleted the file). True when no copy is left anywhere, in*

---

### [`photo_harbor/database.py`](photo_harbor/database.py)
> *The SQLite file behind the catalog, people, copies, sign-ins, journal and import list.*

**Size**: `240` lines (`8608` bytes)

**Classes:**
- `class Database` - *One shared connection; every statement runs under ``lock`` so server threads take turns.*
  - Method `.__init__(path)`
  - Method `._open_schema(path)`
  - Method `._apply(script)` - *Run ``script`` and stamp the version in one transaction: all of it or none.*
  - Method `._backup(target)` - *A consistent copy of the catalog before it is migrated.*
  - Method `.close()`

---

### [`photo_harbor/details.py`](photo_harbor/details.py)
> *File and camera facts for one original, read on demand without touching the catalog.*

**Size**: `110` lines (`3177` bytes)

**Functions:**
- `def _text(value)`
- `def _exposure(value)`
- `def _aperture(value)`
- `def _focal(value)`
- `def _iso(value)`
- `def _camera(make, model)`
- `def read_details(record, path)` - *File facts always; width, height and EXIF fields when Pillow can read them.*

---

### [`photo_harbor/downloads.py`](photo_harbor/downloads.py)
> *One-off ZIP archives for a selection or album, with expiring one-time tokens.*

**Size**: `106` lines (`4327` bytes)

**Classes:**
- `class Downloads` - *Builds stored ZIPs in the library's state directory; tokens live in memory.*
  - Method `.__init__(state_dir, clock)`
  - Method `.clean()` - *Startup cleanup: no token survives a restart, so no archive should either.*
  - Method `.prepare(entries, name, profile)` - *Write ``[(PhotoRecord, path), ...]`` to a new ZIP and return its token details.*
  - Method `.take(token, profile)` - *The ``(path, name, bytes)`` for this person's live token, removing it.*
  - Method `._expire_locked()`

**Functions:**
- `def _entry_name(record, used)`

---

### [`photo_harbor/downloads_api.py`](photo_harbor/downloads_api.py)
> *Prepare one ZIP for a selection or album, then serve it once through a short token.*

**Size**: `60` lines (`2798` bytes)

**Classes:**
- `class DownloadsApi`
  - Method `.__init__(downloads, albums, catalog, store)`
  - Method `.prepare(request)`
  - Method `.serve(request, token)`

---

### [`photo_harbor/errors.py`](photo_harbor/errors.py)
> *The one error type photo-harbor raises for problems a person can fix.*

**Size**: `18` lines (`629` bytes)

**Classes:**
- `class HarborError` - *A failure with a cause and a remedy, mapped to an HTTP status when served.*
  - Method `.__init__(message, why, fix, status)`
  - Method `.as_text()`
  - Method `.as_dict()`

---

### [`photo_harbor/exif_dates.py`](photo_harbor/exif_dates.py)
> *The capture time stored inside a photo, for uploads that arrive without one (browser uploads).*

**Size**: `27` lines (`974` bytes)

**Functions:**
- `def read_taken(path)` - *``YYYY-MM-DDTHH:MM:SS`` from EXIF DateTimeOriginal, or None without Pillow or a date.*

---

### [`photo_harbor/http_server.py`](photo_harbor/http_server.py)
> *The socket side: turns HTTP into a Request, runs the matched endpoint and sends its Reply.*

**Size**: `166` lines (`7469` bytes)

**Classes:**
- `class HarborHandler` - *Built per connection by ThreadingHTTPServer; ``router`` and ``guard`` come from the server.*
  - Method `.do_GET()`
  - Method `.do_POST()`
  - Method `.log_request(code, size)`
  - Method `.log_error(format, *args)`
  - Method `._dispatch(method)`
  - Method `._request(method, path, query)`
  - Method `._send(reply)`
  - Method `._send_file(reply)`
  - Method `._headers(reply, length)`
- `class HarborServer`
  - Method `.__init__(address, router, guard, verbose)`
  - Method `.handle_error(request, client_address)` - *A client closing its connection is normal (Windows reports an idle keep-alive closing*

**Functions:**
- `def _refusal(status, message, why, fix)`

---

### [`photo_harbor/importer.py`](photo_harbor/importer.py)
> *Bringing photos already on the PC's disk into a profile, without touching the source folder.*

**Size**: `112` lines (`4607` bytes)

**Classes:**
- `class ImportReport`
  - Property `.summary`
- `class ImportLedger` - *Source files already imported, by path, size and modification time. A file that is*
  - Method `.__init__(db)`
  - Method `.known(source, size, mtime_ns)`
  - Method `.remember(source, size, mtime_ns, sha256)`

**Functions:**
- `def find_media(folder, library)` - *Photos and videos under ``folder``, sorted; the Harbor library itself is skipped.*
- `def _modified(stat)`
- `def import_folder(store, folder, library, profile, progress, stop, ledger)` - *Copy each photo in; each file is hashed by the store, so re-running adds only new ones.*

---

### [`photo_harbor/journal.py`](photo_harbor/journal.py)
> *What the phone did and when: uploads, finished syncs and photos the PC lacked at cleanup.*

**Size**: `68` lines (`3048` bytes)

**Classes:**
- `class SyncJournal`
  - Method `.__init__(db)`
  - Method `.record(at, kind, sha256, detail, profile)`
  - Method `.last_sync(profile)` - *The start time of the latest finished sync, for one profile or (None) anyone.*
  - Method `.last_event(kind)` - *When the latest event of ``kind`` was recorded.*
  - Method `.counts_since(since, profile)`
  - Method `.missing(limit, profile)` - *Photos a phone holds that the PC still lacks, newest report first; one person's*

---

### [`photo_harbor/layout.py`](photo_harbor/layout.py)
> *The library as people see it in File Explorer: one folder per person, a year folder, a month*

**Size**: `148` lines (`6416` bytes)

**Classes:**
- `class LibraryLayout`
  - Method `.__init__(root, db, copies, profiles, store)`
  - Method `.prepare()` - *Guide file, hidden .harbor, a folder for everyone, and files from the old photos/*
  - Method `.rename_person(ident, name)` - *Rename a person and their folder; every catalogued path inside it follows.*
  - Method `._repoint(old, new)`
  - Method `._move_legacy()` - *Move each file still under photos/ into its owner's folder, one at a time, so an*
  - Method `._remove_empty(folder)`

**Functions:**
- `def hide(path)` - *Mark a folder hidden in File Explorer (Windows only; elsewhere the dot already hides it).*

---

### [`photo_harbor/library_api.py`](photo_harbor/library_api.py)
> *The endpoints the gallery reads: status, the photo list, originals and previews.*

**Size**: `189` lines (`9294` bytes)

**Classes:**
- `class LibraryApi`
  - Method `.__init__(store, catalog, journal, thumbs, albums, now)`
  - Method `.status(request)`
  - Method `.storage(request)` - *Counts, bytes, per-person shares and the largest files the caller may see.*
  - Method `.photos(request)`
  - Method `.outline(request)` - *Months with photos, newest first, for the browser sidebar.*
  - Method `._disk()`
  - Method `.details(request, sha256)`
  - Method `.media(request, sha256)`
  - Method `.thumb(request, sha256)`

**Functions:**
- `def _not_found(sha256)`
- `def _displayable(kind)` - *Images and videos show inline; anything else (HTML, SVG with scripts) only downloads.*
- `def photo_json(record)`
- `def _profile_arg(request)`
- `def _visible_profile(request)` - *The owner may look at anyone (or, with no ?profile=, everyone); others see only*
- `def _narrowing(request, albums)`

---

### [`photo_harbor/messages.py`](photo_harbor/messages.py)
> *Transport-free request and reply values, so the API can be tested without sockets.*

**Size**: `93` lines (`3385` bytes)

**Classes:**
- `class Request`
  - Property `.profile` - *The caller's profile id; the owner's when the route is public.*
  - Property `.owner`
  - Method `.header(name, default)`
  - Method `.arg(name, default)`
  - Method `.json()` - *The body as a JSON object, or HarborError for anything else.*
- `class Reply`

**Functions:**
- `def json_reply(data, status, headers)`
- `def error_reply(error)`
- `def parse_range(value, size)` - *``(first, last)`` for one satisfiable ``bytes=`` range, else None for the whole file.*

---

### [`photo_harbor/naming.py`](photo_harbor/naming.py)
> *Where an original lands on disk: <Person>/<YYYY>/<YYYY-MM>/<safe file name>.*

**Size**: `60` lines (`2178` bytes)

**Functions:**
- `def safe_name(original)` - *A Windows-safe base name; a name that sanitises to nothing becomes ``photo``.*
- `def parse_taken(value)` - *ISO 8601 as Shortcuts formats it; anything unreadable counts as unknown.*
- `def month_folder(moment)` - *``2026/2026-10``: the year to browse by, then a month folder that sorts and reads alone.*
- `def folder_name(name)` - *A person's folder as they would name it, made safe for Windows: ``Ayşe`` stays ``Ayşe``.*
- `def media_type(name)`

---

### [`photo_harbor/pillow_support.py`](photo_harbor/pillow_support.py)
> *Optional Pillow loading, with HEIC support when pillow-heif is installed.*

**Size**: `24` lines (`715` bytes)

**Functions:**
- `def load_image()` - *Pillow's ``Image`` module, or None when Pillow is not installed.*
- `def load_pillow()` - *``(Image, ImageOps)``, or None when Pillow is not installed.*

---

### [`photo_harbor/profiles.py`](photo_harbor/profiles.py)
> *The people a library belongs to: a name, an id, a folder in the library and a Shortcut key.*

**Size**: `128` lines (`5840` bytes)

**Classes:**
- `class ProfileBook`
  - Method `.__init__(db, owner_key)` - *Make sure the owner profile exists and holds the library key, and that every person*
  - Method `.all()` - *Owner first, then the others by name.*
  - Method `.get(ident)`
  - Method `.by_key(key)`
  - Method `.create(name)`
  - Method `.update(ident, name, new_key, folder)` - *Rename a person (``folder`` is set by the layout once their folder has moved), or give*
  - Method `.free_folder(name, keep)` - *``Ayşe``, or ``Ayşe (2)`` when that folder name (any letter case) is already taken.*

**Functions:**
- `def profile_id(name)` - *A URL-safe id: ``Ayşe Yılmaz`` becomes ``ayse-yilmaz``.*
- `def clean_name(name)`
- `def _to_profile(row)`
- `def _now()`

---

### [`photo_harbor/profiles_api.py`](photo_harbor/profiles_api.py)
> *Listing people and, for the library owner, adding, renaming and re-keying them.*

**Size**: `65` lines (`3102` bytes)

**Classes:**
- `class ProfilesApi`
  - Method `.__init__(book, catalog, journal, passwords, sessions, layout)`
  - Method `.listing(request)` - *The owner sees everyone; anyone else sees only themselves (with their own key).*
  - Method `.create(request)`
  - Method `.update(request, ident)` - *JSON ``{"name": "..."}`` renames (and renames their folder); ``{"new_key": true}``*

**Functions:**
- `def _require_owner(request)`

---

### [`photo_harbor/records.py`](photo_harbor/records.py)
> *Immutable values passed between the store, the catalog and the web layer.*

**Size**: `156` lines (`3611` bytes)

**Classes:**
- `class PhotoRecord` - *One stored original, identified by the SHA-256 of its bytes.*
  - Property `.sort_time`
  - Property `.is_video`
- `class UploadClaim` - *What the phone says about a file before its bytes are checked.*
- `class IngestResult` - *``status`` is ``stored`` for a new file or ``duplicate`` when the bytes were already held.*
- `class LibraryStats`
- `class PhotoFilter` - *Gallery narrowing: ``month`` is ``YYYY-MM``, ``start``/``end`` are inclusive*
- `class Outline` - *What the browser sidebar lists: ``(YYYY-MM, count)`` newest first, the video count and the*
- `class Album` - *One person's named collection; ``cover`` is the newest member's SHA-256, if any.*
- `class PersonStorage` - *One person's share: shared photos count in each person's share.*
- `class StorageFile` - *One row of the largest-files list.*
- `class StorageReport` - *Disk use for one profile, or for the whole library when ``profile`` is None.*
- `class TrashItem` - *One recoverable removal; the bytes sit under ``.harbor/trash`` until restored or deleted.*
- `class Profile` - *A person: ``folder`` is their folder in the library, ``key`` is what their Shortcut sends.*
- `class Identity` - *Who a request comes from; the owner (library key) may manage every profile.*

---

### [`photo_harbor/router.py`](photo_harbor/router.py)
> *Maps a method and path to an endpoint; a path ending in ``/`` passes the rest as a parameter.*

**Size**: `31` lines (`1112` bytes)

**Classes:**
- `class Route`
- `class Router`
  - Method `.__init__()`
  - Method `.add(method, path, handler, public)`
  - Method `.match(method, path)`

---

### [`photo_harbor/runner.py`](photo_harbor/runner.py)
> *Starts and stops one server in the background, for the command line and the Harbor window.*

**Size**: `92` lines (`3711` bytes)

**Classes:**
- `class RunningServer`
- `class ServerRunner`
  - Method `.__init__(library, port, host, backup_to, log, verbose)`
  - Property `.running`
  - Method `.start()` - *Open the library and serve it on a background thread; HarborError if the port is busy.*
  - Method `.stop()`
  - Method `.wait()` - *Block until the server stops (Ctrl+C in a console stops it).*

---

### [`photo_harbor/scan.py`](photo_harbor/scan.py)
> *Keeping the catalog in step with the folders, and checking that every file is still intact.*

**Size**: `238` lines (`10035` bytes)

**Classes:**
- `class ScanReport`
- `class CheckReport`
- `class LibraryScanner`
  - Method `.__init__(root, db, catalog, copies, profiles, store, journal, now, clock)`
  - Method `.reconcile(stop)`
  - Method `.check(stop)` - *Re-hash every catalogued file; damaged ones are reported, never deleted.*
  - Method `._tracked()`
  - Method `._media_in(folder)`
  - Method `._register(profile, path, rel, missing)` - *An untracked file in ``profile``'s folder: a moved copy, a new copy, or a new photo.*
- `class ScanSchedule` - *Reconciles at start and every 6 hours; checks every file when the last full check is a*
  - Method `.__init__(scanner, journal, log)`
  - Method `.start()`
  - Method `.run_now(full)`
  - Method `.stop()`
  - Method `._due_check()` - *A full re-read is heavy: the first one comes a week after Harbor first ran.*
  - Method `._run()`
  - Method `._pass()`

**Functions:**
- `def _stamp(moment)`

---

### [`photo_harbor/selection.py`](photo_harbor/selection.py)
> *Validate the photos a bulk request names, so a batch is all or nothing.*

**Size**: `63` lines (`2889` bytes)

**Functions:**
- `def named(body, limit)` - *The hashes in ``sha256`` or ``sha256s``, de-duplicated and bounded.*
- `def check(request, catalog, sha256s, limit)` - *Validate a known list of hashes before any write.*
- `def visible(request, catalog, body, limit)` - *Validate the photos a request body names before any write.*

---

### [`photo_harbor/setup_api.py`](photo_harbor/setup_api.py)
> *What the setup page shows: the address and key to type into the iPhone Shortcut.*

**Size**: `50` lines (`2104` bytes)

**Classes:**
- `class SetupApi` - *The address and this PC's startup setting; each person's key comes from /api/profiles.*
  - Method `.__init__(port, autostart, address)`
  - Method `.details(request)`
  - Method `.startup(request)` - *Owner only: JSON ``{"enabled": true|false}`` turns starting with Windows on or off.*

**Functions:**
- `def lan_address()` - *The PC's address on the home network; connecting a UDP socket sends no packet.*

---

### [`photo_harbor/store.py`](photo_harbor/store.py)
> *Receives originals, proves their bytes against the phone's hash, and re-proves them on request.*

**Size**: `308` lines (`14436` bytes)

**Classes:**
- `class PhotoStore`
  - Method `.__init__(library, catalog, copies, folder_of, now, embedded_date, on_stored)` - *``folder_of`` maps a profile id to that person's folder name in the library.*
  - Method `.ingest(stream, length, claim)` - *Stream ``length`` bytes (None: until the stream ends) to disk; keep them only when the*
  - Method `.verify(sha256)` - *True only when some catalogued copy exists and its bytes still hash to ``sha256``.*
  - Method `.locate(sha256, profile)` - *``(path, record)`` of ``profile``'s copy, or of any copy when no profile is given.*
  - Method `.ensure_copy(profile, sha256)` - *Make sure ``profile``'s folder holds this photo, linking it from another person's*
  - Method `._check_capacity(length)`
  - Method `._receive(stream, length, tmp)`
  - Method `._place(tmp, sha256, size, claim)`
  - Method `._known(tmp, existing, claim)` - *Bytes the library already has: repair a damaged copy, or give this person their own.*
  - Method `._link_new_copy(source, record, profile, name)`
  - Method `.candidate_paths(profile, moment, original, sha256)` - *Free paths in the person's month folder: the name, then the name with a hash suffix.*
  - Method `._intact(sha256)` - *The first copy whose size and SHA-256 still match, or None.*
  - Method `._rel(path)`

**Functions:**
- `def local_now()`
- `def hash_file(path)`
- `def normalise_sha(value)` - *Lower-case hex, or HarborError when the text is not a SHA-256.*
- `def link_or_copy(source, target)` - *A second name for the same file (no extra space); a real copy where links are refused.*
- `def _stamp(moment)`

---

### [`photo_harbor/sync_api.py`](photo_harbor/sync_api.py)
> *The endpoints the iPhone Shortcut calls: start, upload, done, and the cleanup's "has" check.*

**Size**: `94` lines (`4828` bytes)

**Classes:**
- `class SyncApi`
  - Method `.__init__(store, journal, book, now)`
  - Method `.start(request)` - *Tell the phone which photos to send: those created after the last finished sync.*
  - Method `.upload(request)`
  - Method `.has(request)` - *``answer`` is ``yes`` only after the PC re-hashes its copy; with ``report=1`` (the*
  - Method `.done(request)`

**Functions:**
- `def _stamp(moment)`
- `def _target_profile(request, book)` - *A person's own profile; the owner may upload for anyone with ``X-Profile``.*

---

### [`photo_harbor/thumbs.py`](photo_harbor/thumbs.py)
> *Small JPEG previews, made only when the optional Pillow (and pillow-heif for HEIC) is installed.*

**Size**: `101` lines (`3701` bytes)

**Classes:**
- `class Thumbnailer`
  - Method `.__init__(cache_dir, pillow)`
  - Property `.enabled`
  - Method `.preview(record, original)` - *The cached preview, made on first request; None for videos or unreadable images.*
- `class PreviewWarmer` - *Makes previews ahead of time on one background thread, so a large library scrolls without*
  - Method `.__init__(thumbs, catalog, store, page)`
  - Method `.start()`
  - Method `.add(record)`
  - Method `.stop()`
  - Method `._warm(record)`
  - Method `._run()`

---

### [`photo_harbor/trash.py`](photo_harbor/trash.py)
> *A per-person trash: move a copy aside, restore it through the normal ingest, or delete it.*

**Size**: `124` lines (`5568` bytes)

**Classes:**
- `class TrashBook`
  - Method `.__init__(db, library, store, copies, now)`
  - Method `.move(profile, sha256)` - *Move one person's copy to trash and forget it in the catalog; returns the trash id.*
  - Method `.listing(profile)`
  - Method `.restore(profile, ident)` - *Re-ingest the trashed bytes; the normal hash-verified path places them again.*
  - Method `.delete(profile, ident)`
  - Method `.empty(profile)`
  - Method `._owned(profile, ident)`
  - Method `._forget_file(item, path)`

---

### [`photo_harbor/trash_api.py`](photo_harbor/trash_api.py)
> *Endpoints for the per-person trash: list, move, restore, delete and empty.*

**Size**: `47` lines (`2170` bytes)

**Classes:**
- `class TrashApi`
  - Method `.__init__(trash, catalog)`
  - Method `.listing(request)`
  - Method `.move(request)`
  - Method `.update(request, ident)`
  - Method `.empty(request)`

**Functions:**
- `def _item_json(item)`

---

### [`tests/__init__.py`](tests/__init__.py)
**Size**: `0` lines (`0` bytes)

---

### [`tests/library_fixture.py`](tests/library_fixture.py)
> *A throwaway library for tests: temp folder, database, catalog, journal and store.*

**Size**: `38` lines (`1426` bytes)

**Classes:**
- `class Library`
  - Method `.__init__(test_case)`
  - Method `.put(data, name, taken)`

**Functions:**
- `def sha(data)`

---

### [`tests/test_albums.py`](tests/test_albums.py)
**Size**: `112` lines (`6004` bytes)

**Classes:**
- `class AlbumBookTest`
  - Method `.setUp()`
  - Method `.test_an_album_holds_photos_without_moving_any_file()`
  - Method `.test_favorites_are_private_to_the_person_who_marked_them()`
  - Method `.test_album_names_are_cleaned_and_unique_per_person()`
  - Method `.test_a_person_cannot_touch_another_persons_album()`
  - Method `.test_bulk_membership_and_favorites_change_each_row_once()`
  - Method `.test_renaming_and_deleting_an_album_keeps_its_photos()`
- `class CollectionMigrationTest`
  - Method `.test_a_format_4_catalog_gains_collections_and_keeps_its_photos()`
  - Method `.test_a_bad_collection_id_is_a_clear_error()`

---

### [`tests/test_dates.py`](tests/test_dates.py)
**Size**: `31` lines (`1444` bytes)

**Classes:**
- `class DateFilterTest`
  - Method `.setUp()`
  - Method `.names(narrow)`
  - Method `.test_an_inclusive_range_selects_days_on_both_ends()`
  - Method `.test_either_end_can_stand_alone()`
  - Method `.test_dates_combine_with_the_existing_narrowing()`

---

### [`tests/test_details.py`](tests/test_details.py)
**Size**: `62` lines (`2558` bytes)

**Classes:**
- `class DetailsTest`
  - Method `.setUp()`
  - Method `.test_file_facts_survive_an_unreadable_image()`
  - Method `.test_a_video_has_no_image_facts()`
  - Method `.test_pillow_reads_dimensions_and_camera_tags()`

**Functions:**
- `def record_for(path, name, media_type)`

---

### [`tests/test_downloads.py`](tests/test_downloads.py)
**Size**: `67` lines (`3062` bytes)

**Classes:**
- `class DownloadsTest`
  - Method `.setUp()`
  - Method `.photo(data, name)`
  - Method `.test_a_selection_becomes_one_zip_with_original_names()`
  - Method `.test_duplicate_names_get_a_hash_prefix()`
  - Method `.test_a_token_expires_and_removes_its_file()`
  - Method `.test_a_token_belongs_to_the_person_who_prepared_it()`
  - Method `.test_an_empty_download_is_refused()`

---

### [`tests/test_folders.py`](tests/test_folders.py)
> *The library as people see it in File Explorer, and Harbor keeping up with changes made there.*

**Size**: `144` lines (`6578` bytes)

**Classes:**
- `class _NoPreviews`
  - Method `.preview(record, original)`
- `class _NoRegistry`
  - Method `.read()`
- `class LayoutTest`
  - Method `.test_photos_go_to_person_year_month_folders_with_a_guide()`
  - Method `.test_a_shared_photo_is_in_both_folders_but_stored_once()`
  - Method `.test_has_links_a_photo_the_pc_already_has_into_the_askers_folder()`
  - Method `.test_renaming_a_person_renames_their_folder_and_keeps_every_path()`
  - Method `.test_files_from_the_old_layout_move_into_place()`
- `class ScannerTest`
  - Method `.test_files_added_moved_and_deleted_in_explorer_are_noticed()`
  - Method `.test_a_vanished_drive_removes_nothing()`
  - Method `.test_the_file_check_reports_damage_without_deleting()`

**Functions:**
- `def make_app(test_case, root)`
- `def put(app, data, name, profile, taken)`

---

### [`tests/test_http.py`](tests/test_http.py)
> *The server over a real socket on 127.0.0.1, as the Shortcut and the gallery use it.*

**Size**: `556` lines (`31232` bytes)

**Classes:**
- `class _NoPreviews`
  - Method `.preview(record, original)`
- `class _FakeRunKey`
  - Method `.__init__()`
  - Method `.read()`
  - Method `.write(command)`
  - Method `.delete()`
- `class ServerTest`
  - Method `.setUp()`
  - Method `.call(method, path, body, headers, key)`
  - Method `.upload(data, name, digest)`
  - Method `.test_a_full_sync_round()`
  - Method `.test_has_answers_yes_only_for_verified_photos()`
  - Method `.test_a_mismatched_hash_is_rejected_and_counted()`
  - Method `.test_calls_without_the_key_are_refused_but_the_page_loads()`
  - Method `.test_login_sets_a_cookie_that_opens_the_api()`
  - Method `.test_photo_details_are_visible_only_with_the_photo()`
  - Method `.test_a_selection_and_an_album_download_as_one_zip()`
  - Method `.test_trash_moves_restores_and_deletes()`
  - Method `.test_trash_never_crosses_people()`
  - Method `.test_sort_order_changes_the_page()`
  - Method `.test_a_date_range_narrows_the_gallery()`
  - Method `.test_storage_report_follows_the_signed_in_person()`
  - Method `.test_media_serves_ranges_for_video_scrubbing()`
  - Method `.test_photos_lists_newest_first_with_paging()`
  - Method `.test_a_chunked_upload_is_accepted()`
  - Method `.test_browsing_by_month_kind_and_name()`
  - Method `.test_a_browser_upload_needs_no_hash_and_keeps_a_non_ascii_name()`
  - Method `.test_a_non_media_upload_downloads_instead_of_rendering()`
  - Method `.test_a_second_server_cannot_share_the_port()`
  - Method `.add_person(name)`
  - Method `.test_a_persons_key_uploads_into_their_own_profile()`
  - Method `.test_only_the_owner_may_target_or_manage_other_profiles()`
  - Method `.test_a_retired_key_is_refused()`
  - Method `.test_a_client_hanging_up_prints_no_traceback()`
  - Method `.test_the_owner_can_turn_starting_with_windows_on_and_off()`
  - Method `.sign_in(profile, password)`
  - Method `.test_people_sign_in_with_a_password_and_see_only_their_own_photos()`
  - Method `.test_wrong_passwords_are_refused_then_braked()`
  - Method `.test_changing_a_password_needs_the_current_one_and_signs_out_other_browsers()`
  - Method `.test_last_day_counts_follow_the_signed_in_person()`
  - Method `.test_the_owner_can_reset_a_password_and_a_key_still_signs_in()`
  - Method `.test_albums_and_favorites_page_the_photos_they_hold()`
  - Method `.test_bulk_selection_writes_a_validated_batch()`
  - Method `.test_albums_and_favorites_never_cross_people()`

---

### [`tests/test_naming.py`](tests/test_naming.py)
**Size**: `38` lines (`1391` bytes)

**Classes:**
- `class SafeNameTest`
  - Method `.test_keeps_an_ordinary_name_and_lowercases_the_extension()`
  - Method `.test_strips_directories_from_either_separator()`
  - Method `.test_replaces_characters_windows_forbids()`
  - Method `.test_prefixes_reserved_device_names()`
  - Method `.test_falls_back_when_nothing_is_left()`
- `class ParseTakenTest`
  - Method `.test_reads_shortcuts_iso_with_zulu()`
  - Method `.test_unreadable_text_is_unknown()`
  - Method `.test_month_folder_is_zero_padded()`
- `class MediaTypeTest`
  - Method `.test_knows_iphone_formats()`

---

### [`tests/test_parts.py`](tests/test_parts.py)
**Size**: `159` lines (`6641` bytes)

**Classes:**
- `class RangeTest`
  - Method `.test_closed_open_and_suffix_ranges()`
  - Method `.test_unsatisfiable_or_multiple_ranges_mean_the_whole_file()`
- `class BodyReaderTest`
  - Method `.test_length_reader_stops_at_the_length()`
  - Method `.test_chunked_reader_decodes_and_consumes_the_trailer()`
  - Method `.test_json_body_must_be_an_object()`
- `class RouterTest`
  - Method `.test_exact_and_prefix_routes()`
- `class HomeNetworkTest`
  - Method `.test_private_addresses_are_home()`
  - Method `.test_public_addresses_are_not()`
- `class ConfigTest`
  - Method `.test_first_run_creates_a_key_that_later_runs_reuse()`
  - Method `.test_a_damaged_file_is_restored_from_its_backup()`
  - Method `.test_an_unknown_version_is_refused_without_touching_the_file()`
- `class BackupTest`
  - Method `.test_copies_new_files_and_skips_ones_already_there()`
  - Method `.test_refuses_a_target_inside_the_library()`
  - Method `.test_verify_hashes_every_copy_and_reports_damage()`
  - Method `.test_verify_refuses_a_target_that_is_not_there()`
- `class ThumbnailerTest`
  - Method `.test_without_pillow_previews_are_off()`
- `class DamagedConfigTest`
  - Method `.test_both_copies_damaged_is_a_clear_error()`

**Functions:**
- `def temp_dir(test_case)`

---

### [`tests/test_profiles.py`](tests/test_profiles.py)
**Size**: `149` lines (`7523` bytes)

**Classes:**
- `class ProfileBookTest`
  - Method `.setUp()`
  - Method `.test_the_owner_profile_holds_the_library_key()`
  - Method `.test_a_new_library_key_reaches_the_owner_profile()`
  - Method `.test_ids_are_folder_safe_and_unique()`
  - Method `.test_a_new_key_retires_the_old_one()`
- `class MigrationTest`
  - Method `.test_a_format_1_catalog_is_upgraded_and_owned_by_main()`
  - Method `.test_a_format_2_catalog_gains_the_import_list()`
- `class ProfileStorageTest`
  - Method `.test_photos_land_in_their_profile_and_filter_by_it()`
  - Method `.test_last_sync_is_kept_per_profile()`
  - Method `.test_last_day_counts_are_kept_per_profile()`
- `class ImportTest`
  - Method `.setUp()`
  - Method `.test_finds_media_only_and_skips_hidden_folders()`
  - Method `.test_imports_into_a_profile_once_and_leaves_the_source_alone()`
  - Method `.test_refuses_a_folder_inside_the_library()`

---

### [`tests/test_runner.py`](tests/test_runner.py)
> *The background server the Harbor window and `serve` use, and the window's saved settings.*

**Size**: `58` lines (`2353` bytes)

**Classes:**
- `class RunnerTest`
  - Method `.setUp()`
  - Method `.test_start_serves_and_stop_frees_everything()`
  - Method `.test_a_busy_port_is_a_clear_error()`
- `class PrefsTest`
  - Method `.test_round_trip_and_fallbacks()`
  - Method `.test_mask_shows_only_the_last_four()`

---

### [`tests/test_scale.py`](tests/test_scale.py)
> *Starting with Windows, and the pieces that keep large libraries fast.*

**Size**: `172` lines (`6197` bytes)

**Classes:**
- `class _FakeRunKey`
  - Method `.__init__()`
  - Method `.read()`
  - Method `.write(command)`
  - Method `.delete()`
- `class AutostartTest`
  - Method `.test_the_command_runs_the_launcher_windowless_at_startup()`
  - Method `.test_on_and_off()`
  - Method `.test_other_systems_say_so()`
- `class ImportLedgerTest`
  - Method `.setUp()`
  - Method `.reads()` - *Run an import and return how many source files were actually opened.*
  - Method `.test_unchanged_files_are_not_read_again()`
  - Method `.test_a_changed_file_or_a_lost_copy_is_read_again()`
- `class _CountingThumbs`
  - Method `.__init__()`
  - Method `.preview(record, original)`
- `class WarmerTest`
  - Method `.test_backfills_old_photos_and_takes_new_ones_skipping_videos()`
- `class ImportForAnotherPersonTest`
  - Method `.test_a_folder_imported_for_one_person_still_reaches_the_next()`
- `class ScanScheduleTest`
  - Method `.test_a_failing_pass_is_logged_and_the_thread_keeps_going()`
- `class SessionCleanupTest`
  - Method `.test_expired_sessions_are_removed()`

---

### [`tests/test_sort.py`](tests/test_sort.py)
**Size**: `26` lines (`1135` bytes)

**Classes:**
- `class SortOrderTest`
  - Method `.setUp()`
  - Method `.names(order)`
  - Method `.test_each_order_is_stable_and_complete()`
  - Method `.test_an_unknown_order_falls_back_to_newest()`

---

### [`tests/test_storage.py`](tests/test_storage.py)
**Size**: `31` lines (`1537` bytes)

**Classes:**
- `class StorageReportTest`
  - Method `.setUp()`
  - Method `.test_the_whole_library_counts_each_photo_once_and_flags_sharing()`
  - Method `.test_one_persons_share_uses_their_own_name_and_bytes()`

---

### [`tests/test_store.py`](tests/test_store.py)
**Size**: `154` lines (`6943` bytes)

**Classes:**
- `class IngestTest`
  - Method `.setUp()`
  - Method `.test_stores_under_the_month_it_was_taken()`
  - Method `.test_same_bytes_twice_is_a_duplicate_and_keeps_one_file()`
  - Method `.test_a_name_clash_with_different_bytes_gets_a_hash_suffix()`
  - Method `.test_hash_mismatch_keeps_nothing()`
  - Method `.test_a_short_body_is_refused_and_leaves_no_temp_file()`
  - Method `.test_a_malformed_hash_is_a_usage_error()`
- `class VerifyTest`
  - Method `.setUp()`
  - Method `.test_an_intact_file_verifies()`
  - Method `.test_an_unknown_hash_does_not()`
  - Method `.test_a_changed_file_does_not()`
  - Method `.test_a_deleted_file_does_not()`
- `class CatalogAndJournalTest`
  - Method `.setUp()`
  - Method `.test_page_is_newest_taken_first()`
  - Method `.test_missing_report_clears_once_the_photo_arrives()`
  - Method `.test_last_sync_and_counts()`
  - Method `.test_an_unknown_catalog_version_is_refused_untouched()`
- `class SearchEscapingTest`
  - Method `.test_wildcards_in_a_search_are_literal()`
- `class EmbeddedDateTest`
  - Method `.test_the_file_date_is_used_when_the_phone_sends_none()`
- `class RepairAndNamingTest`
  - Method `.setUp()`
  - Method `.test_resending_a_photo_whose_pc_copy_vanished_restores_it()`
  - Method `.test_resending_over_a_damaged_copy_restores_it()`
  - Method `.test_a_name_held_by_a_catalogued_but_missing_file_is_not_reused()`
  - Method `.test_a_connection_error_mid_upload_is_a_clear_failure()`

---

### [`tests/test_trash.py`](tests/test_trash.py)
**Size**: `73` lines (`3538` bytes)

**Classes:**
- `class TrashBookTest`
  - Method `.setUp()`
  - Method `.test_a_copy_moves_to_trash_and_restores_its_bytes()`
  - Method `.test_a_shared_photo_stays_for_the_other_person()`
  - Method `.test_permanent_delete_and_empty_remove_the_files()`
  - Method `.test_another_person_cannot_restore_or_delete_the_entry()`
- `class TrashMigrationTest`
  - Method `.test_a_format_5_catalog_gains_the_trash_table()`

---
