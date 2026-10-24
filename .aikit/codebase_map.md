# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `29`
- **Total Classes**: `48`
- **Total Top-Level Functions**: `36`
- **Total Class Methods**: `144`
- **Total Source Lines**: `2067`

---

## 📦 Modules & Exported Symbols

### [`photo_harbor/__init__.py`](photo_harbor/__init__.py)
> *photo-harbor: a self-hosted photo server that an iPhone feeds through Apple Shortcuts.*

**Size**: `3` lines (`116` bytes)

---

### [`photo_harbor/__main__.py`](photo_harbor/__main__.py)
> *Command line: ``python -m photo_harbor serve | key | backup``.*

**Size**: `92` lines (`3817` bytes)

**Functions:**
- `def _parser()`
- `def _serve(args, settings)`
- `def main(argv)`

---

### [`photo_harbor/app.py`](photo_harbor/app.py)
> *Wires one library's storage, APIs and web page into a Router.*

**Size**: `71` lines (`2812` bytes)

**Classes:**
- `class HarborApp` - *Owns the database connection; ``close`` releases it.*
  - Method `.__init__(settings, port, thumbs, now)`
  - Method `._register(sync, library, setup)`
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
> *Who may talk to the server: devices on the home network that present the library key.*

**Size**: `42` lines (`1698` bytes)

**Classes:**
- `class KeyGuard`
  - Method `.__init__(key)`
  - Method `.admits(request)`
  - Method `.login(request)` - *Trade the key for a long-lived cookie so the gallery need not ask again.*

**Functions:**
- `def is_home_network(address)` - *Private, loopback and link-local addresses; the internet is refused even if port-forwarded.*

---

### [`photo_harbor/backup.py`](photo_harbor/backup.py)
> *A second copy of the library's originals on another drive, so one disk failure loses nothing.*

**Size**: `73` lines (`2563` bytes)

**Classes:**
- `class BackupReport`
- `class DailyBackup` - *Mirrors at start-up and every 24 hours on a background thread while the server runs.*
  - Method `.__init__(source, target, log)`
  - Method `.start()`
  - Method `.stop()`
  - Method `._run()`

**Functions:**
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
> *The index of stored originals, keyed by SHA-256.*

**Size**: `86` lines (`3491` bytes)

**Classes:**
- `class Catalog`
  - Method `.__init__(db)`
  - Method `.add(record)` - *Insert ``record``; False when its hash is already catalogued. A path another record*
  - Method `.get(sha256)`
  - Method `.page(offset, limit, narrow)` - *Records newest first by taken time, falling back to received time.*
  - Method `.outline()`
  - Method `.stats()`

**Functions:**
- `def _to_record(row)`
- `def _where(narrow)`

---

### [`photo_harbor/config.py`](photo_harbor/config.py)
> *The library's settings file: format version and the upload key the phone presents.*

**Size**: `68` lines (`2471` bytes)

**Classes:**
- `class Settings`
  - Property `.state_dir`

**Functions:**
- `def _config_path(library)`
- `def _parse(path)`
- `def load_or_create(library)` - *Read the settings, restoring ``.bak`` if the file is damaged; create them on first run.*
- `def rotate_key(library)` - *Write a fresh random key; a phone holding the old key is refused from now on.*

---

### [`photo_harbor/database.py`](photo_harbor/database.py)
> *The SQLite file behind the catalog and the sync journal, with its format version.*

**Size**: `63` lines (`2052` bytes)

**Classes:**
- `class Database` - *One shared connection; every statement runs under ``lock`` so server threads take turns.*
  - Method `.__init__(path)`
  - Method `._open_schema(path)`
  - Method `.close()`

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

**Size**: `29` lines (`1127` bytes)

**Functions:**
- `def read_taken(path)` - *``YYYY-MM-DDTHH:MM:SS`` from EXIF DateTimeOriginal, or None without Pillow or a date.*

---

### [`photo_harbor/http_server.py`](photo_harbor/http_server.py)
> *The socket side: turns HTTP into a Request, runs the matched endpoint and sends its Reply.*

**Size**: `148` lines (`6570` bytes)

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

**Functions:**
- `def _refusal(status, message, why, fix)`

---

### [`photo_harbor/journal.py`](photo_harbor/journal.py)
> *What the phone did and when: uploads, finished syncs and photos the PC lacked at cleanup.*

**Size**: `54` lines (`2054` bytes)

**Classes:**
- `class SyncJournal`
  - Method `.__init__(db)`
  - Method `.record(at, kind, sha256, detail)`
  - Method `.last_sync()` - *The phone-reported start time of the latest sync that finished.*
  - Method `.counts_since(since)`
  - Method `.missing(limit)` - *Photos the phone holds that the PC still lacks, newest report first.*

---

### [`photo_harbor/library_api.py`](photo_harbor/library_api.py)
> *The endpoints the gallery reads: status, the photo list, originals and previews.*

**Size**: `105` lines (`4853` bytes)

**Classes:**
- `class LibraryApi`
  - Method `.__init__(store, catalog, journal, thumbs, now)`
  - Method `.status(request)`
  - Method `.photos(request)`
  - Method `.outline(request)` - *Months with photos, newest first, for the browser sidebar.*
  - Method `.media(request, sha256)`
  - Method `.thumb(request, sha256)`

**Functions:**
- `def _not_found(sha256)`
- `def _displayable(kind)` - *Images and videos show inline; anything else (HTML, SVG with scripts) only downloads.*
- `def photo_json(record)`
- `def _narrowing(request)`

---

### [`photo_harbor/messages.py`](photo_harbor/messages.py)
> *Transport-free request and reply values, so the API can be tested without sockets.*

**Size**: `80` lines (`2972` bytes)

**Classes:**
- `class Request`
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
> *Where an original lands on disk: a safe file name inside a YYYY/MM folder.*

**Size**: `48` lines (`1652` bytes)

**Functions:**
- `def safe_name(original)` - *A Windows-safe base name; a name that sanitises to nothing becomes ``photo``.*
- `def parse_taken(value)` - *ISO 8601 as Shortcuts formats it; anything unreadable counts as unknown.*
- `def month_folder(moment)`
- `def media_type(name)`

---

### [`photo_harbor/records.py`](photo_harbor/records.py)
> *Immutable values passed between the store, the catalog and the web layer.*

**Size**: `68` lines (`1627` bytes)

**Classes:**
- `class PhotoRecord` - *One stored original, identified by the SHA-256 of its bytes.*
  - Property `.sort_time`
  - Property `.is_video`
- `class UploadClaim` - *What the phone says about a file before its bytes are checked.*
- `class IngestResult` - *``status`` is ``stored`` for a new file or ``duplicate`` when the bytes were already held.*
- `class LibraryStats`
- `class PhotoFilter` - *Gallery narrowing: ``month`` is ``YYYY-MM``, ``query`` matches the file name, ``kind`` is*
- `class Outline` - *What the browser sidebar lists: ``(YYYY-MM, count)`` newest first, and the video count.*

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

### [`photo_harbor/setup_api.py`](photo_harbor/setup_api.py)
> *What the setup page shows: the address and key to type into the iPhone Shortcut.*

**Size**: `32` lines (`1013` bytes)

**Classes:**
- `class SetupApi`
  - Method `.__init__(key, port, address)`
  - Method `.details(request)`

**Functions:**
- `def lan_address()` - *The PC's address on the home network; connecting a UDP socket sends no packet.*

---

### [`photo_harbor/store.py`](photo_harbor/store.py)
> *Receives originals, proves their bytes against the phone's hash, and re-proves them on request.*

**Size**: `192` lines (`8805` bytes)

**Classes:**
- `class PhotoStore`
  - Method `.__init__(library, catalog, now, embedded_date)`
  - Method `.ingest(stream, length, claim)` - *Stream ``length`` bytes (None: until the stream ends) to disk; keep them only when the*
  - Method `.verify(sha256)` - *True only when the catalogued file exists and its bytes still hash to ``sha256``.*
  - Method `.locate(sha256)` - *``(path, record)`` of a stored original, or None.*
  - Method `._check_capacity(length)`
  - Method `._receive(stream, length, tmp)`
  - Method `._place(tmp, sha256, size, claim)`
  - Method `._repair(tmp, record)` - *Put verified bytes back where a catalogued original went missing or was damaged.*

**Functions:**
- `def local_now()`
- `def hash_file(path)`
- `def normalise_sha(value)` - *Lower-case hex, or HarborError when the text is not a SHA-256.*

---

### [`photo_harbor/sync_api.py`](photo_harbor/sync_api.py)
> *The endpoints the iPhone Shortcut calls: start, upload, done, and the cleanup's "has" check.*

**Size**: `73` lines (`3550` bytes)

**Classes:**
- `class SyncApi`
  - Method `.__init__(store, journal, now)`
  - Method `.start(request)` - *Tell the phone which photos to send: those created after the last finished sync.*
  - Method `.upload(request)`
  - Method `.has(request)` - *``answer`` is ``yes`` only after the PC re-hashes its copy; with ``report=1`` (the*
  - Method `.done(request)`

**Functions:**
- `def _stamp(moment)`

---

### [`photo_harbor/thumbs.py`](photo_harbor/thumbs.py)
> *Small JPEG previews, made only when the optional Pillow (and pillow-heif for HEIC) is installed.*

**Size**: `58` lines (`2056` bytes)

**Classes:**
- `class Thumbnailer`
  - Method `.__init__(cache_dir, pillow)`
  - Property `.enabled`
  - Method `.preview(record, original)` - *The cached preview, made on first request; None for videos or unreadable images.*

**Functions:**
- `def _load_pillow()` - *Pillow's Image and ImageOps modules, or None without Pillow. HEIC opens only when*

---

### [`tests/__init__.py`](tests/__init__.py)
**Size**: `0` lines (`0` bytes)

---

### [`tests/library_fixture.py`](tests/library_fixture.py)
> *A throwaway library for tests: temp folder, database, catalog, journal and store.*

**Size**: `36` lines (`1330` bytes)

**Classes:**
- `class Library`
  - Method `.__init__(test_case)`
  - Method `.put(data, name, taken)`

**Functions:**
- `def sha(data)`

---

### [`tests/test_http.py`](tests/test_http.py)
> *The server over a real socket on 127.0.0.1, as the Shortcut and the gallery use it.*

**Size**: `152` lines (`7601` bytes)

**Classes:**
- `class _NoPreviews`
  - Method `.preview(record, original)`
- `class ServerTest`
  - Method `.setUp()`
  - Method `.call(method, path, body, headers, key)`
  - Method `.upload(data, name, digest)`
  - Method `.test_a_full_sync_round()`
  - Method `.test_has_answers_yes_only_for_verified_photos()`
  - Method `.test_a_mismatched_hash_is_rejected_and_counted()`
  - Method `.test_calls_without_the_key_are_refused_but_the_page_loads()`
  - Method `.test_login_sets_a_cookie_that_opens_the_api()`
  - Method `.test_media_serves_ranges_for_video_scrubbing()`
  - Method `.test_photos_lists_newest_first_with_paging()`
  - Method `.test_a_chunked_upload_is_accepted()`
  - Method `.test_browsing_by_month_kind_and_name()`
  - Method `.test_a_browser_upload_needs_no_hash_and_keeps_a_non_ascii_name()`
  - Method `.test_a_non_media_upload_downloads_instead_of_rendering()`
  - Method `.test_a_second_server_cannot_share_the_port()`

---

### [`tests/test_naming.py`](tests/test_naming.py)
**Size**: `38` lines (`1386` bytes)

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
**Size**: `135` lines (`5435` bytes)

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
- `class ThumbnailerTest`
  - Method `.test_without_pillow_previews_are_off()`
- `class DamagedConfigTest`
  - Method `.test_both_copies_damaged_is_a_clear_error()`

**Functions:**
- `def temp_dir(test_case)`

---

### [`tests/test_store.py`](tests/test_store.py)
**Size**: `154` lines (`6950` bytes)

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
