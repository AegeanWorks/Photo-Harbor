# Proposals: making the implicit state machines explicit (2026-11-08)

Ranked by (reachable harm) x (how many of UX, DX, AX it lifts) / (risk of the change).
Each proposal records what it changes, which of the three experiences it improves, and why
it is safe. **Verification method** for every "will not break" claim is stated.

---

## P1. Paging gets a `failed` state (fixes C1) - *accept*

**Change**: replace the bare `catch` in `loadMore` with a `state.paging` machine
(`idle|loading|exhausted|failed`); on failure set `failed`, stop re-entering, and render a
retry control. `resetPhotos` clears it.

**Evidence**: a Node harness extracting the real `loadMore`/`resetPhotos` measured **61
requests and 61 toasts from one user action**, and the loop never yielded to the event loop.

- **UX**: a broken endpoint becomes one visible, retryable message instead of a frozen grid,
  a toast storm, and an unresponsive tab.
- **DX**: the invariant "requests stop when there is nothing to load" becomes one field
  instead of relying on a promise's `finally`.
- **AX**: an agent reading `paging` knows the legal states; today it must infer that `next`
  staying non-null while `loading` is false means "failed".

**Risk**: low. Only the failure path changes; the success path keeps its generation guard.
**Verification**: harness must show 1 request + 1 retry control; suite must stay green.

---

## P2. Replacing the photo list closes the viewer (fixes C2) - *accept*

**Change**: `resetPhotos` closes the viewer when open. Keep `state.viewing` meaningful only
for the current list.

**Evidence**: every viewer action is guarded by `if (!photo) return` at 8 call sites, so a
stale index silently disables Favorite, Archive, Details, Add to album, Add tag, Cover,
Remove and Trash while the stage still shows the previous photo and `#viewer-download`
keeps a stale `href`.

- **UX**: no more "the button does nothing" after changing a filter; the overlay matches the
  list behind it.
- **DX**: one transition instead of eight defensive guards.
- **AX**: removes the only place where an index is valid for a list that no longer exists.

**Risk**: low. Closing on an explicit user action (a filter change) is expected behaviour.
**Verification**: new test that a scope change with the viewer open leaves `viewing === -1`;
existing viewer tests must pass.

---

## P3. Sign-out closes overlays and resets identity (fixes C3) - *accept*

**Change**: `showLogin` closes the viewer, compare overlay, drop zone and upload panel, and
clears `state.profile`, `state.selecting`, `state.selected`, `state.viewing`. Add an
in-flight guard on the login form.

**Evidence**: `#viewer` (z-index 50), `.compare` (85), `#drop` (70) and `#uploads` (40) are
all fixed-position and paint above the static `#login` card (app.css:69); `showLogin` resets
nothing; `start()` is reachable again without a reload.

- **UX**: session expiry with the viewer open currently shows a login form the user **cannot
  see**. This is the worst first impression in the app.
- **DX**: identity reset stops being per-call-site folklore.
- **AX**: "signed out" becomes one state instead of two DOM banners plus four fields that
  outlive it.

**Risk**: low-medium; touches sign-in flow, so the whole auth suite is the gate.
**Verification**: test that `showLogin` hides every overlay; existing login/session tests.

---

## P4. Bulk actions get a `busy` guard (fixes C4) - *accept*

**Change**: one `state.bulkBusy` flag set around the `batches()` loops; `renderSelection`
disables the bar while set.

**Evidence**: `renderSelection` disables only when `count === 0` (1217-1220); the five bulk
functions are `async` loops over `batches()` with the buttons left enabled.

- **UX**: a double-clicked "Move to trash" currently runs two confirmation dialogs and two
  identical POST sequences.
- **DX/AX**: one guard replaces five scattered assumptions.

**Risk**: low. **Verification**: test that a second call while set is a no-op.

---

## P5. One scope builder (fixes C7) - *accept*

**Change**: a single `scopeWith(kind, month, extra)` used by `setScope`, `selectPerson` and
`deleteAlbum`, so the field list cannot drift.

**Evidence**: a script compared the three literals. `deleteAlbum` omits **4** keys
(`start`, `end`, `format`, `missing`); `selectPerson` omits **2** (`format`, `missing`). A
date range or a format filter therefore survives a person switch and a delete.

- **UX**: switching person after filtering by format currently keeps the invisible format
  filter, so the new person's gallery is silently wrong.
- **DX**: one definition, so a new filter is added once.
- **AX**: an agent adding a filter cannot forget the two bypass sites.

**Risk**: low, but it changes what a person switch clears - which is the point.
**Verification**: test that all three paths produce identical key sets.

---

## P6. Failed first status fetch falls back to sign-in (fixes C8) - *accept*

**Change**: when `refreshStatus` fails in `start()`, call `showLogin()` instead of returning.

**Evidence**: `start()` returns at 2856 leaving **both** `#shell` and `#login` hidden - a
blank page with a single toast and no retry.

- **UX**: a blank page is the worst possible recovery state.
- **DX/AX**: removes the only "no view is showing" state.

**Risk**: very low. **Verification**: test that a failing status fetch leaves sign-in visible.

---

## P7. Scan `_full` becomes an `Event` (fixes B7) - *accept*

**Change**: `ScanSchedule._full` bool -> `threading.Event`.

**Evidence**: set from the UI thread (`run_now`) and read/cleared on the scan thread
(`scan.py:236-237`) with no lock.

- **UX**: a "Check all files" press can currently be lost.
- **DX/AX**: the wake-up semantics are already an `Event`; making the request one too removes
  a cross-thread bool.

**Risk**: very low. **Verification**: existing scan tests; a lost-wakeup test.

---

## P8. Runner unwinds a half-started server (fixes B9) - *accept*

**Change**: wrap the post-bind setup in `try/except` that calls `stop()` and re-raises.

**Evidence**: if `warmer.start()` or `schedule.start()` raises after the socket is bound,
`_server` stays set, so `running` is True with no working schedule and only `stop()` recovers.

- **UX/DX**: `running` cannot lie. **Risk**: low. **Verification**: inject a failing start.

---

## P9. Name the machines in one registry (codifies B1-B6, B10-B11, C6, C9-C10) - *accept*

**Change**: `.aikit/state_machines.md` (written) plus a short pointer in the README's
"what's inside" tree.

- **AX**: this is the single largest agent-facing win - an agent reads one document instead
  of re-deriving 19 lifecycles from 11 modules and 2 900 lines of JS.
- **DX**: reviewers get the same map.
- **UX**: indirect, but it is what keeps the fixes from regressing.

**Risk**: none (documentation only). **Verification**: link integrity gate.

---

## Rejected / deferred

### R1. Rewrite the client around a reducer - *deferred*

A real store with `dispatch` would eliminate C1-C10 by construction. But it is a rewrite of
2 900 lines of shipped, tested UI for no user-visible change beyond the fixes above, and this
project's evidence gates are built on static assertions over the current file shape.

**Decision**: defer. Take it when the UI next needs a feature that forces structural change.

### R2. Cancellation tokens for the similarity scan (C6) - *deferred*

Correct, but it needs a server-side job id and an abort endpoint; larger than this pass.
Recorded in the registry so it is not lost.

### R3. Crash-safe trash ordering (B6) - *rejected*

Writing the trash row before moving the file is the safer ordering: a stray row is
recoverable, a lost file is not. No change.

### R4. An explicit "sync in progress" marker (B2)

The hash-first protocol is idempotent, so a second phone re-reading a cursor is harmless.
A marker would add a stuck-forever state for one-phone households.

---

## Chosen set

**Accept**: P1-P9. All are reachable-defect fixes or documentation, none changes a healthy
path's behaviour, and each has a named verification.

**Deferred**: R1, R2. **Rejected**: R3, R4 with reasons.

Order of implementation is P9 (already written) -> P2, P6, P1 (client correctness) ->
P4, P5, P3 (client invariants) -> P7, P8 (backend).
