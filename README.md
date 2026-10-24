# photo-harbor

[![Built with AIKit](https://img.shields.io/badge/built%20with-AIKit-6f42c1)](https://github.com/Aegean-E/AIKit)

Self-hosted photo server for Windows: an iPhone sends new photos over home Wi-Fi through Apple Shortcuts, no app needed, with a verified-hash cleanup and a gallery.

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10 or newer (standard library only). Optional: `pip install pillow pillow-heif` for HEIC thumbnails in every browser.
- **Canonical Regression Shield Gate**:
  ```bash
  python -m unittest discover -s tests -t .
  ```
- **Try it now** (from this folder):
  ```bash
  python -m photo_harbor serve
  ```
  Open `http://localhost:8642` and sign in with the key it prints. When Windows Firewall asks,
  allow Python on **Private networks** so the iPhone can reach it.

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status photo-harbor` |
| Phase 4: every gate | `python aikit.py check photo-harbor` |
| Repair memory and map, then check | `python aikit.py fix photo-harbor` |
| Resume an interrupted task | `python aikit.py resume photo-harbor` |

## 💡 How It Works

- **No iPhone app.** Two Shortcuts built in Apple's Shortcuts app call the server. The gallery's
  **Setup** tab lists every action, with the server address and key ready to copy.
- **Automatic on home Wi-Fi.** Automations run *Harbor Sync* when the phone joins the home
  network and when it is plugged in. The Shortcut stops at once on any other network.
- **Only what is new is sent.** `POST /api/sync/start` returns the time of the last finished
  sync (minus 10 minutes of clock slack). The Shortcut asks `GET /api/has` before each upload,
  so photos already on the PC are only hashed, never re-sent. The sync is marked done only if
  every upload succeeded.
- **Every byte is proven.** The phone sends the SHA-256 of each file with it. The PC streams the
  upload to a temporary file, hashes it, and keeps it only if the hashes match. Then it fsyncs
  the file and moves it into `photos/YYYY/MM/` under its original name. A name clash with different
  bytes gets a hash suffix; identical bytes are stored once.
- **Deletion only after a fresh check.** *Harbor Cleanup* asks `GET /api/has` for each phone photo
  older than 30 days. The PC answers `yes` only after re-hashing its own copy. Only those photos
  are deleted, and iOS asks once to confirm. A `no` uploads the photo instead and appears under
  **Sync → On the iPhone, not yet on the PC** until it arrives.
- **Home network only.** Requests from public IP addresses are refused even if a router forwards
  the port. Every API call needs the library key, sent as `X-Harbor-Key` or by the gallery's
  sign-in cookie.
- **A library browser.** The gallery has a sidebar of years and months with counts, a Videos
  filter and search by file name; on a phone the sidebar becomes a scrolling row of chips. Days
  are labelled in the browser's language. Click any photo for a full-screen viewer (arrow keys,
  swipe, download the original).
- **Upload from any browser.** Drop files on the page or press **Upload**, from the PC or from
  the iPhone's photo picker when the Shortcut is not set up. Browser uploads need no hash: the
  PC computes it. Their date is the phone's, else the EXIF capture date (with Pillow), else the
  file's modified time.
- **Second copy.** `--backup-to E:\HarborBackup` mirrors the originals at start-up and every 24
  hours. It never deletes anything in the backup.

### Commands

```text
python -m photo_harbor [--library DIR] serve [--port 8642] [--host 0.0.0.0] [--backup-to DIR]
python -m photo_harbor [--library DIR] key [--new]      # print, or replace, the Shortcut key
python -m photo_harbor [--library DIR] backup --to DIR  # one-off mirror to another drive
```

The default library is `%USERPROFILE%\Pictures\Harbor`. Errors print `Error:`, `Why:` and `Fix:`
and exit 1; usage errors exit 2.

### HTTP API

| Call | Purpose |
|---|---|
| `POST /api/sync/start` | `{since, started_at}`: which photos to send |
| `POST /api/upload` | raw file body; headers `X-Name` (may be percent-encoded), optional `X-Sha256`, `X-Taken`, `X-Modified`. `{status: stored\|duplicate, answer: yes}` |
| `GET /api/has?sha256=…[&name=…&report=1]` | `{present, answer: yes\|no}` after re-hashing the PC's copy |
| `POST /api/sync/done` | JSON `{started_at}`: records a finished sync |
| `GET /api/status`, `GET /api/outline` | counts, sync state, months with photos |
| `GET /api/photos?offset=&limit=[&month=YYYY-MM&kind=photo\|video&q=name]` | gallery page, newest first |
| `GET /media/<sha256>`, `GET /thumb/<sha256>` | original (with byte ranges) and JPEG preview |

## 📦 What's Inside

```text
photo-harbor/
├── .aikit/                   <- this project's memory: record, ledger, decisions
├── .gitignore
├── LICENSE                   <- GNU AGPL-3.0
├── README.md
├── photo_harbor/
│   ├── __init__.py           <- package version
│   ├── __main__.py           <- `python -m photo_harbor` commands
│   ├── app.py                <- wires storage, APIs and the web page into routes
│   ├── atomic_file.py        <- temp + fsync + replace placement
│   ├── auth.py               <- home-network check, key and sign-in cookie
│   ├── backup.py             <- mirror to a second drive, daily thread
│   ├── body_readers.py       <- Content-Length and chunked request bodies
│   ├── catalog.py            <- index of stored originals by SHA-256
│   ├── config.py             <- settings file with the library key
│   ├── database.py           <- SQLite file and its format version
│   ├── errors.py             <- the Error/Why/Fix triad
│   ├── exif_dates.py         <- capture date from EXIF, when Pillow is installed
│   ├── http_server.py        <- HTTP handling, byte ranges, security headers
│   ├── journal.py            <- uploads, finished syncs, photos reported missing
│   ├── library_api.py        <- status, month outline, filtered photo list, originals, previews
│   ├── messages.py           <- Request and Reply values, Range parsing
│   ├── naming.py             <- safe file names, month folders, media types
│   ├── records.py            <- frozen value objects
│   ├── router.py             <- method + path routing
│   ├── setup_api.py          <- address and key for the Setup tab
│   ├── store.py              <- hash-verified ingest and re-verification
│   ├── sync_api.py           <- the endpoints the Shortcuts call
│   ├── thumbs.py             <- optional Pillow previews
│   └── web/                  <- gallery and browser: index.html, app.css, app.js, icon, manifest
└── tests/
    ├── __init__.py
    ├── library_fixture.py    <- a throwaway library for tests
    ├── test_http.py          <- the server over a real socket
    ├── test_naming.py
    ├── test_parts.py
    └── test_store.py
```

Library layout: `photos/YYYY/MM/<original name>` holds the originals untouched;
`.harbor/` holds `config.json`, `catalog.sqlite3`, `incoming/` and `thumbs/`.

## ⚠️ Limits

- The PC must be on, awake and on the same Wi-Fi.
- iOS always asks before Shortcuts deletes photos. Deleted photos stay in *Recently Deleted* for
  30 days. With iCloud Photos on, deleting also removes them from iCloud.
- Very large videos may need more than one run because Shortcuts limits how long one run takes.
- Thumbnails need Pillow. Without them, Safari still shows HEIC originals; other browsers show a
  placeholder.

## 📜 License

GNU Affero General Public License v3.0; see [LICENSE](LICENSE).
