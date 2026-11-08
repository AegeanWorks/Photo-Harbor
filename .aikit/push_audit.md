# Push-by-push audit

The audit window expands three pushes at a time from the newest push backwards: the last 3,
then the last 6, then the last 9, until the window reaches the first push. Every run checks the
code, tests, docs and assets added by its new (older) pushes, then reruns the current suite and
gates. A run with a finding ends in a fix commit and a publish; a clean run records that it
found nothing.

Push numbers are the `update by push` entries in `git reflog show origin/master`, oldest first.

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

## Status

- Runs completed: 4 (pushes 69-80).
- Next run: last 15 pushes, adding pushes 66-68.
