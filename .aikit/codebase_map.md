# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `83`
- **Total Classes**: `169`
- **Total Top-Level Functions**: `125`
- **Total Class Methods**: `673`
- **Total Source Lines**: `11030`

---

## 📦 Modules & Exported Symbols

### [`android/build.py`](android/build.py)
> *Build a signed debug APK with the Android SDK tools; no Gradle or runtime libraries.*

**Size**: `129` lines (`5091` bytes)

**Functions:**
- `def find_sdk()`
- `def find_java()`
- `def run(command, env, cwd)`
- `def main()`

---

### [`photo_harbor/__init__.py`](photo_harbor/__init__.py)
> *photo-harbor: a self-hosted photo server that an iPhone feeds through Apple Shortcuts.*

**Size**: `3` lines (`116` bytes)

---

### [`photo_harbor/__main__.py`](photo_harbor/__main__.py)
> *Command line: ``python -m photo_harbor serve | panel | key | profiles | import | backup``.*

**Size**: `148` lines (`6411` bytes)

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

**Size**: `161` lines (`6519` bytes)

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
  - Method `.reset()` - *An owner set a password: guessing protection restarts for every address.*

**Functions:**
- `def hash_password(password, iterations, salt)` - *``pbkdf2_sha256$<iterations>$<salt>$<hash>``: the password itself is never stored.*
- `def password_matches(password, stored)`
- `def check_new_password(password)`
- `def _token_hash(token)`
- `def _stamp(moment)`

---

### [`photo_harbor/activity_api.py`](photo_harbor/activity_api.py)
> *Read-only recent journal events for the Activity view.*

**Size**: `25` lines (`934` bytes)

**Classes:**
- `class ActivityApi`
  - Method `.__init__(journal)`
  - Method `.listing(request)`

---

### [`photo_harbor/albums.py`](photo_harbor/albums.py)
> *Personal albums and favorites: named collections that never move or copy a file.*

**Size**: `207` lines (`9693` bytes)

**Classes:**
- `class AlbumBook` - *Albums belong to one person; favorites are that person's own mark on a photo.*
  - Method `.__init__(db, now)`
  - Method `.summary(profile)` - *``(favorite count, [Album, ...])`` for the signed-in person, names in A-Z order.*
  - Method `.create(profile, name)`
  - Method `.rename(profile, ident, name)`
  - Method `.set_cover(profile, ident, sha256)` - *Pick a visible member as the album cover; an empty value returns to newest.*
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

**Size**: `66` lines (`2932` bytes)

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

**Size**: `253` lines (`12572` bytes)

**Classes:**
- `class HarborApp` - *Owns the database connection; ``close`` releases it.*
  - Method `.__init__(settings, port, thumbs, now, autostart, password_iterations, android_dir)`
  - Method `.android_page(request)`
  - Method `.android_apk(request)`
  - Method `.service_worker(request)`
  - Method `.android_apk_info(request)`
  - Method `.android_metadata(request)` - *The gallery's APK card: built state plus the signed build's sidecar fields.*
  - Method `.android_script(request)`
  - Method `.android_style(request)`
  - Method `._register(sync, library, people, albums, archive, tags, similar, sidecar, folders, activity, downloads, trash, backup, setup)`
  - Method `.close()`

**Functions:**
- `def static_file(request, name)`

---

### [`photo_harbor/archive.py`](photo_harbor/archive.py)
> *Per-person archive: hide a photo from the timeline without moving or copying it.*

**Size**: `34` lines (`1349` bytes)

**Classes:**
- `class ArchiveBook`
  - Method `.__init__(db, now)`
  - Method `.set(profile, sha256, archived)`
  - Method `.set_many(profile, sha256s, archived)` - *Archive or restore several photos in one lock; returns how many rows changed.*

---

### [`photo_harbor/archive_api.py`](photo_harbor/archive_api.py)
> *Endpoint for the per-person archive: hide or restore a validated batch.*

**Size**: `23` lines (`952` bytes)

**Classes:**
- `class ArchiveApi`
  - Method `.__init__(archive, catalog)`
  - Method `.update(request)`

---

### [`photo_harbor/atomic_file.py`](photo_harbor/atomic_file.py)
> *Crash-safe file placement: temp file, fsync, atomic replace, directory fsync, and exclusive*

**Size**: `81` lines (`2721` bytes)

**Functions:**
- `def write_atomic(path, data, keep_backup)` - *Replace ``path`` with ``data`` so a power cut leaves the old or the new file, never half.*
- `def replace_with_retry(src, dst)` - *os.replace, retried because Windows briefly locks files that a scanner has open.*
- `def copy_exclusive(source, target)` - *Copy ``source`` to ``target`` only when that name is free; a failed copy leaves nothing.*
- `def place_exclusive(source, target)` - *Give ``target`` the bytes of ``source`` only when the name is free, then remove ``source``.*
- `def fsync_dir(directory)` - *Persist a directory entry; Windows cannot open a directory, and NTFS journals it anyway.*

---

### [`photo_harbor/auth.py`](photo_harbor/auth.py)
> *Who is asking: a phone's Shortcut presents its key; a browser signs in with a name and password.*

**Size**: `105` lines (`5019` bytes)

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

**Size**: `187` lines (`6394` bytes)

**Classes:**
- `class BackupReport`
- `class VerifyReport`
  - Property `.ok`
- `class BackupStatus`
- `class DailyBackup` - *Mirrors at start-up and every 24 hours on a background thread while the server runs.*
  - Method `.__init__(source, target, log)`
  - Method `.start()`
  - Method `.stop()`
  - Method `.status()`
  - Method `.run_once()`
  - Method `._run()`

**Functions:**
- `def _refuse_inside(source, target)`
- `def _require_source(source)`
- `def _files(root)` - *Every visible file below ``root``, skipping Harbor's dot folders.*
- `def _digest(path)`
- `def verify(source, target)` - *Re-hash every source original against its backup copy; extras there are reported only.*
- `def mirror(source, target)` - *Copy each original missing from ``target`` or differing in size; never deletes there.*

---

### [`photo_harbor/backup_api.py`](photo_harbor/backup_api.py)
> *Owner-only view of the daily mirror: target, last attempt and result.*

**Size**: `31` lines (`1111` bytes)

**Classes:**
- `class BackupApi`
  - Method `.__init__(backup)`
  - Method `.status(request)`

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

**Size**: `412` lines (`21499` bytes)

**Classes:**
- `class Catalog`
  - Method `.__init__(db)`
  - Method `.add(record)` - *Insert ``record``; False when its hash is already catalogued. A path another record*
  - Method `.get(sha256)`
  - Method `.known(sha256s)` - *The hashes in ``sha256s`` that the catalog holds, in one query.*
  - Method `.stored_hashes()` - *Every hash still in the catalog; the preview cache keeps only these.*
  - Method `.copies_of(profile, sha256s)` - *The hashes in ``sha256s`` that sit in ``profile``'s folder, in one query.*
  - Method `.page(offset, limit, narrow)` - *Records in the requested order, newest first by default (taken time, then received).*
  - Method `.hashes(narrow, limit)` - *Every matching hash in the same order as the gallery, capped by ``limit``.*
  - Method `.similar_status(profile, viewer)` - *How many visible photos are hashed, skipped, ungrouped or missing a hash.*
  - Method `.missing_hashes(profile, viewer, limit)` - *Visible photo hashes that have no perceptual-hash row yet, newest first.*
  - Method `.set_hash(sha256, dhash)` - *Cache one perceptual hash or the ``skip`` marker; groups wait for a rebuild.*
  - Method `.rebuild_groups(radius)` - *Recompute cached radius groups from every valid hash; returns hash groups.*
  - Method `.similar_groups(profile, viewer, limit)` - *Read-only cached groups of visible photos.*
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

**Size**: `569` lines (`27260` bytes)

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

**Size**: `75` lines (`3834` bytes)

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

**Size**: `334` lines (`11820` bytes)

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

**Size**: `133` lines (`4122` bytes)

**Functions:**
- `def _text(value)`
- `def _exposure(value)`
- `def _aperture(value)`
- `def _focal(value)`
- `def _iso(value)`
- `def _camera(make, model)`
- `def read_camera(path)` - *``(camera, lens)`` from EXIF, or ``(None, None)`` without Pillow or readable tags.*
- `def read_details(record, path)` - *File facts always; width, height and EXIF fields when Pillow can read them.*

---

### [`photo_harbor/downloads.py`](photo_harbor/downloads.py)
> *One-off ZIP archives for a selection or album, with expiring one-time tokens.*

**Size**: `132` lines (`5396` bytes)

**Classes:**
- `class Downloads` - *Builds stored ZIPs in the library's state directory; tokens live in memory.*
  - Method `.__init__(state_dir, clock)`
  - Method `.clean()` - *Startup cleanup: no token survives a restart, so an abandoned archive older than an*
  - Method `.prepare(entries, name, profile)` - *Write ``[(PhotoRecord, path), ...]`` to a new ZIP and return its token details.*
  - Method `.take(token, profile)` - *The ``(path, name, bytes)`` for this person's live token, removing it.*
  - Method `._expire_locked()`

**Functions:**
- `def _entry_key(name)` - *One key for names a case- or normalization-insensitive filesystem would merge.*
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

### [`photo_harbor/folders_api.py`](photo_harbor/folders_api.py)
> *Read-only folder tree from the per-person year/month library layout.*

**Size**: `30` lines (`1139` bytes)

**Classes:**
- `class FoldersApi`
  - Method `.__init__(profiles, catalog)`
  - Method `.listing(request)`

---

### [`photo_harbor/geo.py`](photo_harbor/geo.py)
> *The camera's GPS point, read once at ingest for the Places rail.*

**Size**: `60` lines (`1905` bytes)

**Functions:**
- `def _number(value)`
- `def _degrees(value)` - *A GPS coordinate written as three rational degrees/minutes/seconds.*
- `def _point(gps)`
- `def read_place(path)` - *``(latitude, longitude)`` from EXIF GPS, or None without Pillow or a valid point.*

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

**Size**: `79` lines (`3725` bytes)

**Classes:**
- `class SyncJournal`
  - Method `.__init__(db)`
  - Method `.record(at, kind, sha256, detail, profile)`
  - Method `.last_sync(profile)` - *The start time of the latest finished sync, for one profile or (None) anyone.*
  - Method `.last_event(kind)` - *When the latest event of ``kind`` was recorded.*
  - Method `.recent(limit, profile)` - *Newest journal events, for everyone or one person; old profile-less events are main.*
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

**Size**: `264` lines (`12738` bytes)

**Classes:**
- `class LibraryApi`
  - Method `.__init__(store, catalog, journal, thumbs, albums, tags, now)`
  - Method `.status(request)`
  - Method `.hashes(request)` - *Every matching hash for Select matching, in the gallery's order.*
  - Method `.storage(request)` - *Counts, bytes, per-person shares and the largest files the caller may see.*
  - Method `.photos(request)`
  - Method `.outline(request)` - *Months with photos, newest first, for the browser sidebar.*
  - Method `._disk()`
  - Method `.details(request, sha256)`
  - Method `.media(request, sha256)`
  - Method `.thumb(request, sha256)`

**Functions:**
- `def _valid_date(value)` - *Shape plus a real calendar day: 2026-02-30 and 2025-02-29 fail.*
- `def _valid_day(value)` - *A month-day anniversary; 02-29 is allowed because leap years exist.*
- `def _not_found(sha256)`
- `def _displayable(kind)` - *Images and videos show inline; anything else (HTML, SVG with scripts) only downloads.*
- `def photo_json(record)`
- `def _profile_arg(request)`
- `def _visible_profile(request)` - *The owner may look at anyone (or, with no ?profile=, everyone); others see only*
- `def _narrowing(request, albums, tags)`

---

### [`photo_harbor/messages.py`](photo_harbor/messages.py)
> *Transport-free request and reply values, so the API can be tested without sockets.*

**Size**: `115` lines (`4079` bytes)

**Classes:**
- `class Request`
  - Property `.profile` - *The caller's profile id; the owner's when the route is public.*
  - Property `.owner`
  - Method `.header(name, default)`
  - Method `.arg(name, default)`
  - Method `.json()` - *The body as a JSON object, or HarborError for anything else.*
- `class Reply`

**Functions:**
- `def _read_body(body, limit)` - *Read up to ``limit`` bytes plus one, even when a chunked stream stops at every chunk.*
- `def json_reply(data, status, headers)`
- `def error_reply(error)`
- `def parse_range(value, size)` - *``(first, last)`` for one satisfiable ``bytes=`` range, else None for the whole file.*

---

### [`photo_harbor/naming.py`](photo_harbor/naming.py)
> *Where an original lands on disk: <Person>/<YYYY>/<YYYY-MM>/<safe file name>.*

**Size**: `63` lines (`2267` bytes)

**Functions:**
- `def safe_name(original)` - *A Windows-safe base name; a name that sanitises to nothing becomes ``photo``.*
- `def parse_taken(value)` - *ISO 8601 as Shortcuts formats it; anything unreadable counts as unknown.*
- `def month_folder(moment)` - *``2026/2026-10``: the year to browse by, then a month folder that sorts and reads alone.*
- `def folder_name(name)` - *A person's folder as they would name it, made safe for Windows: ``Ayşe`` stays ``Ayşe``.*
- `def media_type(name)`

---

### [`photo_harbor/phash.py`](photo_harbor/phash.py)
> *A small perceptual difference hash for the read-only Similar review.*

**Size**: `114` lines (`3830` bytes)

**Functions:**
- `def hash_pixels(pixels)` - *A 64-bit difference hash as 16 hex digits, or None for the wrong pixel count.*
- `def hamming(left, right)` - *How many bits differ between two 16-hex perceptual hashes.*
- `def _bands(radius)` - *Split 64 bits into more than ``radius`` bands, so a pair within radius shares one band.*
- `def hash_bands(dhash, radius)` - *``(band, signature)`` keys for the cached radius-8 candidate index.*
- `def hash_components(hashes, radius)` - *Connected groups of valid hashes whose bits differ by at most ``radius``.*
- `def read_dhash(path)` - *Perceptual hash from the original, or None without Pillow or a readable image.*

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

**Size**: `88` lines (`4111` bytes)

**Classes:**
- `class ProfilesApi`
  - Method `.__init__(book, catalog, journal, passwords, sessions, layout, brake)`
  - Method `.listing(request)` - *The owner sees everyone; anyone else sees only themselves (with their own key).*
  - Method `.create(request)`
  - Method `.update(request, ident)` - *JSON ``{"name": "..."}`` renames (and renames their folder); ``{"new_key": true}``*

**Functions:**
- `def _require_owner(request)`

---

### [`photo_harbor/records.py`](photo_harbor/records.py)
> *Immutable values passed between the store, the catalog and the web layer.*

**Size**: `182` lines (`4515` bytes)

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
- `class Tag` - *One person's label; ``count`` is how many visible photos carry it.*
- `class PersonStorage` - *One person's share: shared photos count in each person's share.*
- `class StorageFile` - *One row of the largest-files list.*
- `class StorageReport` - *Disk use for one profile, or for the whole library when ``profile`` is None.*
- `class TrashItem` - *One recoverable removal; the bytes sit under ``.harbor/trash`` until restored or deleted.*
- `class Profile` - *A person: ``folder`` is their folder in the library, ``key`` is what their Shortcut sends.*
- `class Identity` - *Who a request comes from; the owner (library key) may manage every profile.*

---

### [`photo_harbor/router.py`](photo_harbor/router.py)
> *Maps a method and path to an endpoint; a path ending in ``/`` passes the rest as a parameter.*

**Size**: `36` lines (`1381` bytes)

**Classes:**
- `class Route`
- `class Router`
  - Method `.__init__()`
  - Method `.add(method, path, handler, public)`
  - Method `.add_exact(method, path, handler, public)` - *A path that ends in ``/`` but must still match exactly (a page, not a parameter).*
  - Method `.match(method, path)`

---

### [`photo_harbor/runner.py`](photo_harbor/runner.py)
> *Starts and stops one server in the background, for the command line and the Harbor window.*

**Size**: `98` lines (`3866` bytes)

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

**Size**: `241` lines (`10210` bytes)

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

**Size**: `52` lines (`2159` bytes)

**Classes:**
- `class SetupApi` - *The address and this PC's startup setting; each person's key comes from /api/profiles.*
  - Method `.__init__(port, autostart, address)`
  - Method `.details(request)`
  - Method `.startup(request)` - *Owner only: JSON ``{"enabled": true|false}`` turns starting with Windows on or off.*

**Functions:**
- `def lan_address()` - *The PC's address on the home network; connecting a UDP socket sends no packet.*

---

### [`photo_harbor/sidecar.py`](photo_harbor/sidecar.py)
> *Read-only JSON and XMP sidecars for selected photos; originals are never touched.*

**Size**: `139` lines (`5237` bytes)

**Classes:**
- `class SidecarApi`
  - Method `.__init__(catalog, tags)`
  - Method `.export(request)`

**Functions:**
- `def _entry_key(name)`
- `def _sidecar_name(record, suffix, used)`
- `def json_sidecar(record, tags)`
- `def _gps(value, positive, negative)`
- `def xmp_sidecar(record, tags)`
- `def sidecar_zip(entries, fmt)` - *Build a ZIP of JSON or XMP sidecars; ``entries`` are ``(record, tag names)`` pairs.*

---

### [`photo_harbor/similar_api.py`](photo_harbor/similar_api.py)
> *Read-only Similar review: perceptual hashes, no automatic deletion.*

**Size**: `71` lines (`3017` bytes)

**Classes:**
- `class SimilarApi`
  - Method `.__init__(catalog, store, dhash, builder)`
  - Method `._profile(request)`
  - Method `._status(request)`
  - Method `.listing(request)`
  - Method `.build(request)` - *Start the background group rebuild; the caller polls the listing.*
  - Method `.scan(request)`

---

### [`photo_harbor/similar_builder.py`](photo_harbor/similar_builder.py)
> *One background rebuild of the cached Similar groups.*

**Size**: `38` lines (`1268` bytes)

**Classes:**
- `class SimilarBuilder`
  - Method `.__init__(catalog, radius)`
  - Method `.start()` - *Start a rebuild unless one is already running; True when this call started it.*
  - Method `.running()`
  - Method `.error()`
  - Method `._run()`

---

### [`photo_harbor/store.py`](photo_harbor/store.py)
> *Receives originals, proves their bytes against the phone's hash, and re-proves them on request.*

**Size**: `363` lines (`16855` bytes)

**Classes:**
- `class PhotoStore`
  - Method `.__init__(library, catalog, copies, folder_of, now, embedded_date, embedded_place, embedded_camera, on_stored)` - *``folder_of`` maps a profile id to that person's folder name in the library.*
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

**Size**: `122` lines (`5977` bytes)

**Classes:**
- `class SyncApi`
  - Method `.__init__(store, journal, book, now)`
  - Method `.start(request)` - *Tell the phone which photos to send: those created after the last finished sync.*
  - Method `.upload(request)`
  - Method `.has(request)` - *``answer`` is ``yes`` only after the PC re-hashes its copy; with ``report=1`` (the*
  - Method `.done(request)`

**Functions:**
- `def _stamp(moment)`
- `def _comparable(moment, now)` - *Put a stored or phone timestamp and the PC clock into one timezone frame.*
- `def _target_profile(request, book)` - *A person's own profile; the owner may upload for anyone with ``X-Profile``.*

---

### [`photo_harbor/tags.py`](photo_harbor/tags.py)
> *Personal tags: named marks on photos that never move or copy a file.*

**Size**: `161` lines (`6971` bytes)

**Classes:**
- `class TagBook` - *Tags belong to one person; a tag marks a photo without touching its folder.*
  - Method `.__init__(db, now)`
  - Method `.summary(profile)` - *The person's tags and how many non-archived photos each one marks.*
  - Method `.create(profile, name)` - *Return the person's tag with this name, creating it once; matching is case-insensitive.*
  - Method `.rename(profile, ident, name)`
  - Method `.delete(profile, ident)`
  - Method `.owned(profile, ident)` - *Whether this person owns the tag; a bad id is a 400, a missing one is False.*
  - Method `.members(profile, sha256)` - *The ids of this person's tags on one photo.*
  - Method `.names(profile, sha256)` - *The names of this person's tags on one photo, A-Z.*
  - Method `.add(profile, ident, sha256, member)` - *Put a tag on a photo or take it off; True when the mark changed.*
  - Method `.add_many(profile, ident, sha256s, member)` - *Mark or unmark several photos in one lock; returns how many rows changed.*
  - Method `._owned(profile, tag)`

**Functions:**
- `def _clean_name(value)`
- `def _tag_id(value)`

---

### [`photo_harbor/tags_api.py`](photo_harbor/tags_api.py)
> *Endpoints for personal tags; every write stays inside the caller's profile.*

**Size**: `74` lines (`2973` bytes)

**Classes:**
- `class TagApi`
  - Method `.__init__(tags, catalog)`
  - Method `.listing(request)` - *Every tag and, when ?sha256= is present, whether it is on that photo.*
  - Method `.create(request)`
  - Method `.update(request, ident)`
  - Method `.membership(request)`

**Functions:**
- `def _flag(body, name)`
- `def _sha_arg(request)`

---

### [`photo_harbor/thumbs.py`](photo_harbor/thumbs.py)
> *Small JPEG previews, made only when the optional Pillow (and pillow-heif for HEIC) is installed.*

**Size**: `125` lines (`4757` bytes)

**Classes:**
- `class Thumbnailer`
  - Method `.__init__(cache_dir, pillow)`
  - Property `.enabled`
  - Method `.preview(record, original)` - *The cached preview, made on first request; None for videos or unreadable images.*
  - Method `.prune(live)` - *Delete previews whose photo is gone; they are disposable and remade on demand.*
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

**Size**: `135` lines (`6070` bytes)

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

**Size**: `52` lines (`2507` bytes)

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

**Size**: `40` lines (`1567` bytes)

**Classes:**
- `class Library`
  - Method `.__init__(test_case)`
  - Method `.put(data, name, taken)`

**Functions:**
- `def sha(data)`

---

### [`tests/test_activity.py`](tests/test_activity.py)
**Size**: `26` lines (`1187` bytes)

**Classes:**
- `class JournalRecentTest`
  - Method `.setUp()`
  - Method `.test_recent_events_are_newest_first_and_limit()`
  - Method `.test_one_person_sees_only_their_events()`

---

### [`tests/test_albums.py`](tests/test_albums.py)
**Size**: `162` lines (`8601` bytes)

**Classes:**
- `class AlbumBookTest`
  - Method `.setUp()`
  - Method `.test_an_album_holds_photos_without_moving_any_file()`
  - Method `.test_favorites_are_private_to_the_person_who_marked_them()`
  - Method `.test_album_names_are_cleaned_and_unique_per_person()`
  - Method `.test_a_person_cannot_touch_another_persons_album()`
  - Method `.test_a_chosen_cover_is_used_until_it_leaves_the_album()`
  - Method `.test_bulk_membership_and_favorites_change_each_row_once()`
  - Method `.test_renaming_and_deleting_an_album_keeps_its_photos()`
- `class CollectionMigrationTest`
  - Method `.test_a_format_4_catalog_gains_collections_and_keeps_its_photos()`
  - Method `.test_a_format_6_catalog_gains_the_album_cover_column()`
  - Method `.test_a_bad_collection_id_is_a_clear_error()`
  - Method `.test_a_non_integer_collection_id_is_a_clear_error()`
  - Method `.test_a_collection_id_beyond_sqlite_is_a_clear_error()`

---

### [`tests/test_archive.py`](tests/test_archive.py)
**Size**: `88` lines (`4804` bytes)

**Classes:**
- `class ArchiveBookTest`
  - Method `.setUp()`
  - Method `.test_archiving_hides_from_the_timeline_and_shows_in_the_archive()`
  - Method `.test_archiving_is_private_to_the_viewer()`
  - Method `.test_unarchiving_brings_the_photo_back()`
  - Method `.test_a_batch_changes_each_row_once()`
  - Method `.test_forgetting_a_copy_drops_its_archive_mark()`
- `class ArchiveMigrationTest`
  - Method `.test_a_format_7_catalog_gains_the_archive_table()`

---

### [`tests/test_cameras.py`](tests/test_cameras.py)
**Size**: `103` lines (`3783` bytes)

**Classes:**
- `class _Exif`
  - Method `.__init__(tags)`
  - Method `.get_ifd(number)`
  - Method `.get(number)`
- `class _Image`
  - Method `.__init__(tags)`
  - Method `.__enter__()`
  - Method `.__exit__(*args)`
  - Method `.getexif()`
- `class _ImageModule`
  - Method `.__init__(tags)`
  - Method `.open(path)`
- `class CameraTest`
  - Method `.test_make_model_and_lens_are_read_together()`
  - Method `.test_unreadable_or_missing_exif_is_empty()`
- `class CameraFilterTest`
  - Method `.setUp()`
  - Method `._add(data, name, camera)`
  - Method `.test_a_camera_filters_and_lists_the_rail()`
  - Method `.test_archiving_removes_the_camera_count()`
- `class CameraMigrationTest`
  - Method `.test_a_format_10_catalog_gains_the_camera_columns()`

---

### [`tests/test_dates.py`](tests/test_dates.py)
**Size**: `39` lines (`1945` bytes)

**Classes:**
- `class DateFilterTest`
  - Method `.setUp()`
  - Method `.names(narrow)`
  - Method `.test_an_inclusive_range_selects_days_on_both_ends()`
  - Method `.test_either_end_can_stand_alone()`
  - Method `.test_dates_combine_with_the_existing_narrowing()`
  - Method `.test_a_month_day_matches_anniversaries()`

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
**Size**: `149` lines (`6923` bytes)

**Classes:**
- `class DownloadsTest`
  - Method `.setUp()`
  - Method `.test_startup_keeps_a_fresh_archive_and_drops_a_stale_one()`
  - Method `.test_a_vanished_archive_is_not_taken()`
  - Method `.photo(data, name)`
  - Method `.test_a_selection_becomes_one_zip_with_original_names()`
  - Method `.test_a_third_collision_still_gets_a_unique_name()`
  - Method `.test_many_collisions_stay_unique_with_a_counter()`
  - Method `.test_duplicate_names_get_a_hash_prefix()`
  - Method `.test_names_that_differ_only_by_case_do_not_collide_on_windows()`
  - Method `.test_names_that_differ_only_by_unicode_form_do_not_collide()`
  - Method `.test_a_token_expires_and_removes_its_file()`
  - Method `.test_a_token_belongs_to_the_person_who_prepared_it()`
  - Method `.test_an_empty_download_is_refused()`
  - Method `.test_a_file_vanishing_mid_zip_is_a_404()`

---

### [`tests/test_folder_view.py`](tests/test_folder_view.py)
**Size**: `44` lines (`2174` bytes)

**Classes:**
- `class FoldersApiTest`
  - Method `.setUp()`
  - Method `._request(profile, owner)`
  - Method `.test_owner_sees_both_people_with_real_paths()`
  - Method `.test_another_person_sees_only_their_folder()`
  - Method `.test_archived_photos_leave_the_folder_tree()`

---

### [`tests/test_folders.py`](tests/test_folders.py)
> *The library as people see it in File Explorer, and Harbor keeping up with changes made there.*

**Size**: `187` lines (`8654` bytes)

**Classes:**
- `class _NoPreviews`
  - Method `.preview(record, original)`
- `class _NoRegistry`
  - Method `.read()`
- `class PreviewCacheTest`
  - Method `.test_startup_drops_previews_of_photos_that_are_gone()`
- `class LayoutTest`
  - Method `.test_photos_go_to_person_year_month_folders_with_a_guide()`
  - Method `.test_a_shared_photo_is_in_both_folders_but_stored_once()`
  - Method `.test_has_links_a_photo_the_pc_already_has_into_the_askers_folder()`
  - Method `.test_renaming_a_person_renames_their_folder_and_keeps_every_path()`
  - Method `.test_files_from_the_old_layout_move_into_place()`
- `class ScannerTest`
  - Method `.test_files_added_moved_and_deleted_in_explorer_are_noticed()`
  - Method `.test_a_vanished_drive_removes_nothing()`
  - Method `.test_drive_loss_with_fewer_than_50_files_removes_nothing()`
  - Method `.test_single_delete_in_small_library_still_allowed()`
  - Method `.test_the_file_check_reports_damage_without_deleting()`

**Functions:**
- `def make_app(test_case, root)`
- `def put(app, data, name, profile, taken)`

---

### [`tests/test_hashes.py`](tests/test_hashes.py)
**Size**: `45` lines (`2167` bytes)

**Classes:**
- `class HashSelectionTest`
  - Method `.setUp()`
  - Method `.test_hashes_follow_the_same_filter_and_order_as_the_page()`
  - Method `.test_a_limit_caps_the_result()`
  - Method `.test_negative_limit_is_rejected()`
  - Method `.test_unknown_kind_is_rejected_not_silently_ignored()`
  - Method `.test_known_and_copies_of_chunk_large_batches()`

---

### [`tests/test_http.py`](tests/test_http.py)
> *The server over a real socket on 127.0.0.1, as the Shortcut and the gallery use it.*

**Size**: `1061` lines (`59774` bytes)

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
  - Method `.test_keep_alive_serves_two_requests_on_one_connection()`
  - Method `.test_a_full_sync_round()`
  - Method `.test_has_answers_yes_only_for_verified_photos()`
  - Method `.test_a_mismatched_hash_is_rejected_and_counted()`
  - Method `.test_a_huge_page_offset_is_a_clear_400()`
  - Method `.test_a_huge_album_id_is_a_clear_400()`
  - Method `.test_a_chunked_json_login_is_accepted()`
  - Method `.test_json_answers_are_never_browser_cached()`
  - Method `.test_the_gallery_is_installable_as_a_pwa()`
  - Method `.test_android_page_and_apk_are_public()`
  - Method `.test_calls_without_the_key_are_refused_but_the_page_loads()`
  - Method `.test_login_sets_a_cookie_that_opens_the_api()`
  - Method `.test_photo_details_are_visible_only_with_the_photo()`
  - Method `.test_an_album_can_choose_its_cover()`
  - Method `.test_a_selection_and_an_album_download_as_one_zip()`
  - Method `.test_trash_moves_restores_and_deletes()`
  - Method `.test_trash_never_crosses_people()`
  - Method `.test_hashes_match_the_filters_for_select_matching()`
  - Method `.test_sort_order_changes_the_page()`
  - Method `.test_a_date_range_narrows_the_gallery()`
  - Method `.test_a_month_day_matches_each_year()`
  - Method `.test_archive_hides_restores_and_stays_out_of_the_timeline()`
  - Method `.test_tags_are_personal_and_filter_the_gallery()`
  - Method `.test_places_group_and_filter_a_gps_point()`
  - Method `.test_camera_metadata_groups_and_filters()`
  - Method `.test_similar_review_groups_hashes_without_deleting()`
  - Method `.test_sidecar_export_is_a_read_only_zip()`
  - Method `.test_lens_metadata_groups_and_filters()`
  - Method `.test_folder_tree_follows_people_visibility()`
  - Method `.test_timeline_outline_has_months_and_counts()`
  - Method `.test_explore_outline_has_every_statistic_section()`
  - Method `.test_albums_overview_has_cover_and_count()`
  - Method `.test_tags_overview_has_name_and_count()`
  - Method `.test_people_overview_has_counts_folders_and_last_sync()`
  - Method `.test_activity_journal_is_recent_and_private()`
  - Method `.test_backup_status_is_visible_only_to_the_owner()`
  - Method `.test_storage_report_follows_the_signed_in_person()`
  - Method `.test_media_serves_ranges_for_video_scrubbing()`
  - Method `.test_photos_lists_newest_first_with_paging()`
  - Method `.test_a_chunked_upload_is_accepted()`
  - Method `.test_search_matches_every_word_and_stays_in_scope()`
  - Method `.test_browsing_by_month_kind_and_name()`
  - Method `.test_a_browser_upload_needs_no_hash_and_keeps_a_non_ascii_name()`
  - Method `.test_a_non_media_upload_downloads_instead_of_rendering()`
  - Method `.test_a_second_server_cannot_share_the_port()`
  - Method `.add_person(name)`
  - Method `.test_a_persons_key_uploads_into_their_own_profile()`
  - Method `.test_only_the_owner_may_target_or_manage_other_profiles()`
  - Method `.test_a_rejected_profile_write_changes_nothing()`
  - Method `.test_a_retired_key_is_refused()`
  - Method `.test_a_client_hanging_up_prints_no_traceback()`
  - Method `.test_the_owner_can_turn_starting_with_windows_on_and_off()`
  - Method `.sign_in(profile, password)`
  - Method `.test_people_sign_in_with_a_password_and_see_only_their_own_photos()`
  - Method `.test_wrong_passwords_are_refused_then_braked()`
  - Method `.test_changing_a_password_needs_the_current_one_and_signs_out_other_browsers()`
  - Method `.test_a_successful_password_change_resets_the_brake()`
  - Method `.test_last_day_counts_follow_the_signed_in_person()`
  - Method `.test_the_owner_can_reset_a_password_and_a_key_still_signs_in()`
  - Method `.test_an_owner_password_reset_clears_the_brake()`
  - Method `.test_albums_and_favorites_page_the_photos_they_hold()`
  - Method `.test_bulk_selection_writes_a_validated_batch()`
  - Method `.test_albums_and_favorites_never_cross_people()`

---

### [`tests/test_lenses.py`](tests/test_lenses.py)
**Size**: `40` lines (`1865` bytes)

**Classes:**
- `class LensFilterTest`
  - Method `.setUp()`
  - Method `._add(data, name, lens)`
  - Method `.test_a_lens_filters_and_lists_the_rail()`
  - Method `.test_archiving_removes_the_lens_count()`
  - Method `.test_another_person_sees_only_their_copies()`

---

### [`tests/test_naming.py`](tests/test_naming.py)
**Size**: `47` lines (`1759` bytes)

**Classes:**
- `class SafeNameTest`
  - Method `.test_keeps_an_ordinary_name_and_lowercases_the_extension()`
  - Method `.test_strips_directories_from_either_separator()`
  - Method `.test_replaces_characters_windows_forbids()`
  - Method `.test_prefixes_reserved_device_names()`
  - Method `.test_reserved_name_with_trailing_space_is_neutered()`
  - Method `.test_falls_back_when_nothing_is_left()`
- `class ParseTakenTest`
  - Method `.test_reads_shortcuts_iso_with_zulu()`
  - Method `.test_lowercase_zulu_parses_as_utc()`
  - Method `.test_unreadable_text_is_unknown()`
  - Method `.test_month_folder_is_zero_padded()`
- `class MediaTypeTest`
  - Method `.test_knows_iphone_formats()`

---

### [`tests/test_parts.py`](tests/test_parts.py)
**Size**: `827` lines (`38068` bytes)

**Classes:**
- `class RangeTest`
  - Method `.test_closed_open_and_suffix_ranges()`
  - Method `.test_unsatisfiable_or_multiple_ranges_mean_the_whole_file()`
- `class BodyReaderTest`
  - Method `.test_length_reader_stops_at_the_length()`
  - Method `.test_chunked_reader_decodes_and_consumes_the_trailer()`
  - Method `.test_json_body_must_be_an_object()`
  - Method `.test_a_json_body_split_over_chunks_is_read_whole()`
  - Method `.test_a_chunked_json_body_over_the_cap_is_refused()`
- `class AtomicPlacementTest`
  - Method `.test_placing_a_new_name_refuses_an_existing_file()`
  - Method `.test_placing_moves_the_bytes_and_removes_the_source()`
  - Method `.test_a_copy_fallback_also_refuses_an_existing_file()`
  - Method `.test_a_copy_fallback_still_places_the_bytes()`
- `class RouterTest`
  - Method `.test_exact_and_prefix_routes()`
  - Method `.test_an_exact_trailing_slash_route_is_not_a_prefix()`
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
  - Method `.test_mirror_recopies_same_size_content_change()`
  - Method `.test_verify_refuses_a_target_that_is_not_there()`
  - Method `.test_a_missing_source_is_refused_instead_of_an_empty_success()`
  - Method `.test_a_backup_run_records_its_last_status()`
- `class ThumbnailerTest`
  - Method `.test_without_pillow_previews_are_off()`
  - Method `.test_prune_removes_only_previews_of_photos_that_are_gone()`
- `class ArchiveUiTest`
  - Method `.test_gallery_archive_is_reachable_and_wired()`
- `class TagUiTest`
  - Method `.test_gallery_tags_are_reachable_and_wired()`
- `class PlaceUiTest`
  - Method `.test_gallery_places_are_reachable_and_wired()`
- `class CameraUiTest`
  - Method `.test_gallery_cameras_are_reachable_and_wired()`
- `class SimilarUiTest`
  - Method `.test_similar_review_is_read_only_and_wired()`
- `class MapUiTest`
  - Method `.test_offline_map_is_embedded_and_wired()`
- `class SidecarUiTest`
  - Method `.test_sidecar_export_is_reachable_for_selection_and_viewer()`
- `class LensUiTest`
  - Method `.test_gallery_lenses_are_reachable_and_wired()`
- `class FolderUiTest`
  - Method `.test_read_only_folders_view_is_wired()`
- `class ScrubberUiTest`
  - Method `.test_timeline_scrubber_is_wired_to_outline_months()`
- `class VirtualGridUiTest`
  - Method `.test_day_grid_is_windowed_and_keeps_scroll_height()`
- `class ExploreUiTest`
  - Method `.test_explore_statistics_are_wired_to_outline()`
- `class AlbumsUiTest`
  - Method `.test_albums_overview_is_wired_to_covers_and_counts()`
- `class TagsOverviewUiTest`
  - Method `.test_tags_overview_is_wired_to_counts()`
- `class PeopleOverviewUiTest`
  - Method `.test_people_overview_is_wired_to_profiles()`
- `class ActivityUiTest`
  - Method `.test_activity_overview_is_read_only_and_wired()`
- `class AndroidVersionTest`
  - Method `.test_gallery_android_card_has_live_download_controls()`
  - Method `.test_android_page_loads_its_script_from_a_csp_allowed_file()`
  - Method `.test_android_requests_partial_media_access()`
  - Method `.test_android_version_constants_match_the_build()`
- `class CliErrorTest`
  - Method `.test_an_oserror_is_a_clear_failure_not_a_traceback()`
- `class PasswordHashTest`
  - Method `.test_malformed_stored_hash_returns_false_not_500()`
  - Method `.test_lan_address_falls_back_when_socket_creation_fails()`
  - Method `.test_sync_done_rejects_a_future_started_at()`
  - Method `.test_sync_done_rejects_a_naive_future_started_at()`
  - Method `.test_sync_done_rejects_future_when_clocks_mix_naive_and_aware()`
  - Method `.test_start_ignores_a_future_cursor_left_by_an_old_clock()`
  - Method `.test_media_and_thumb_vary_by_cookie()`
  - Method `.test_warmer_survives_a_catalog_failure()`
  - Method `.test_warmer_retries_backlog_after_a_transient_failure()`
  - Method `.test_too_long_password_names_the_maximum()`
  - Method `.test_details_corrupt_exif_returns_file_facts()`
- `class DamagedConfigTest`
  - Method `.test_both_copies_damaged_is_a_clear_error()`

**Functions:**
- `def temp_dir(test_case)`

---

### [`tests/test_places.py`](tests/test_places.py)
**Size**: `104` lines (`4007` bytes)

**Classes:**
- `class _Exif`
  - Method `.__init__(gps)`
  - Method `.get_ifd(number)`
- `class _Image`
  - Method `.__init__(gps)`
  - Method `.__enter__()`
  - Method `.__exit__(*args)`
  - Method `.getexif()`
- `class _ImageModule`
  - Method `.__init__(gps)`
  - Method `.open(path)`
- `class GeoTest`
  - Method `.test_degrees_minutes_seconds_and_south_west_are_signed()`
  - Method `.test_missing_or_out_of_range_gps_is_none()`
- `class PlaceFilterTest`
  - Method `.setUp()`
  - Method `._add(data, name, latitude, longitude)`
  - Method `.test_a_coarse_point_filters_and_lists_places()`
  - Method `.test_archived_photos_leave_places()`
- `class PlaceMigrationTest`
  - Method `.test_a_format_9_catalog_gains_the_gps_columns()`

---

### [`tests/test_profiles.py`](tests/test_profiles.py)
**Size**: `173` lines (`8753` bytes)

**Classes:**
- `class ProfileBookTest`
  - Method `.setUp()`
  - Method `.test_the_owner_profile_holds_the_library_key()`
  - Method `.test_a_new_library_key_reaches_the_owner_profile()`
  - Method `.test_ids_are_folder_safe_and_unique()`
  - Method `.test_a_new_key_retires_the_old_one()`
  - Method `.test_rekey_invalidates_existing_session_cookies()`
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

**Size**: `86` lines (`3594` bytes)

**Classes:**
- `class RunnerTest`
  - Method `.setUp()`
  - Method `.test_start_serves_and_stop_frees_everything()`
  - Method `.test_a_busy_port_is_a_clear_error()`
  - Method `.test_wait_returns_immediately_when_never_started()`
  - Method `.test_wait_unblocks_after_stop()`
  - Method `.test_prepare_failure_closes_the_library()`
- `class PrefsTest`
  - Method `.test_round_trip_and_fallbacks()`
  - Method `.test_mask_shows_only_the_last_four()`

---

### [`tests/test_scale.py`](tests/test_scale.py)
> *Starting with Windows, and the pieces that keep large libraries fast.*

**Size**: `176` lines (`6349` bytes)

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

### [`tests/test_search.py`](tests/test_search.py)
**Size**: `35` lines (`1570` bytes)

**Classes:**
- `class SearchTest`
  - Method `.setUp()`
  - Method `.names(query, **kwargs)`
  - Method `.test_every_word_must_appear_in_the_file_name()`
  - Method `.test_search_combines_with_other_narrowing()`
  - Method `.test_words_past_the_eighth_still_narrow()`
  - Method `.test_like_wildcards_are_literal()`

---

### [`tests/test_sidecar.py`](tests/test_sidecar.py)
**Size**: `75` lines (`3508` bytes)

**Classes:**
- `class SidecarTest`
  - Method `.setUp()`
  - Method `._request(body)`
  - Method `._zip(body)`
  - Method `.test_json_sidecar_contains_tags_place_and_camera()`
  - Method `.test_xmp_sidecar_escapes_tags_and_writes_gps()`
  - Method `.test_duplicate_names_get_unique_sidecar_files()`
  - Method `.test_another_person_cannot_export_someone_elses_photo()`
  - Method `.test_format_and_empty_selection_are_clear_errors()`

---

### [`tests/test_similar.py`](tests/test_similar.py)
**Size**: `174` lines (`8731` bytes)

**Classes:**
- `class HashTest`
  - Method `.test_a_gradient_becomes_a_hex_difference_hash()`
  - Method `.test_hamming_distance_and_connected_groups()`
- `class SimilarCatalogTest`
  - Method `.setUp()`
  - Method `.test_status_and_cached_groups_are_read_only()`
  - Method `.test_existing_hashes_are_grouped_by_a_rebuild()`
  - Method `.test_archiving_removes_a_photo_from_the_review()`
  - Method `.test_another_person_sees_only_their_copies()`
- `class SimilarApiTest`
  - Method `.setUp()`
  - Method `._request(method, path, body)`
  - Method `.test_scan_indexes_visible_photos_and_listing_groups_them()`
  - Method `.test_build_endpoint_starts_the_background_worker()`
  - Method `.test_unreadable_files_are_skipped_once()`
- `class SimilarMigrationTest`
  - Method `.test_a_format_11_catalog_gains_the_hash_cache()`
  - Method `.test_a_format_12_catalog_gains_the_cached_group_tables()`

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
**Size**: `250` lines (`11136` bytes)

**Classes:**
- `class IngestTest`
  - Method `.setUp()`
  - Method `.test_stores_under_the_month_it_was_taken()`
  - Method `.test_same_bytes_twice_is_a_duplicate_and_keeps_one_file()`
  - Method `.test_a_name_clash_with_different_bytes_gets_a_hash_suffix()`
  - Method `.test_hash_mismatch_keeps_nothing()`
  - Method `.test_a_short_body_is_refused_and_leaves_no_temp_file()`
  - Method `.test_a_full_disk_during_upload_is_a_clear_507()`
  - Method `.test_a_malformed_hash_is_a_usage_error()`
  - Method `.test_ensure_copy_returns_false_when_source_vanishes()`
  - Method `.test_copy_fallback_fsyncs_before_replace()`
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
  - Method `.test_corrupt_row_is_not_reported_as_duplicate()`
  - Method `.test_stored_hashes_are_the_live_catalog()`
- `class StaleBufferTest`
  - Method `.test_startup_keeps_a_fresh_upload_buffer_and_drops_an_old_one()`
- `class SearchEscapingTest`
  - Method `.test_wildcards_in_a_search_are_literal()`
- `class EmbeddedDateTest`
  - Method `.test_the_file_date_is_used_when_the_phone_sends_none()`
- `class RepairAndNamingTest`
  - Method `.setUp()`
  - Method `.test_resending_a_photo_whose_pc_copy_vanished_restores_it()`
  - Method `.test_resending_over_a_damaged_copy_restores_it()`
  - Method `.test_a_name_held_by_a_catalogued_but_missing_file_is_not_reused()`
  - Method `.test_a_rival_file_at_the_chosen_name_is_never_overwritten()`
  - Method `.test_linking_a_second_copy_never_overwrites()`
  - Method `.test_a_connection_error_mid_upload_is_a_clear_failure()`

---

### [`tests/test_tags.py`](tests/test_tags.py)
**Size**: `99` lines (`5176` bytes)

**Classes:**
- `class TagBookTest`
  - Method `.setUp()`
  - Method `.test_creating_a_tag_is_case_insensitive_and_idempotent()`
  - Method `.test_tagging_filters_the_gallery_and_renaming_keeps_marks()`
  - Method `.test_tags_are_private_to_the_person_who_made_them()`
  - Method `.test_archived_photos_leave_the_tag_count_and_delete_removes_marks()`
  - Method `.test_a_batch_changes_each_row_once()`
  - Method `.test_forgetting_a_copy_drops_only_that_persons_marks()`
- `class TagMigrationTest`
  - Method `.test_a_format_8_catalog_gains_the_tag_tables()`

---

### [`tests/test_trash.py`](tests/test_trash.py)
**Size**: `111` lines (`5550` bytes)

**Classes:**
- `class TrashBookTest`
  - Method `.setUp()`
  - Method `.test_a_copy_moves_to_trash_and_restores_its_bytes()`
  - Method `.test_a_shared_photo_stays_for_the_other_person()`
  - Method `.test_permanent_delete_and_empty_remove_the_files()`
  - Method `.test_trash_id_rejects_floats_and_bools_like_albums()`
  - Method `.test_a_trash_id_beyond_sqlite_is_a_clear_error()`
  - Method `.test_update_rejects_restore_and_delete_together()`
  - Method `.test_another_person_cannot_restore_or_delete_the_entry()`
- `class TrashMigrationTest`
  - Method `.test_a_format_5_catalog_gains_the_trash_table()`

---
