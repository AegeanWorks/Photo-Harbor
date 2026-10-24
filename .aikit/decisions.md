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
