# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: Apple Shortcuts as the phone client, hash-proven ingest, SQLite catalog
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: The user wants an iPhone to copy photos to their Windows PC whenever it is on the
  home Wi-Fi, with no app installed, and to delete from the phone only what the PC really holds.
  A web page cannot read the photo library in the background; Shortcuts automations can.
- **Decision**: The phone side is two Shortcuts (sync and cleanup) documented in the gallery's
  Setup tab, since unsigned `.shortcut` files cannot be imported on current iOS. The server is
  Python standard library only (`http.server`, `sqlite3`). Each upload carries the phone's
  SHA-256; the server streams to `.harbor/incoming`, hashes, keeps the file only on a match,
  fsyncs and `os.replace`s it into `photos/YYYY/MM/`. `GET /api/has` re-hashes the stored copy
  before answering `yes`. The catalog and journal live in one SQLite file (WAL,
  `synchronous=FULL`, `PRAGMA user_version` 1, unknown versions refused untouched), so
  transactions replace the temp-file-and-replace protocol for that state. `config.json` uses
  the atomic write with a `.bak`. Requests from non-private addresses are refused, and every API
  call needs the library key. Pillow and pillow-heif are optional and imported only in
  `thumbs.py`.
- **Consequences**: Nothing is installed on the iPhone and nothing unverified can be deleted. The
  cost is a manual Shortcut setup (about ten minutes), one confirmation tap per cleanup (iOS
  enforces it), and a full re-hash per `has` query, which is slow for large videos. If
  Shortcuts' Generate Hash ever hashes different bytes than it uploads, every upload is
  rejected (422) rather than stored unverified.

### ADR-002: Month/kind/name browsing and hashless browser uploads
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: The user wants to browse the library on the web, not only scroll a single
  timeline, and a way to add photos from a browser. Review screenshots also showed unfinished
  rows with clipped corners, "Today" in English beside dates in the browser's language, and
  setup panels hugging the left edge.
- **Decision**: `GET /api/outline` returns months with counts and the video count;
  `GET /api/photos` takes `month`, `kind` and `q` (a LIKE match on the original name, with `!` as
  the escape character). The gallery shows these as a sticky sidebar, which becomes a chip row
  under 900 px. Search spans the whole library. `POST /api/upload` accepts a percent-encoded
  `X-Name` and no `X-Sha256`: the PC hashes what it received, so a browser upload is proven
  against its own bytes, not a phone's. The date order is `X-Taken`, then EXIF DateTimeOriginal
  via optional Pillow (`exif_dates.py`, injected into `PhotoStore`), then `X-Modified`. Tiles are
  rounded individually, today/yesterday come from `Intl.RelativeTimeFormat`, and the Sync and
  Setup views are centred at 920 px.
- **Consequences**: Browser uploads skip the end-to-end hash check that Shortcut uploads get. A
  dropped connection is still caught by the Content-Length check, and the cleanup only deletes
  what `has` re-verifies. Without Pillow, browser-uploaded photos are dated by their file time,
  which on an iPhone picker can be the time they were picked.

### ADR-003: Self-repairing duplicates, download-only non-media, exclusive port, socket timeout
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: A review of the browser milestone found five faults. A re-sent photo whose PC copy
  had vanished or been damaged was answered `duplicate` and stayed broken. A new photo whose name
  was still held by a catalogued but missing file was moved into place but never catalogued, so
  every sync sent it again. An uploaded HTML or SVG file would render, and run scripts, on the
  gallery's own origin. On Windows a second server could bind the same port without an error. A
  stalled client held a server thread forever.
- **Decision**: On a hash match, `PhotoStore` re-verifies the stored copy and, if it fails, puts
  the verified upload back at the catalogued path and answers `stored`. `Catalog.add` raises on
  a `rel_path` clash, and the store then tries `name-<sha8>` and `name-<sha256>`. `/media` serves
  only `image/*` (not SVG) and `video/*` inline; anything else is
  `application/octet-stream` with `Content-Disposition: attachment`. `HarborServer` turns
  `allow_reuse_address` off on Windows. Handlers time out after 120 s, and a read error mid-upload
  becomes the "upload stopped early" HarborError. A config whose `.bak` is also unreadable fails
  with Error/Why/Fix instead of a traceback.
- **Consequences**: A duplicate upload now costs one re-hash of the stored copy. A phone left
  mid-upload for over two minutes has to retry.

### ADR-004: One profile per person, catalog format 2, import from disk
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: The user asked for profiles and for uploading from the PC's disk. One library is
  shared by a household, and each iPhone should sync into its own person's space without a
  second server or a second library.
- **Decision**: The catalog moves to format 2. `photos` and `events` gain a `profile` column,
  and a `profiles` table holds `id` (folder-safe, from the name), `name` and a unique `key`.
  Format 1 is upgraded in one transaction after a SQLite backup copy to
  `catalog.sqlite3.v1.bak`; existing rows default to `main`. The library key in `config.json`
  is always the `main` profile's key, so existing Shortcuts keep working, and only that key may
  add people, issue new keys or upload for another profile (`X-Profile`). New originals go to
  `photos/<profile>/YYYY/MM`; older files are not moved. A SHA-256 stays globally unique, so
  shared photos are stored once under the first sender. Sync start/done and reports are kept per
  profile. `importer.import_folder` walks a folder (skipping hidden folders and the library
  itself), streams each media file through `PhotoStore.ingest` with the file's mtime as the
  fallback date, and never writes to the source. If another process catalogues the same bytes
  first, the placed copy is removed and the result is `duplicate`.
- **Consequences**: Profiles separate photos, not access: any valid key can browse everyone's
  photos, because this is one household. A photo both phones hold appears only in its first
  sender's profile. Re-keying `main` stays a PC-side action (`key --new`).

### ADR-005: Harbor window, background runner and double-click launchers
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: The user asked for a server start button and a file that opens the photo
  browser, so no console is needed day to day.
- **Decision**: `runner.ServerRunner` starts `HarborServer` on a daemon thread and stops it,
  together with the optional daily backup. Both `serve` and the window use it. The window
  (`control_panel.py`, tkinter from the standard library) offers Start/Stop, Open photo
  browser, the iPhone address, people with Copy key / New key / Add person, Import folder…
  with progress and cancel, and an activity log. Worker threads reach Tk only through a queue
  drained on the Tk thread. Window choices persist in `~/.photo-harbor/panel.json` (version 1,
  atomic write; a damaged or unknown file falls back to defaults). `Harbor.pyw` opens the window
  without a console, and `Open Photo Browser.url` points at `http://localhost:8642/`. The server
  now ignores `ConnectionError` in `handle_error`, because Windows reports every idle keep-alive
  close as `ConnectionAbortedError` and printed a traceback for each one.
- **Consequences**: A Python without tkinter cannot open the window; `panel` prints
  Error/Why/Fix and `serve` still works. The `.url` file assumes port 8642. The window has no
  dark mode.

### ADR-006: Start with Windows via the Run key; catalog format 3 and background work for GB-scale libraries
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: The user asked for a start-on-Windows setting, available in the web browser too,
  and for Harbor to handle gigabytes easily. Measurements on 1-2 GB files, a 1 GB folder and a
  50,000-row catalog showed that server upload throughput was already near the disk's hash+write
  rate (169 MB/s; the earlier 76 MB/s was the benchmark client's 8 KB sends). The real costs were
  elsewhere: a re-import re-read every file (11 s per GB), the people list took 223 ms, name
  search 230-344 ms, and thumbnails were made only on first view.
- **Decision**: `autostart.Autostart` writes or deletes the `Harbor` value under
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (no admin rights; `winreg` from the
  standard library), with the command `pythonw.exe Harbor.pyw --startup`. The registry sits
  behind an injected adapter so tests never touch the real one. The window and
  `POST /api/startup` (owner only) share it. `--startup` iconifies the window, starts the server
  on the first idle tick, and opens the browser if that preference is set. Catalog format 3 adds
  `imported_files(source, size, mtime_ns, sha256)`, which lets `import_folder` skip unchanged
  files whose photo is still present, and a covering index `photos_profile_totals`. Formats 1
  and 2 upgrade in one transaction after a backup copy. Name searches read `photos NOT INDEXED`
  and sort the matches. I/O blocks grow from 1 MB to 4 MB. `PhotoStore.on_stored` feeds a
  `PreviewWarmer` thread that makes previews for new photos first, then backfills older ones
  newest first; JPEG previews use Pillow's draft mode. The browser runs 3 uploads in parallel.
- **Consequences**: Re-import 11 s to under 0.1 s, people list 223 ms to 10 ms, search to 14
  ms. Start-with-Windows starts at sign-in, not at boot. The import skip list trusts path, size
  and mtime, so a file edited in place without changing either is not re-read (its old photo
  stays). `has` still re-hashes in full, so deletion safety is unchanged.

### ADR-007: Name-and-password sign-in, private per-person galleries
- **Date**: 2026-10-25
- **Status**: Accepted
- **Context**: The user asked that people reach their own photos from the local server and be
  able to change their passwords. Until now any key opened everyone's photos, and browsers
  signed in by storing the key itself in a cookie.
- **Decision**: `profiles.password_hash` stores `pbkdf2_sha256$240000$salt$hash` (standard-library
  `hashlib.pbkdf2_hmac`). Signing in (`POST /api/login` with `{profile, password}`, or `{key}`
  for someone without a password yet) opens a random session whose SHA-256 is stored in
  `sessions`, sent as an HttpOnly, SameSite=Strict `harbor_session` cookie for 365 days. Shortcuts
  keep using `X-Harbor-Key`. Five wrong passwords from one address lock it for 5 minutes (in
  memory). People change their own password with the current one; the owner can set anyone's.
  Either change signs that person out elsewhere. Every non-owner request is scoped to its own
  profile: photos, outline, status, the missing list, people, `/media` and `/thumb` (a photo
  outside your folder is a 404), and asking for another profile is a 403. The owner keeps the
  everyone view. `GET /api/people` (names only) is public so the sign-in screen can show who to
  pick on the home network.
- **Consequences**: Family members no longer see each other's photos unless both own the photo.
  A forgotten password needs the owner (or the person's key). The brake resets when the server
  restarts.

### ADR-008: Readable per-person folders, hard-linked shared photos, folder reconciliation
- **Date**: 2026-10-25
- **Status**: Accepted
- **Context**: The user asked that folder storage on Windows be simple, understandable and usable
  without the app. The old layout (`photos/<id>/YYYY/MM`) used ids, and a photo owned by two
  people existed in one folder only.
- **Decision**: Catalog format 4 adds `copies(profile, sha256, rel_path, original_name, added_at)`
  and `profiles.folder`; paths become relative to the library. Files live at
  `<Person>/<YYYY>/<YYYY-MM>/<name>`, with the person's display name made Windows-safe and unique
  (`Ayşe (2)`). A second owner gets an NTFS hard link (`os.link`, copy as fallback), so the photo
  sits in both folders at the cost of one. `/api/has` makes sure the asking person has a verified
  copy (linking it if the PC has the bytes) before saying yes. `layout.LibraryLayout.prepare`
  writes a bilingual guide, hides `.harbor`, creates person folders, and moves old-layout files one
  at a time on start (resumable). Renaming a person renames their folder and rewrites the paths.
  `scan.LibraryScanner.reconcile` (start and every 6 h) adopts media files dropped into a person's
  folder (after 2 minutes without changes), follows moves by hash, and forgets deleted copies. If
  over 50 and over 10 % of files vanish at once it removes nothing, since that looks like an
  unplugged drive. `check` (weekly, or on demand) re-hashes every copy and reports damage without
  deleting. Backups mirror the person folders and skip `.harbor`.
- **Consequences**: People can browse, copy and back up photos in File Explorer, and deleting a
  file there deletes it from Harbor for that person. Hard links share bytes, so damage to one
  shows in every copy; repair re-links all copies to the repaired file. The backup drive holds
  plain copies, so shared photos take space twice there. A file edited in place in Explorer is
  reported as damaged by the weekly check rather than re-imported.

### ADR-009: Review of the accounts and folders work before release
- **Date**: 2026-10-25
- **Status**: Accepted
- **Context**: A review of everything since the last push found five faults and one performance
  gap. (1) The import skip list skipped files already imported for *any* person, so importing a
  folder for a second person added nothing to their private view. (2) Any database or disk error,
  or stopping the server mid-scan, killed the scan thread silently, and folders were never
  reconciled again; its messages also went to a console the window does not have. (3) A
  non-integrity SQLite error inside `Catalog.add` or `CopyIndex.forget` left a savepoint, and so
  an open transaction, behind, and nothing written afterwards would be committed. (4)
  `ensure_copy` re-hashed under the placement lock, so a large video held up every upload. (5)
  Expired sessions were never removed. Measured at 50,000 photos, one person's view took 200-918
  ms per page, 462 ms per outline and 206 ms for the people list, because ordering needed the
  date from the joined photo row.
- **Decision**: The skip list now requires *this* person's copy. `ScanSchedule` runs each pass
  inside a handler that logs `sqlite3.Error`/`OSError` and carries on (quietly when stopping),
  reconcile honours the stop event, and the runner routes scan messages to the window's log,
  listing up to ten damaged files. Both savepoints roll back and release on any `sqlite3.Error`.
  `ensure_copy` hashes before taking the lock. Starting a session deletes expired ones. Format 4
  (unreleased until this commit) gives `copies` its photo's `sort_time`, `size` and `is_video`,
  with indexes `copies_by_time (profile, sort_time DESC, sha256 DESC)` and covering
  `copies_totals`. One person's page, outline and totals read the copy rows alone, and a person's
  name search scans their copies unindexed.
- **Consequences**: One person's page takes 10-33 ms, outline 26 ms, status 10 ms, people list 9
  ms and search 23 ms at 50,000 photos; a page 45,000 deep takes about 150 ms (OFFSET). The copy
  rows repeat three immutable facts of their photo.

## Licensing migration (agpl-final)

- New versions use the Aegean License 1.1 (AL-1.1); versions up to and including `agpl-final` remain under GNU AGPL-3.0.
- Rights holder: AegeanWorks; commercial use under ACL-1.0.
- Counsel review of the 1.1 texts remains pending.

## License notice cleanup (2026-10-26)

- The license-history notes were removed from README.md and COMMERCIAL.md: the project is offered only under the Aegean License 1.1 (AL-1.1), with commercial use under ACL-1.0.

### ADR-010: Personal albums and favorites without moving files
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: After per-person folders landed, the library could only be narrowed by month,
  kind and file name. There was no way to keep a set of photos for a trip or mark the keepers,
  and copying them into album folders would break the plain-folder layout, duplicate storage and
  desynchronise the catalog.
- **Decision**: Catalog format 5 adds `favorites (profile, sha256, added_at)` and
  `albums (id, profile, name COLLATE NOCASE, created_at)` plus
  `album_photos (album_id, sha256, added_at)`. The migration is additive from format 4 and keeps
  every existing row; the old catalog is backed up as `catalog.sqlite3.v4.bak`. Albums and
  favorites belong to the signed-in person, so the owner's marks are the owner's own. Album names
  are trimmed, limited to 60 characters and unique case-insensitively per person. The gallery
  gains a Favorites entry and an album list in the rail, a heart and **Add to album…** in the
  viewer, and rename/delete controls on an album. `/api/photos` accepts `favorite=1` and
  `album=ID`, every photo carries its viewer's `favorite` flag, and `/api/albums` returns counts
  and the newest member as a cover. Albums never move, copy or delete a file.
- **Consequences**: A photo can be in any number of albums at no extra disk cost, and deleting an
  album leaves its photos in the library. Reads join `photos`, so a membership row left behind
  when a file leaves the catalog is invisible and cannot resurrect a missing photo. Format 5 is
  readable only by this version; an older build refuses it and leaves the `.v4.bak` intact.

### ADR-011: Gallery selection and bounded bulk writes
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Albums and favorites worked one viewer at a time. Collecting a trip's photos meant
  opening each photo, pressing the heart, and choosing an album, which is slow and easy to leave
  half done.
- **Decision**: The gallery gains a **Select** mode: tiles become checkable, a selection bar shows
  the count and offers **Select all loaded**, **♥ Favorite**, **♡ Unfavorite**, **Add to album…**
  and **Clear**, and changing scope or leaving the gallery ends the mode. `POST /api/favorite` and
  `POST /api/album-photos` accept either `sha256` or `sha256s`; a batch is capped at 500,
  de-duplicated, and every hash is checked for existence and (for non-owners) ownership before
  the first write. `AlbumBook.add_many` and `favorite_many` apply the rows under one database
  lock; the browser splits larger selections into 500-hash requests.
- **Consequences**: A batch request is all or nothing once validation passes, but a multi-request
  selection stops at the first failed chunk. Selection is client-only and never persisted; a
  filter, person switch or tab change clears it. Single-hash callers keep the old request shape,
  and `changed` now reports the number of rows changed rather than a boolean.

### ADR-012: Details are read on demand, never indexed
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The viewer showed only the file name, date and size, although originals carry
  dimensions and camera settings. Copying every EXIF tag into SQLite would add a migration and a
  second source of truth for data that changes only when the file does.
- **Decision**: `details.py` reads the requested original when the viewer asks. File facts (name,
  type, size, capture and added dates) are always returned; with Pillow, `Image.open` supplies
  pixel dimensions and curated EXIF fields (make, model, lens, exposure, aperture, ISO, focal
  length). GPS and free-form tags are deliberately not exposed. `GET /api/details/<sha256>` uses
  the same visibility rule as `/media`, so a non-owner sees only their own copy. Pillow and
  pillow-heif loading moves into `pillow_support.py`, shared with previews and date extraction.
- **Consequences**: Each Details open reads one file and holds no cache, so a very large image
  costs one decode to read its header while the catalog stays untouched. A malformed or
  unsupported file still returns the facts Harbor already knows, and videos return file facts
  only. A future GPS or histogram feature would need a deliberate new decision rather than an
  accidental field.

### ADR-013: Downloads are one-time ZIP tokens, not library copies
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: A selection or album can now hold dozens of photos, but taking them out meant
  opening each original and downloading it separately. A long-lived archive directory would
  silently double disk use and become stale.
- **Decision**: `POST /api/download` accepts `sha256`/`sha256s` or `album`, validates visibility,
  and writes one stored (uncompressed) ZIP to `.harbor/downloads`. The response carries a random
  token URL; `GET /api/download/<token>` serves it once to the same profile, then deletes the
  file. Tokens expire after 15 minutes, archives are capped at 8 GB with a 1 GB free-space
  reserve, and startup removes any archive left by a restart. `Reply.delete_after` lets the
  HTTP sender unlink the file in a `finally`, even when the client disconnects. `selection.py`
  now owns bulk hash parsing and all-or-nothing validation for both album writes and downloads.
- **Consequences**: The library is never copied permanently, and an interrupted download cannot
  leave a served token behind. Preparing a large ZIP costs one temporary file and a synchronous
  read of every selected original, so a slow disk delays the request; the 8 GB cap bounds that
  cost. A token is a short-lived capability bound to the profile, not a share link.

### ADR-014: Storage is an aggregate view, not a second index
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The Sync tab showed only a total file count and bytes. A shared photo is stored
  once on disk but appears in two people's folders, so neither `photos` nor `copies` alone tells
  the whole story, and there was no list of the files most likely to matter when space runs low.
- **Decision**: `Catalog.storage(profile)` runs indexed aggregates: whole-library totals come
  from `photos` (each file once), one person's share from `copies`, the shared count from a
  grouped `copies` query, per-person shares from a grouped `copies` query, and the ten largest
  files from the visible side. `GET /api/storage` applies the same profile visibility as
  `/api/status`; the Sync tab renders the summary, people and largest files, with links to the
  originals. No schema or state is added.
- **Consequences**: A report is three or four cheap queries and never reads a photo. The
  whole-library byte total is the disk cost; the sum of per-person shares can be larger because
  a shared photo is counted in each share, which the UI states. A non-owner sees only their own
  files and no people breakdown; a future per-folder or per-year report can reuse the same
  aggregates without a migration.

### ADR-015: Album covers and creation from the selection
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Albums were plain text rows, and creating one while photos were selected forced
  the user back to the sidebar and lost the selection. Both made a working feature feel
  unfinished.
- **Decision**: The album rail row carries a small lazy cover from the newest member (the
  existing `/thumb` route and `cover` field); a missing or broken thumbnail falls back to the
  text label. The selection **Add to album…** menu always starts with **New album…**; choosing
  it prompts for a name, creates the album, and sends the selected hashes through the existing
  chunked batch endpoint. No server contract changes.
- **Consequences**: A cover costs one thumbnail request per album row and never blocks the
  label; the cover follows the newest photo, so it changes as photos are added. Creating from a
  selection is one continuous flow, but a failed add leaves the empty album in place with an
  error toast, which is honest and recoverable.

### ADR-016: Backup verification compares hashes, not just sizes
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The daily mirror skips a file when the destination size matches, which is fast
  but cannot detect bit rot or same-size corruption on the backup drive. The window could say a
  backup ran, but not whether the copy is good.
- **Decision**: `backup.verify(source, target)` walks the visible library and the backup,
  compares sizes, then streams SHA-256 for every matching pair in 1 MB blocks. It reports
  missing, different and extra counts plus the first 50 problem paths. `backup --to DIR --check`
  prints the report and exits 1 when anything is missing or different; extra files are
  informational because the mirror never deletes. The Harbor window's **Check backup** button
  runs the same function on a background thread and logs the result. Both refuse a target inside
  the library.
- **Consequences**: A check reads every byte of both drives, so it takes as long as the library
  is large; it is explicit, never automatic. Extra files count as normal history from deleted
  photos, not damage. A backup that was never made fails with a clear message instead of
  reporting zero files as clean.

### ADR-017: Date windows are inclusive and combine with every other filter
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Months were the only date axis. A trip that crosses a month boundary, or a single
  day, still meant scrolling, and there was no way to combine an exact period with a person,
  album or search.
- **Decision**: `PhotoFilter` gains `start`/`end` (`YYYY-MM-DD`, both optional and inclusive).
  `Catalog._where` compares `substr(sort_time, 1, 10)`, so the existing date order and the
  current index family stay valid. `/api/photos` accepts `from`/`to`, rejects anything that is
  not the exact date shape, and rejects a start after the end. The gallery's **Dates** popover
  fills the scope keys and resets when any other scope is chosen; the title shows the window and
  the count reflects the filtered page.
- **Consequences**: A date window costs one extra `substr` predicate per side and works on the
  same `sort_time` the gallery already sorts by. Choosing a month, person, album or favorites
  clears the dates; the month outline stays global so the sidebar remains a way out of the
  window. A future saved-search feature can serialize the same four keys.
