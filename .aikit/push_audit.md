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

## Status

- Runs completed: 1 (pushes 78-80).
- Next run: last 6 pushes, adding pushes 75-77.
