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

### ADR-018: Sort order is part of the gallery filter, with a stable tiebreaker
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The gallery was always newest-first. Finding the oldest photo, or the largest
  files, meant opening another tool; a sort control is a natural companion to the date window
  and storage report.
- **Decision**: `PhotoFilter.order` accepts `newest` (default), `oldest`, `largest` and
  `smallest`; `/api/photos` validates the same set. `Catalog.page` maps each order to an
  `ORDER BY` on the owner side (`photos` for the library, `copies` for one person) and always
  ends with `sha256` as a stable tiebreaker. The scope-bar **Sort** select updates the scope
  without clearing dates, album, favorites or search; person, month and favorites changes keep
  the chosen order.
- **Consequences**: Sorting costs no extra query and no schema, and pagination remains stable
  because every order has a unique tiebreaker. Largest/smallest sort by stored bytes, not pixel
  dimensions, which is the number the storage report uses. A future custom order (for example
  a drag-and-drop album sequence) would need a stored position rather than another SQL order.

### ADR-019: Trash moves only the caller's copy and restores through ingest
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: There was no way to remove an unwanted photo in Harbor; doing it in Explorer
  bypassed the catalog, and a direct delete would be irreversible. A photo can be shared by
  hard link between people, so removing one person's copy must not remove another's.
- **Decision**: Catalog format 6 adds a `trash` table. `TrashBook.move(profile, sha)` inserts a
  row, moves that profile's file into `.harbor/trash/<token>/<safe name>`, then calls
  `CopyIndex.forget(profile, sha)`; if forgetting fails the file is moved back and the row is
  removed. A shared photo keeps its other copy and stays in the catalog; the last copy removes
  the photo row. Restore re-ingests the trashed bytes with the original hash, name, profile and
  capture time through `PhotoStore.ingest`, so placement, hard links and thumbnails use the
  normal path; only then is the trash row and file removed. Permanent delete and empty remove
  the files. The Trash tab is per person, and move/restore/delete all check ownership.
- **Consequences**: Trash is a safety net, not a second gallery: files are hidden from the
  library, storage report and backup mirror until restored. A crash between the move and the
  catalog forget leaves a row and a file for the scanner to reconcile; no bytes are deleted in
  that path. The owner cannot trash another person's copy from the everyone view; the error
  tells them to select that person. Empty trash is the only irreversible action, and the UI
  confirms it.

### ADR-020: An album can keep a chosen cover
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The rail cover was always the album's newest photo, which is rarely the image
  that represents a trip. Choosing one should not copy a file or require a second thumbnail.
- **Decision**: Catalog format 7 adds nullable `albums.cover_sha`. `AlbumBook.set_cover` accepts
  a hash only when it is a current member whose photo still exists; an empty value resets it.
  Removing that photo from the album clears the column. `summary` uses the chosen hash when it
  is still a member and otherwise falls back to the newest member, so old albums and a removed
  or trashed cover degrade without a broken image. The viewer shows **Use as cover** only while
  an album is the current scope. `/api/albums/<id>` accepts `{cover: sha256}` or `{cover: null}`.
- **Consequences**: A cover costs one nullable column and reuses `/thumb`. The cover follows the
  chosen photo until it leaves the album; a fallback is computed live rather than stored. Format
  6 upgrades add the column; formats 1-4 get it from the recreated albums table, so no duplicate
  ALTER runs.

### ADR-021: Select matching asks the server for the filtered hashes
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: **Select all loaded** only covered the pages the browser had already scrolled in.
  A 300-photo album or a wide date window still required scrolling before a bulk action, and the
  album selector cannot know which pages are still unloaded.
- **Decision**: `Catalog.hashes` runs the same `_source`/`_where`/`_ORDER` path as `page` but
  selects only `p.sha256`, capped at 10,001 rows so the API can report a 10,000 cap without a
  second count query. `GET /api/photos/hashes` accepts exactly the `/api/photos` filters,
  including profile privacy, album ownership and order. The selection bar adds **Select
  matching**; it adds every returned hash to the client Set, marks loaded tiles, and tells the
  user when the 10,000 cap was hit. Existing bulk writes still chunk at 500.
- **Consequences**: One request can return up to 10,000 hashes (about 670 KB); a wider library
  must narrow the filters. Selection remains client-only and resets with the scope, and no new
  state or schema is added. The endpoint is read-only and uses the same validation as the page,
  so a malformed filter fails before any hash is returned.

### ADR-022: Search is a narrowing axis, not a scope reset
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Typing in the search box silently cleared the album, favorites, month and date
  scope and searched the whole library. That contradicted the visible scope and made it
  impossible to search inside a trip or a date window. A single `LIKE` also treated
  `trip beach` as one literal substring.
- **Decision**: The search handler no longer rewrites `state.scope`; `q` combines with every
  existing filter, and the title shows `scope · “query”`. `Catalog._where` splits the query on
  whitespace (up to 8 terms) and adds one escaped `LIKE ... ESCAPE '!'` per term, so all words
  must appear in the file name. The count uses the filtered page whenever a query, month, kind
  or date is active; album/favorite totals are only shown for the unfiltered collection.
  **Show everything** remains the single explicit reset.
- **Consequences**: Searching is now contextual, which is what the scope header promises;
  finding a photo outside the current view means clearing the scope first. Multi-word search
  adds one indexed-or-scan predicate per term and keeps the same wildcard escaping. No schema
  or API shape changed; existing `q=` callers gain the all-words semantics.

### ADR-023: The viewer is a modal for keyboard and screen-reader users
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The viewer had `role="dialog"` and `aria-modal`, but focus stayed on the page
  behind it, Tab could leave the dialog, and closing dropped focus. The shortcuts added over
  time were also undiscoverable.
- **Decision**: Opening the viewer records the focused tile (only when it was closed), focuses
  **Close**, and traps Tab/Shift+Tab among visible, enabled controls. Closing restores focus to
  the recording when that element is still connected. Escape closes date/album/detail menus
  when no viewer is open. Selection and trash counts are `aria-live="polite"`, the viewer's
  favorite/details/close buttons declare `aria-keyshortcuts`, and Setup has a Keyboard panel.
- **Consequences**: Keyboard users cannot tab into the hidden page, and a closed viewer returns
  them to the photo they opened. Focus is not restored after an action that removes the tile
  (for example Move to trash), because the target is gone; the browser falls back to the page.
  The help panel is static and costs no script.

### ADR-024: A native Android client, built without AndroidX and served by Harbor
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The phone side was Apple Shortcuts only. Android users had no client and no way
  to install one from the same home server; adding AndroidX and Gradle would add a second
  toolchain and a large dependency surface to a deliberately small project.
- **Decision**: Add `android/` with a plain Java client for Android 8+ (minSdk 26, target 34):
  programmatic UI, MediaStore query over `date_added`, SHA-256 hash before upload, `/api/has`
  first, `/api/upload` with `X-Harbor-Key`, `X-Name`, `X-Sha256`, `X-Taken`, then
  `/api/sync/done`. An optional persisted `JobScheduler` job runs every 6 hours on an unmetered
  network; a manual **Sync now** button shares the same engine. `android/build.py` compiles with
  `javac`, links with `aapt2`, dexes with `d8`, aligns with `zipalign`, signs with a debug key in
  `~/.harbor-android/debug.keystore`, and verifies with `apksigner`; no Gradle or runtime
  libraries. Harbor serves `/android/` and `/android/Harbor.apk` publicly on the home network,
  and Setup links to it. Cleartext is enabled because the server is plain HTTP on the LAN.
  `Router.add_exact` serves a trailing-slash page without turning it into a parameter prefix.
- **Consequences**: One APK is installed by sideloading and updated only when signed with the
  same private debug key; the key stays outside the repository. The app keeps the phone's files
  and deletes nothing, so cleanup remains an iOS Shortcut feature for now. The client has no
  AndroidX, so its UI is intentionally plain and its sync is a single foreground/background
  pass rather than a system media observer. The APK is built only when the SDK is present; the
  served binary is committed so a normal server install needs no Android toolchain.

### ADR-025: Android share sheet uploads chosen items directly
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Scheduled sync handles new media, but sending one photo from Gallery meant opening
  Harbor first; a wrong address or key was only discovered after a long sync started.
- **Decision**: Add an exported `ShareActivity` with `ACTION_SEND` and `ACTION_SEND_MULTIPLE`
  filters for `image/*` and `video/*`. It reads the granted content URIs, queries display name,
  size and capture/added time, then runs the same SHA-256 → `/api/has` → `/api/upload` path
  without starting or finishing a sync journal entry. A shared item is skipped when the PC
  already has it. The settings screen gains **Test**, which calls `/api/status` with the saved
  key and reports the library count. No new permission or persistence is added.
- **Consequences**: A share upload does not advance the journal's last-sync time, so the next
  scheduled sync still checks recent media (hash checks make this cheap). Share metadata can be
  missing on unusual providers; the app falls back to the URI name, asset length and the current
  time, and skips a file whose size cannot be determined. Both the share activity and the
  background job rely on the same hash check, so concurrent uploads cannot store a file twice.

### ADR-026: APK downloads carry a verifiable metadata sidecar
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: A sideloaded APK is an opaque binary; the install page showed no version, size or
  checksum, so a user could not tell whether the served file was the build they expected.
- **Decision**: `android/build.py` writes `Harbor.apk.json` after `apksigner verify`, containing
  version, versionCode, size, SHA-256 and build time. Harbor serves it publicly at
  `/android/Harbor.apk.json` with `Cache-Control: no-cache`; the install page fetches it and
  replaces the static note with the exact version, size and full SHA-256. Metadata is generated
  only from the signed bytes, never hand-written.
- **Consequences**: The checksum identifies the exact APK without adding a signing service or
  another dependency. If the sidecar is missing the page falls back to its static note and the
  JSON route returns 404; the APK itself is still served. A future updater can compare
  `versionCode` from the same file without parsing the APK.

### ADR-027: Android checks the served versionCode on launch
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: The install page shows the version and checksum, but an already-installed app
  could not notice that the server had a newer build; users had to compare manually.
- **Decision**: The app carries `VERSION_CODE`/`VERSION_NAME` constants matching the manifest.
  On launch, if a server is saved, a background thread reads the public
  `/android/Harbor.apk.json` and compares `versionCode`. A newer value shows **Update Harbor**
  and a message; the button opens the server's `/android/` page in the browser. A missing,
  malformed or unreachable sidecar is treated as "no update" and never blocks the screen.
- **Consequences**: The check is one public read on launch and adds no permission. Installing an
  update still goes through Android's browser/installer confirmation; the app does not self-
  install. The constants must be bumped with the manifest in future builds, and the metadata
  sidecar is the single comparison source.

### ADR-028: The gallery is an installable PWA with a shell-only cache
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Android and desktop users could open the gallery in a browser but could not
  install it as a standalone app, even though a manifest and an SVG icon already existed.
- **Decision**: Add PNG icons (192/512), manifest entries, and `sw.js` served from `/sw.js` with
  `Service-Worker-Allowed: /` and no-cache. Registration runs from the external `app.js` because
  the page's CSP forbids inline scripts. The worker pre-caches the shell on install, then uses
  network-first for same-origin GETs so online clients always see fresh assets, falling back to
  the cache only when offline. `/api`, `/media`, `/thumb`, `/android` and `/sw.js` are bypassed;
  private photos and JSON are never cached. Old caches are deleted on activate.
- **Consequences**: Chrome/Edge can install the gallery with an offline shell, but photos still
  require the server; offline opens the UI without data. The cache is per browser profile and
  not shared between people. Bumping the cache name is only needed if the shell pre-cache list
  changes; network-first keeps ordinary asset updates fresh.

### ADR-029: Backup status is an owner-only snapshot
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: `DailyBackup` reported into the Harbor window log only; the web Sync tab could
  show photos and storage but not whether the second copy was configured or had last succeeded.
- **Decision**: `DailyBackup` keeps an immutable `BackupStatus` (target, last attempt, copied,
  unchanged, bytes, error) under a lock and exposes `run_once()` plus `status()`. `ServerRunner`
  attaches the running backup to `HarborApp`; `GET /api/backup` returns the snapshot only to the
  owner and `{"configured": false}` when no `--backup-to` was supplied. The Sync tab shows the
  target and last result, or hides itself for non-owners. No status is persisted; it describes
  this server process.
- **Consequences**: A web user can see the last mirror result without opening the Harbor window,
  and a failed target is visible as text. A restart shows a fresh “starting” state until the
  first run completes. The check remains a separate explicit action; this endpoint never starts
  a long verification from a page request.

### ADR-030: Sign-in gate keeper; gallery views withheld for privacy
- **Date**: 2026-11-03
- **Status**: Accepted
- **Context**: The browser UI past sign-in shows the owner's personal photo library; there is no
  demo or seeded library mode, and signing in with the live main key to screenshot private
  photos would expose personal data and risk state changes.
- **Decision**: Register only `2026-11-03-signin.png` (unauthenticated profile picker plus key
  link, commit `c73fa38`, viewport 1440x900) in `.aikit/media.json` and the README
  `aegean:screenshots` block. Gallery/browse views stay uncaptured until a seeded demo
  library mode exists.
- **Consequences**: README proves the real first-run gate without leaking credentials or
  personal photos. A demo-library feature would unlock full coverage; that is new scope,
  explicitly not this change.

### ADR-031: Bounded ids, whole chunked JSON, and exclusive file placement
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: An audit of the request, catalog and placement paths found four gaps that the
  188 passing tests did not cover. Album ids, trash ids and page offsets were turned into
  Python integers and bound to SQLite, which only accepts signed 64-bit values, so a crafted
  request produced an uncaught `OverflowError` and a 500. `Request.json` read a chunked body
  once, so JSON split over two chunks was rejected. A new photo was moved into its month folder
  before the catalog accepted its path, so a server upload and a CLI import that chose the same
  name could make the second write overwrite the first file. And private JSON answers carried no
  `Cache-Control`, leaving a shared browser free to reuse one person's data after a sign-in
  switch.
- **Decision**: `MAX_ROW_ID` (2^63-1) bounds every album id, trash id and page offset; an
  out-of-range value is a clear 400 before SQLite sees it, and `Catalog.page`/`hashes` keep the
  same guard defensively. `Request.json` reads through `_read_body` until the cap or the end of
  the body, so chunked and partial streams are parsed whole; a body over 64 KiB still gets 413.
  `place_exclusive` gives a new name its bytes with a hard link or an exclusive ``xb`` copy and
  raises `FileExistsError` instead of replacing a rival; `link_or_copy` uses the same exclusive
  copy, and `_place`/`_link_new_copy` simply try the next candidate on a clash. JSON replies
  carry `Cache-Control: no-store`.
- **Consequences**: A malformed request is a 400, not a traceback. Chunked JSON clients work.
  Two Harbor processes may add photos at the same time without losing either file. Private API
  answers are re-fetched rather than replayed from the browser cache. The fallback copy path is
  used on filesystems without hard links; it costs one extra write only there.

### ADR-032: Preview cache is pruned to the live catalog
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: The preview cache under `.harbor/thumbs` keeps one JPEG per photo ever previewed.
  Deleting a photo forever, emptying the trash, or removing a file in File Explorer removed the
  catalog row but not its preview, so the hidden cache could accumulate dead bytes that the
  Storage tab could not attribute to any photo.
- **Decision**: `Thumbnailer.prune` deletes every cached preview whose SHA-256 is not in
  `Catalog.stored_hashes()`. `HarborApp` calls it once while opening the library, before server
  threads start; a preview a scanner still holds is skipped and retried on the next start.
  Previews are disposable: a live photo is regenerated on demand, and a deleted one never is.
- **Consequences**: The cache stays bounded by the live catalog and deleting photos reclaims
  their preview bytes at the next start. Startup scans the two-level cache directory once, which
  is proportional to the number of previews, and a missing cache directory simply has nothing
  to do.

### ADR-033: Startup cleanup only removes stale buffers
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: `PhotoStore.__init__` deleted every `.tmp_upload_*` in `.harbor/incoming` and
  `Downloads.clean` deleted every `.zip` in `.harbor/downloads`. A CLI import constructs a
  second `HarborApp` against the same library while the server runs, so its startup cleanup
  could delete the server's in-progress upload or a prepared download that still had a live
  token. The paths are per-library, not per-process.
- **Decision**: Cleanup is age-based: upload buffers older than six hours and download archives
  older than one hour may be removed, while younger files are presumed to belong to a running
  Harbor process and are left alone. A failed unlink is skipped and retried at the next start.
  Download tokens still live only in memory, so `clean` clears them as before.
- **Consequences**: Starting an import or a second Harbor window can no longer break an upload
  or download already in flight. An abandoned buffer can linger for up to its threshold instead
  of being removed immediately; it is still cleaned on a later start.

### ADR-034: Rejected profile writes and vanished archives leave no partial state
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: `ProfilesApi.update` renamed the person and their folder before validating a new
  password, and before the owner-key refusal, so a 400/403 response still applied the rename.
  `ProfilesApi.create` inserted the person before rejecting a bad password. And
  `Downloads.take` returned a token for a ZIP that had been deleted underneath it, which then
  failed with a 500 while serving.
- **Decision**: Validate the password (`check_new_password`) and the owner-key rule before the
  first rename or insert; validate a new profile's password before creating the person. A name
  and password change is still applied in two steps because a folder move and SQLite are not one
  transaction, but every validation failure now happens before either step. `Downloads.take`
  drops the token and returns None when its file is missing, which the API maps to 404.
- **Consequences**: A rejected profile request leaves the name, folder, person list and key
  untouched. A vanished download archive answers 404 instead of a broken transfer. A filesystem
  failure in the middle of a valid rename can still leave the folder and database disagreeing;
  the next `layout.prepare` reconciles what it can.

### ADR-035: ZIP entry names are unique case-insensitively
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Push 79 added a counter for repeated ZIP entry names, but `_entry_name` compared
  exact strings. `IMG.JPG` and `img.jpg` are distinct strings and became two entries, while
  Windows extraction treats them as the same name and one photo can overwrite the other.
- **Decision**: The set of used names is compared with `str.casefold()`, so the second name gets
  the existing SHA-8 prefix and further collisions get the same counter. The entry itself keeps
  its original case.
- **Consequences**: A downloaded ZIP keeps every photo on Windows, macOS and Linux. A
  case-only duplicate gains a hash prefix in its entry name; the library file name is unchanged.

### ADR-036: ZIP entry names are Unicode-normalization safe too
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Run 1 made ZIP names unique by casefolding, but `é` in NFC form and `e` plus a
  combining accent in NFD form are different strings with the same normalized name. macOS
  filesystems are normalization-insensitive, so extracting such a ZIP can still merge two
  photos.
- **Decision**: `_entry_name` compares `unicodedata.normalize("NFC", name).casefold()`. The
  entry name keeps its original characters; only the used-name key is normalized.
- **Consequences**: Case and normalization variants now receive the existing SHA-8 prefix.
  The delivered ZIP is safe on case- and normalization-insensitive filesystems.

### ADR-037: A future sync cursor is ignored, not replayed
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Wave 1 (push 74) rejected a new `sync/done` whose `started_at` was in the future,
  but a cursor recorded before that fix can still sit in the future. `sync/start` would return
  that future time minus clock slack, so a phone filtering photos after the cursor finds none
  until its clock catches up.
- **Decision**: `SyncApi.start` normalizes the stored cursor and the PC clock into one timezone
  frame and ignores a cursor more than `CLOCK_SLACK` in the future, returning
  `FIRST_SYNC_SINCE`. `SyncApi.done` uses the same `_comparable` helper.
- **Consequences**: An old skew causes one full rescan instead of a stalled sync. A cursor
  inside the ten-minute slack is still honoured; a naive and an aware cursor compare safely.

### ADR-038: Backup refuses a missing source
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: `mirror` and `verify` iterated a missing source folder as if it were empty. An
  unplugged library drive therefore produced "0 copied, 0 unchanged" or "0 checked, 0 missing"
  and looked like a clean backup; `DailyBackup` recorded no error and the Sync tab showed success.
- **Decision**: Both functions require `source.is_dir()` before scanning and raise the
  Error/Why/Fix triad when it is missing. A missing or disconnected library is recorded as a
  backup failure by `DailyBackup`, and the CLI exits 1.
- **Consequences**: The backup status can no longer claim success for a library it never read.
  A target that is missing is still refused separately (ADR-016); only a real source is copied.

### ADR-039: PWA installation is documented for secure contexts only
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: The PWA bullet said Chrome or Edge could install `http://<pc>:8642/` and run its
  service worker. Browsers require a secure context for both; a LAN address over plain HTTP is
  not one, so the claim holds only at `http://localhost` on the PC or behind HTTPS.
- **Decision**: Document the secure-context boundary: localhost on the PC can install and cache
  the shell; a phone on plain HTTP still gets the gallery but uses the Android app or HTTPS for
  an installed app. The service worker registration stays harmless where the browser refuses it.
- **Consequences**: The README no longer promises an install that a phone browser rejects. The
  gallery itself and the Android client are unchanged.

### ADR-040: The Android install page uses CSP-allowed external assets
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Every HTML reply carries `script-src 'self'` and `style-src 'self'`. The Android
  install page embedded both its metadata fetch and its whole stylesheet inline, so the browser
  blocked them: the version, size and checksum never replaced the fallback text, and the page
  rendered unstyled. The tests only checked the JSON endpoint.
- **Decision**: Move the fetch to `photo_harbor/web/android/meta.js` and the CSS to
  `style.css`, serve both from public `/android/...` routes with the right content type and
  `no-cache`, and reference them with normal `src`/`href` attributes. Regressions assert the
  page has no inline script or style, both files exist, and both routes serve them. The Android
  version constants in `build.py` and `MainActivity.java` are pinned together by a test so the
  update check cannot silently compare stale numbers.
- **Consequences**: The install page shows its build metadata and styling under the existing
  CSP. Two public static routes are added; missing assets answer 404 with the usual triad.

### ADR-041: Unknown-size Android shares upload chunked
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: `SyncEngine.share` skipped any item whose provider did not expose
  `OpenableColumns.SIZE` or a descriptor length. Many content providers stream fine without a
  length, and Harbor already accepts a chunked upload and hashes it as it arrives. The skip was
  misleadingly reported as "already on the PC".
- **Decision**: Only a genuinely empty item (`size == 0`) is skipped. An unknown size (`-1`) is
  uploaded with `HttpURLConnection.setChunkedStreamingMode`; a known size keeps the fixed-length
  path. The Android app, manifest, build metadata and sidecar move to 1.1/2, and a unit test
  pins those four version sources plus the committed APK's size and SHA-256.
- **Consequences**: A share from a size-less provider arrives instead of disappearing. Existing
  1.0 installs see the served 1.1 metadata and offer **Update Harbor**. The APK was rebuilt and
  signature-verified; the emulator share path was not rerun here.

### ADR-042: CLI OSErrors use the Error/Why/Fix triad
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: `backup --check` could raise an `OSError` from an unreadable or locked file. The
  CLI caught only `HarborError`, so the documented triad became a Python traceback and exit 1
  with no Fix line.
- **Decision**: `main` catches `OSError` after `HarborError` and prints a HarborError-shaped
  failure with the offending path and a permission/lock remedy. The exit stays 1; argparse
  misuse still exits 2.
- **Consequences**: A backup or import that hits an unreadable file explains how to recover
  instead of dumping a stack. The original exception text remains in the Why line.

### ADR-043: A full drive during upload is a clear 507
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: `PhotoStore._receive` checked free space before a known-length upload, but a
  chunked/unknown-length upload or a race could make `write`, `flush` or `fsync` raise
  `OSError`. That escaped the HTTP handler as a 500 traceback instead of the documented 507.
- **Decision**: The temp `open`, every block `write`, `flush` and `fsync` map `OSError` to a
  HarborError with status 507 and the drive remedy; the existing `finally` removes the temp.
- **Consequences**: A full drive answers 507 with Error/Why/Fix and stores nothing partial.
  The pre-flight free-space check stays as the fast path for known lengths.

### ADR-044: In-gallery Android download card and app 1.2
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: The APK and install page existed, but the signed-in gallery only linked to them.
  Users could not see whether the build was current, its checksum, or download it from the
  Setup view. The Android app also had no shortcut to the gallery and hid its last background
  result.
- **Decision**: Add a public `GET /api/android` that reports availability, version, versionCode,
  size, SHA-256 and page from the sidecar (available=false for a missing or malformed build).
  Setup's Android app card fetches it, shows the metadata, offers a direct APK download and a
  copy-install-link button. The app moves to 1.2/3 with **Open photo gallery** and a
  `last_background`/`last_background_at` summary recorded by `SyncJobService` and shown on
  resume. The APK is rebuilt and signature-verified.
- **Consequences**: The web UI is the single place to inspect and download the current build;
  a missing/malformed APK is a clear message instead of a broken link. The app reports its last
  background run and can open the gallery. Version constants, manifest and sidecar remain
  pinned by the existing integrity test.

### ADR-045: Android sources compile as UTF-8
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: The first 1.2 build showed the background status separator as `Â·` on the
  emulator. `javac` had used the Windows platform encoding for UTF-8 source text, so `·` (and
  other labels) were transcoded twice.
- **Decision**: Pass `-encoding UTF-8` to `javac` and move the APK to 1.2.1/4. Rebuild,
  signature-verify, install on the Android 14 emulator and recheck the background status.
- **Consequences**: Device text renders correctly; the version bump prompts existing 1.2
  installs to update. The sidecar and integrity test track the new build.

### ADR-046: Android handles partial and split media permissions
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: `startSync` checked only `READ_MEDIA_IMAGES`. A user who granted images but
  denied videos entered sync, and MediaStore returned an empty video cursor, so the app reported
  "Done" while silently omitting videos. Android 14 also offers selected-photo access through
  `READ_MEDIA_VISUAL_USER_SELECTED`, which the app declared but never accepted.
- **Decision**: `SyncEngine.hasMediaAccess` requires images *and* videos, or the Android 14
  selected-photo permission on API 34+. `MainActivity` requests every missing permission,
  including selected access, and rechecks after the result. `SyncEngine.sync` refuses to start
  when access is incomplete, and `syncCollection` still catches `SecurityException` as a
  defensive sentinel. The app moves to 1.3/5, is rebuilt and installed on the emulator.
- **Consequences**: A partial grant asks for the missing permission instead of silently
  skipping videos; a background job records "Photo access is missing" and is visible in the
  app. Test and Sync remain green on the emulator.

### ADR-047: Memories are a month-day gallery filter
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: An Immich comparison (`.aikit/immich_gap.md`) ranked Memories as the highest
  value/lowest cost missing feature. The gallery already stores local sort times and filters by
  date, so a separate memories table or job would duplicate state.
- **Decision**: Add `day=MM-DD` to `PhotoFilter`, validated with a real calendar (leap day
  allowed). The gallery's **On this day** button uses the browser's current month/day, composes
  with person/query/sort filters, and has an explicit empty message. No schema change.
- **Consequences**: Users get an Immich-style anniversary view with one indexed substring
  predicate. A separate memories image generation/selection feature remains future work.
  Tags, Archive, Places and near-duplicate review are recorded as the next candidates.

### ADR-048: Archive is per-person hidden state, not a folder
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: The Immich comparison ranked Archive as the next cheap, high-value gap. A move
  to a separate folder would break the readable `<Person>/<YYYY>/<YYYY-MM>` layout, complicate
  deduplication and could hide shared copies from other people.
- **Decision**: Add format 8 with an `archived(profile, sha256, archived_at)` table and a
  private mark per person. `PhotoFilter.archived` hides marks by default and shows only them
  when true; `POST /api/archive` archives or restores a validated single hash or batch. The
  rail **Archive** view, viewer and selection bar call it. `CopyIndex.forget` drops the leaving
  person's mark (and every mark when the last copy goes); a new format-7 catalog gains the table
  through `.v7.bak`-backed migration. Files never move.
- **Consequences**: Timeline, month counts, video/favorite counts and `On this day` hide
  archived photos while Storage and the catalog keep counting the bytes. Each person's archive
  is private; the owner archiving a shared photo does not hide it from the other person.

### ADR-049: Tags are per-person marks, not folders or file metadata
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: The Immich comparison ranks tags as the next core organization gap. Writing
  tags into EXIF/XMP would mutate originals and break the copy-once guarantee; a single global
  tag list would break the per-person privacy model.
- **Decision**: Add format 9 with `tags(profile, name)` and `photo_tags(tag_id, sha256)`.
  Creating a name is case-insensitive and idempotent per person. `GET /api/photos?tag=ID`
  narrows the gallery through the existing `PhotoFilter`; `GET/POST /api/tags` and
  `POST /api/photo-tags` list, create and mark tags. The rail lists only the viewer's tags with
  visible counts, and the viewer and selection bar add/remove marks. Archived photos leave the
  count, and `CopyIndex.forget` drops the leaving person's marks or every mark when the last
  copy goes.
- **Consequences**: Tags never move, copy or rewrite a file and compose with the other filters.
  A tag with only archived photos stays listed with a zero count, so it can be reused or
  cleaned up. Cross-person tag ids are rejected before any write.

### ADR-050: Places are coarse stored GPS points, not a map
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Immich's map is valuable, but map tiles need a network provider or a large
  offline asset, which conflicts with the home-network promise. The camera's GPS point is
  already inside many originals and is cheap to read once.
- **Decision**: Add format 10 with nullable `latitude`/`longitude` on `photos`, read from EXIF
  GPS at ingest (Pillow optional). `GET /api/outline` groups visible photos into one-decimal
  coordinate buckets (top 100); `GET /api/photos?place=LAT,LON` filters one bucket; the rail
  lists **Places** and Details shows the exact point. Archived photos leave place counts.
- **Consequences**: Users get a local, offline place browse without reverse geocoding or tiles.
  Names like "Athens" are deliberately not invented from coordinates; a future map can render
  the stored points without re-reading originals.

### ADR-051: Cameras are stored EXIF strings, not inferred models
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Camera/lens metadata is the next local search gap after Places. Deriving a
  shared camera identity from make/model or matching lenses would add guessing and migration
  complexity; the EXIF strings themselves are stable and human-readable.
- **Decision**: Add format 11 with nullable `camera`/`lens` on `photos`, read once at ingest
  through the optional Pillow path. `GET /api/outline` returns camera names with visible
  counts; `GET /api/photos?camera=NAME` exact-matches the stored make/model; the rail lists
  **Cameras**. Archived photos leave the count. Details keeps reading the original file for its
  full camera/lens facts.
- **Consequences**: A camera filter works offline and composes with every existing filter. An
  EXIF-less photo simply has no camera entry; no model inference or network lookup is claimed.

### ADR-052: Similar review groups exact perceptual hashes and never deletes
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Near-duplicate detection is the last high-value Immich gap, but automatic
  clustering and deletion can destroy a keeper. Existing photos also need hashing, which must
  not make every upload or server start expensive.
- **Decision**: Add format 12 with a `photo_hashes(sha256, dhash)` cache. **Similar** is a
  separate read-only tab: **Scan library** computes a 64-bit Pillow difference hash in bounded
  batches, stores `skip` for unreadable files and links each grouped photo to its original with
  no delete action. Groups require an exact hash match; archived photos are excluded.
- **Consequences**: Re-encoded and resized copies with the same perceptual hash are reviewable
  without SHA-256 equality, and nothing is deleted automatically. Crops or edits that change
  the hash need a future Hamming-distance pass; that can build on the same cache without a
  migration of originals.

### ADR-053: Similar review links hashes within four bits
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Exact dHash groups miss re-encoded or resized copies whose hash changes by a
  few bits. A full radius-8 pass was measured at 268 s for 50k hashes; the page must stay
  responsive.
- **Decision**: Treat the cached 64-bit hashes as a Hamming metric and build connected groups
  with radius 4. Split 64 bits into five bands of about 13 bits: a pair within four bits must
  share at least one exact band, so a band index finds every candidate without an O(n²) scan.
  The API reports `threshold: 4`; the UI explains the distance. No schema change and no delete
  action.
- **Consequences**: A 50k-hash grouping takes about 2.1 s on the development PC and catches
  small re-encode/resize changes. Wider-radius grouping would need a cached or precomputed
  index; the cache format leaves that open.
