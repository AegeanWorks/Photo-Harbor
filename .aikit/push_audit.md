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

## Run 8 - pushes 57-80

- Range: `eb04454` (push 57), `cacc760` (push 58), `b5d98d3` (push 59), plus the last 21 pushes.
- Reviewed: native Android client, manifest/share target, scheduled job service, APK serving and
  install page, plus the previous runs.
- Finding: `SyncEngine.share` skipped every item whose provider reports no size; Harbor accepts
  chunked uploads, so those shares disappeared and were counted as "already on the PC".
- Fix: chunked upload for unknown sizes, 1.1/2 APK rebuilt and signature-verified, version and
  sidecar integrity pinned by a test. ADR-041.
- Verification: 215 tests OK; project check 4/4 gates; APK badging shows versionCode 2/1.1.

## Status

- Runs completed: 8 (pushes 57-80).
- Next run: last 27 pushes, adding pushes 54-56.
