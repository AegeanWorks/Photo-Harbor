# Push-by-push audit

The audit window expands three pushes at a time from the newest push backwards: the last 3,
then the last 6, then the last 9, until the window reaches the first push. Every run checks the
code, tests, docs and assets added by its new (older) pushes, then reruns the current suite and
gates. A run with a finding ends in a fix commit and a publish; a clean run records that it
found nothing.

Push numbers are the `update by push` entries in `git reflog show origin/master`, oldest first.
The audit end is push 80 (`63077b4`), the tip when this audit began; fix commits after it are the
audit output and do not extend the numbered target.

## Run 1 - pushes 78-80

- Range: `48fb669` (push 78), `e6f7397` (push 79), `63077b4` (push 80).
- Reviewed: login-brake reset on password change and owner reset; real calendar-date validation;
  sync foreground/naive clock comparison; ZIP entry-name counter; the four hardening commits from
  push 80 and the recorded UI evidence.
- Finding: `_entry_name` compared exact strings, so `IMG.JPG` and `img.jpg` became two ZIP
  entries even though Windows extraction treats them as one and can overwrite a photo.
- Fix: casefold the used-name set while keeping the original entry case; two-photo regression
  plus existing collision tests. ADR-035.
- Verification: 210 tests OK; project check 4/4 gates; strict check 4/4 with matching UI evidence.

## Run 2 - pushes 75-80

- Range: `9fcf232` (push 75), `15e35a7` (push 76), `e6b3e5a` (push 77), plus Run 1's pushes.
- Reviewed: unlimited search terms, real calendar-date rejection, ZIP counter, login-brake
  resets, sync clock comparison and the push-80 hardening.
- Finding: ZIP names were case-insensitive but not Unicode-normalization safe; `é` (NFC) and
  `e` + combining accent (NFD) can merge on macOS.
- Fix: NFC-normalize before casefolding in the used-name key; two-record regression. ADR-036.
- Verification: 211 tests OK; project check 4/4 gates.

## Run 3 - pushes 72-80

- Range: `c73fa38` (push 72), `e42534a` (push 73), `cb28579` (push 74), plus the last 6 pushes.
- Reviewed: reforge state, UI metadata, transient-log ignore, naive future cursor rejection,
  preview-warmer retry, plus the previous runs.
- Finding: a cursor recorded in the future before wave 1 was still returned by `sync/start`,
  stalling the phone until its clock caught up.
- Fix: compare cursor and PC clock in one timezone frame; ignore a cursor over the 10-minute
  slack and rescan once. Regression covers aware and naive future cursors. ADR-037.
- Verification: 212 tests OK; project check 4/4 gates.

## Run 4 - pushes 69-80

- Range: `79c3796` (push 69), `49ad061` (push 70), `4213a1c` (push 71), plus the last 9 pushes.
- Reviewed: PWA close-out, owner-only backup status, its Sync panel and runner wiring.
- Finding: `mirror`/`verify` scanned a missing source as empty, so an unplugged library drive
  looked like a clean backup and `DailyBackup` recorded success.
- Fix: require a real source directory before scanning; the status records the failure and the
  CLI exits 1. ADR-038.
- Verification: 213 tests OK; project check 4/4 gates.

## Run 5 - pushes 66-80

- Range: `366b391` (push 66), `88f0d92` (push 67), `63dc39d` (push 68), plus the last 12 pushes.
- Reviewed: Android update check and metadata, PWA manifest/icons/service worker, secure-context
  registration, plus the previous runs.
- Finding: the README claimed a phone could install `http://<pc>:8642/` and use its service
  worker; browsers require HTTPS or localhost for both.
- Fix: document the secure-context boundary and the Android/HTTPS alternatives. ADR-039.
  The code path was already harmless (registration failure is caught).
- Verification: 213 tests OK; project check 4/4 gates.

## Run 6 - pushes 63-80

- Range: `96e8409` (push 63), `911924d` (push 64), `cae2307` (push 65), plus the last 15 pushes.
- Reviewed: Android APK metadata sidecar, install page, public metadata route, update check,
  plus the previous runs.
- Finding: the install page's inline metadata script and inline stylesheet were blocked by the
  CSP (`script-src 'self'`, `style-src 'self'`), so version/checksum stayed hidden and the page
  was unstyled. Android version constants can also drift between build and app.
- Fix: external `/android/meta.js` and `/android/style.css`, routes and static tests; a guard
  test pins the two version declarations together. ADR-040.
- Verification: 215 tests OK; project check 4/4 gates; install page re-reviewed in Chromium with
  metadata rendered and no CSP/console errors.

## Run 7 - pushes 60-80

- Range: `3835304` (push 60), `6265014` (push 61), `a102c75` (push 62), plus the last 18 pushes.
- Reviewed: Android share fallback for an intent data URI, manifest/share-sheet wiring, the
  emulator verification notes and the scheduled `SyncJobService` path.
- Finding: none actionable. The fallback only adds a missing URI; an unreadable or size-less
  provider is still skipped by the existing size guard, and proving a change needs the emulator.
  The Python tree has no defect attributable to this batch.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 8 - pushes 57-59

- Range: `cacc760` (push 57), `b5d98d3` (push 58), `706132a` (push 59), plus the last 21 pushes.
  The Android client at push 56 was also reviewed while checking the share/upload path.
- Reviewed: native Android client, manifest/share target, scheduled job service, APK serving and
  install page, plus the previous runs.
- Finding: `SyncEngine.share` skipped every item whose provider reports no size; Harbor accepts
  chunked uploads, so those shares disappeared and were counted as "already on the PC".
- Fix: chunked upload for unknown sizes, 1.1/2 APK rebuilt and signature-verified, version and
  sidecar integrity pinned by a test. ADR-041.
- Verification: 215 tests OK; project check 4/4 gates; APK badging shows versionCode 2/1.1.

## Run 9 - pushes 54-80

- Range: `88e80e1` (push 54), `1a60456` (push 55), `eb04454` (push 56), `706132a` (push 59),
  plus the last 24 pushes.
- Reviewed: the accessible photo viewer (dialog semantics, initial focus, tab trap, Escape and
  arrow keys, focus return), the keyboard panel, the library pushes and the previous runs.
- Finding: none actionable. Focus returns to the tile, the trap filters hidden controls, arrow
  boundaries are disabled and the dialog carries `aria-modal`; no current regression found.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 10 - pushes 51-80

- Range: `43fc394` (push 51), `644a5bf` (push 52), `fb1130a` (push 53), plus the last 27
  pushes.
- Reviewed: search as a narrowing axis, multi-word matching, escaping, the title/count and
  "Show everything" reset, plus the previous runs.
- Finding: none actionable. Scope is preserved, every word is ANDed with the existing filters
  and the LIKE escape still protects `%` and `_`.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 11 - pushes 48-80

- Range: `edd9ffb` (push 48), `51194b1` (push 49), `dc86be3` (push 50), plus the last 30
  pushes.
- Reviewed: chosen album covers and fallback to newest, cover clearing on removal, format-7
  migration, the 10,000-hash selection endpoint and its batching in the gallery.
- Finding: none actionable. Cover validation, fallback and removal are consistent; hashes use
  the same filters/order and bulk writes stay at 500 per request.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 12 - pushes 45-80

- Range: `dc62cb2` (push 45), `104c819` (push 46), `61a53b5` (push 47), plus the last 33
  pushes.
- Reviewed: move/restore/delete/empty, shared-photo hard links, hash-verified restore, trash id
  validation and the format-6 migration.
- Finding: none actionable. A shared photo keeps the other person's link, restore re-ingests the
  bytes, and delete/empty remove only the caller's entry.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 13 - pushes 42-80

- Range: `228e4ed` (push 42), `aa48a33` (push 43), `713f456` (push 44), plus the last 36
  pushes.
- Reviewed: the inclusive date window, real-calendar validation, date/sort stacking and the
  stable newest/oldest/largest/smallest orders in the page and hash endpoints.
- Finding: none actionable. Both ends are included, an impossible day is a 400, and every order
  has a SHA tiebreaker used by both endpoints.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 14 - pushes 39-80

- Range: `49c3510` (push 39), `bf0e9ac` (push 40), `119342b` (push 41), plus the last 39
  pushes.
- Reviewed: backup verify by hash, missing source/target handling, mirror failures and the CLI
  boundary.
- Finding: an unreadable file in `backup --check` escaped as an `OSError` traceback because the
  CLI caught only `HarborError`.
- Fix: catch `OSError` in `main` and print the Error/Why/Fix triad with exit 1; regression covers
  the CLI. ADR-042.
- Verification: 216 tests OK; project check 4/4 gates.

## Run 15 - pushes 36-80

- Range: `6b8bb89` (push 36), `07031b2` (push 37), `8f9e2dd` (push 38), plus the last 42
  pushes.
- Reviewed: whole-library and per-person storage totals, shared-photo counting, largest files,
  disk warning and album cover/selection creation.
- Finding: none actionable. The whole library counts distinct files once; per-person shares count
  copies and flag sharing; trash is excluded from both.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 16 - pushes 33-80

- Range: `2f01b2b` (push 33), `e7764d2` (push 34), `f0133e0` (push 35), plus the last 45
  pushes.
- Reviewed: stored ZIPs for a selection or album, one-time tokens, expiry, size/free-space
  limits, unique entry names, missing-archive 404 and stale-archive cleanup.
- Finding: none actionable. Tokens are per person and one-time; entry names are case- and
  normalization-safe; an empty, oversized or vanished selection gives a clear refusal.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 17 - pushes 30-80

- Range: `a4b0eb5` (push 30), `b25061a` (push 31), `ba5a978` (push 32), plus the last 48
  pushes.
- Reviewed: batch favorite/album/trash/download flows, the 500-hash server cap, selection
  clearing, and file/EXIF details with and without Pillow.
- Finding: none actionable. Batch writes validate the whole chunk before writing; details fail
  soft to file facts when Pillow or EXIF is unavailable.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 18 - pushes 27-80

- Range: `491347b` (push 27), `4a89872` (push 28), `02a4d50` (push 29), plus the last 51
  pushes.
- Reviewed: album task close, the committed UI contract and the no-findings reforge run.
- Finding: none; no code or contract change beyond the already-validated `.aikit/ui.json`.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 19 - pushes 24-80

- Range: `b8281a0` (push 24), `4528f0f` (push 25), `fce2e21` (push 26), plus the last 54
  pushes.
- Reviewed: the personal albums/favorites tables, unique names, membership/favorite bulk
  writes, stale-row hiding and the format-4 to 5 migration.
- Finding: none actionable. Album names are unique per person, deletes keep photos, and stale
  catalog rows are excluded from counts and members.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Run 20 - pushes 21-80

- Range: `df65a88` (push 21), `362fb38` (push 22), `f192f61` (push 23), plus the last 57
  pushes.
- Reviewed: reforge completion and stage records; no application code or contract changed.
- Finding: none; the records are consistent and the current gates are green.
- Verification: 215 tests OK; project check 4/4 gates; no code change.

## Status

- Runs completed: 20 (pushes 21-80).
- Next run: last 63 pushes, adding pushes 18-20.
