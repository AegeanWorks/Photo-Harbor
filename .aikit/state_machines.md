# Implicit state machines (2026-11-08)

An implicit state machine is a lifecycle whose states are spread across loose booleans,
sentinel strings, nullable columns or DOM attributes, with transitions written at every call
site instead of in one place. Each entry below records the states, who owns the truth, the
transitions, and the concrete fault that follows from not having it written down.

Every claim marked **verified** was reproduced from the shipped code, not inferred from
reading it. Verification method is stated per entry.

Legend for the decision column:

- **fix** - reachable defect; the proposal corrects it
- **codify** - no live defect, but the machine is worth naming so readers stop re-deriving it
- **document** - real state, genuine ambiguity, deliberately left as-is

---

## Backend (Python)

### B1. Ingest result — `stored` / `duplicate` / `rejected`

- **States**: stored, duplicate, rejected (rejections are a raised `HarborError`, not a return)
- **Truth**: `PhotoStore._place` returns `IngestResult(status)`; `store.py:246-275`; the
  rejection state exists only as an exception, logged by `sync_api.upload` (`sync_api.py:79-82`)
- **Transitions**: received -> hashed -> `_place` -> stored | duplicate; anything raised becomes
  rejected
- **Illegal combos**: `duplicate` carries `self._catalog.get(sha256) or record`, so a duplicate
  whose catalog row vanished returns the *incoming* record - a subtle "duplicate that is not
  the stored record" state
- **Decision**: **codify** - three states in one enum-shaped value is fine; the fallback
  deserves a comment, not a rewrite

### B2. Sync cursor — first-sync / caught-up / future-skew

- **States**: never-synced, syncing, finished, cursor-in-the-future
- **Truth**: the `events` table (`sync_done` rows), one per profile; `journal.last_sync`,
  `sync_api.start` (`sync_api.py:57-68`)
- **Transitions**: `start` reads the cursor; `done` writes one. A cursor more than 10 minutes
  ahead is ignored and the next sync rescans
- **Illegal combos**: a `start` with no matching `done` leaves no state at all - there is no
  "sync in progress" marker, so two phones syncing at once both read the same cursor
- **Decision**: **document** - the design is deliberate (idempotent, hash-first); an in-progress
  marker would add a failure mode for one-phone households

### B3. Download token — prepared / live / taken / expired / stale

- **States**: live (token + file), taken (token consumed, file streamed), expired (TTL),
  stale (file older than an hour at startup)
- **Truth**: `Downloads._tokens` in memory only, plus files under `.harbor/downloads`;
  `downloads.py:107-131`
- **Transitions**: `prepare` -> live; `take` -> taken; expiry timer -> expired; `clean` on
  startup -> stale removed
- **Illegal combos**: a token is dropped *before* the file is streamed (`take` pops at
  `downloads.py:124-125`), so a failed stream loses the download with the token already gone.
  Deliberate: it is one-time by design
- **Decision**: **codify** - states are already clear in one small class; add the explicit
  `consume=` distinction to the docstring (done in ADR-076)

### B4. Login brake — open / counting / locked

- **States**: open, counting (1..4 failures), locked (5 failures, 5 minutes)
- **Truth**: `LoginBrake._failures` dict in memory; `accounts.py:131-161`
- **Transitions**: `failed` increments, `passed` clears, `check` raises 429 while locked, and
  the counter self-clears after the window
- **Illegal combos**: none reachable - but the state is per-process, so a restart unlocks
- **Decision**: **codify** - three states, one class; worth naming for AX so an agent does not
  add a second brake

### B5. Session — absent / valid / expired / revoked

- **States**: absent (no cookie), valid, expired (past `expires_at`), revoked (row deleted)
- **Truth**: `sessions` table; active state is derived on every request by
  `Sessions.find` (`accounts.py:109-116`) filtering `expires_at > now`
- **Transitions**: `start` inserts, `close(token)` deletes one, `close(profile, keep)` deletes
  the rest on a password change
- **Illegal combos**: none - expiry is a filter, not a mutation, so a stale row is harmless
- **Decision**: **codify** - the cleanest machine here; name it so nobody "optimises" the
  expiry filter into a delete that breaks the password-change flow

### B6. Trash entry — active / trashed / restored / deleted

- **States**: active (a `copies` row), trashed (a `trash` row + file under `.harbor/trash`),
  restored (back through ingest), deleted (both gone)
- **Truth**: split between `copies` and `trash` tables; `trash.py:28-98`
- **Transitions**: `move` writes the trash row then moves the file then forgets the copy;
  `restore` re-ingests then forgets the trash row; `delete` unlinks then forgets
- **Illegal combos**: `move` writes the trash row *before* the file move (`trash.py:41-51`).
  If the move fails it compensates (`trash.py:54-62`), but a crash between the two leaves a
  trash row with no file and a copy still catalogued
- **Decision**: **document** - the write-ahead ordering is the safer choice for crash
  recovery (a stray row is recoverable, a lost file is not); no change

### B7. Scan schedule — first-run / reconcile / full-check-due

- **States**: never-checked, reconcile-only, full-check-due, checking
- **Truth**: derived from the `events` table (`checked` rows) plus `ScanSchedule._full`;
  `scan.py:206-241`
- **Transitions**: `_due_check` writes a placeholder `checked` event on first run, returns
  due after a week; `run_now(full=True)` sets `_full`
- **Illegal combos**: `_full` is a plain bool mutated from the UI thread and read on the scan
  thread without a lock (`scan.py:196-198` vs `236-237`)
- **Decision**: **fix** - make `_full` an `Event` so the flag cannot be lost between a set and
  a clear (cheap, no behaviour change)

### B8. Similar rebuild — idle / running / failed

- **States**: idle, running, failed (error retained)
- **Truth**: `SimilarBuilder._thread` + `_error`, under `_lock`; `similar_builder.py:14-38`
- **Transitions**: `start` refuses while alive; `_run` sets `_error` on failure
- **Illegal combos**: `running()` returns False the instant the thread dies, so a caller that
  polls `running()` then `error()` can miss both between the poll and the read. Benign here
  because the client polls the HTTP endpoint, which reads both under one lock
- **Decision**: **codify**

### B9. Server runner — stopped / starting / running / stopping

- **States**: stopped, starting, running, stopping
- **Truth**: `ServerRunner._server`/`_thread` (`runner.py:41-92`)
- **Transitions**: `start` refuses if already set; `stop` clears all
- **Illegal combos**: `start` can fail *after* binding (e.g. `warmer.start()` or
  `schedule.start()` raising), leaving `_server` set and `running` True with no working
  schedule; `stop` is the only recovery
- **Decision**: **fix** - wrap the post-bind setup so a failure calls `stop()` and re-raises,
  so "running" is never true for a half-started server

### B10. Schema version — current / migratable / too-new / corrupt

- **States**: missing (0), migratable (1..12), current (13), too-new (>13), corrupt
- **Truth**: `PRAGMA user_version`; `database.py:292-308`
- **Transitions**: `_open_schema` applies an upgrade chain, refusing too-new
- **Illegal combos**: none - refusal is explicit and the file is left untouched
- **Decision**: **codify** - a model of what this document is for

### B11. Legacy layout — old / moved / removed

- **States**: none, files-under-`photos/`, moved
- **Truth**: `copies.rel_path LIKE 'photos/%'`; `layout.py:116-137`
- **Transitions**: `prepare` -> `_move_legacy` moves one file at a time
- **Illegal combos**: a missing source is skipped (`layout.py:127-128`), so an interrupted run
  simply continues; the row stays until a later run finds the file
- **Decision**: **codify** - resumable by construction

---

## Client (`photo_harbor/web/app.js`)

The client has exactly one mutable store, `state` (app.js:9-20), plus `uploads` (2099) and
`login` (2812). There is no transition function: every handler writes fields directly and
every reader re-derives the invariants.

### C1. Paging — idle / loading / exhausted / failed

- **States**: idle, loading, exhausted (`next === null`), **failed** (missing)
- **Truth**: `state.next` / `state.loading` / `state.generation`; app.js:342-377
- **Transitions**: `resetPhotos` bumps generation and resets; `loadMore` guards on `loading`,
  drops a stale generation, sets `next`
- **Illegal combos**: there is no failed state. On error `handle(error)` shows a toast, `next`
  is left untouched, and `finally` re-enters `loadMore` when the sentinel is near the bottom
  (`app.js:358-359`)
- **Verified**: extracted the real `loadMore`/`resetPhotos` into a Node harness with a stub DOM
  and a failing `api()`. **One `resetPhotos()` produced 61 requests and 61 toasts** before the
  harness capped it, and the loop never yielded to the event loop (the first attempt had to be
  killed after 60 s). Recovery works once the endpoint is healthy.
- **Decision**: **fix** - add a `failed` state that stops the loop and offers a retry

### C2. Viewer — closed / open / stale-index

- **States**: closed (`viewing === -1`), open (`viewing` valid), **stale** (`viewing` points
  past a list that was replaced)
- **Truth**: `state.viewing` + `#viewer.hidden` + `body.style.overflow` + focus; app.js:2241-2279,
  2516-2527
- **Transitions**: `openViewer` in; `closeViewer` out; `resetPhotos` and `setScope` **replace
  the list without closing the viewer**
- **Illegal combos**: verified by reading the guarded call sites - every viewer action starts
  `const photo = state.photos[state.viewing]; if (!photo) return;` (2356, 2375, 2336, 2401,
  2432, 2472, 2488, 2501), so Favorite, Archive, Details, Add to album, Add tag, Cover,
  Remove and Trash all become **silent no-ops** while the stage still shows the old photo and
  `#viewer-download` keeps a stale `href`
- **Decision**: **fix** - close the viewer whenever the list it indexes is replaced

### C3. Sign-in — signed-out / signing-in / owner / guest

- **States**: signed-out, signing-in, owner, guest
- **Truth**: `state.owner` / `state.me` / `state.people` / `state.profile` **plus** two DOM
  banners (`#shell.hidden`, `#login.hidden`) with `loggedIn` derived from the DOM
- **Transitions**: `showLogin` (2823) from any 401; submit -> `start()` (2851)
- **Illegal combos**: `showLogin` resets **none** of `state.*` and closes **no** overlay. The
  viewer (z-index 50), compare (85), drop (70) and the upload panel (40) all paint above the
  static `#login` card (app.css:69), and `start()` is reachable again without a reload, so
  `state.profile` survives a change of identity
- **Decision**: **fix** - close overlays and reset identity fields on sign-out; add an
  in-flight guard so a double submit cannot run `start()` twice

### C4. Selection — off / on-empty / on-some

- **States**: off, on-with-none, on-with-some
- **Truth**: `state.selecting` + `state.selected` + `#select-bar.hidden` + per-tile class
- **Transitions**: `setSelecting`, `clearSelected`, `toggleSelected`, `selectLoaded`,
  `selectMatching`; app.js:1166-1246
- **Illegal combos**: `selectLoaded`/`selectMatching` never check `state.selecting`, and the
  bulk family (`bulkFavorite` 1256, `bulkArchive` 1280, `bulkAlbum` 1301, `bulkTag` 1318,
  `trashPhotos` 1440) has **no busy guard** - `renderSelection` only disables on `count === 0`
  (1217-1220), so a double click runs the whole POST sequence twice
- **Decision**: **fix** - add a `busy` state to the bulk family and disable the bar while set

### C5. Uploads — idle / running / appended / finished

- **States**: idle, running, running+appended, finished
- **Truth**: `uploads` counters + per-row classes + `#uploads.hidden`; app.js:2099-2217
- **Transitions**: `enqueue` -> `runUploads` -> three lanes -> finalise
- **Illegal combos**: the panel header re-evaluates `uploadTarget()` at render time (2138,
  2197) while each item's destination was frozen at enqueue (2182), so changing the person
  filter mid-run mislabels files already queued elsewhere. Appending mid-run keeps `done` and
  grows `total`, so the bar jumps backwards
- **Decision**: **fix** - render the frozen label, and only reset counters when starting fresh

### C6. Similar scan/build — idle / scanning / building / failed

- **States**: idle, scanning, building, failed
- **Truth**: `state.similarTimer` + `data.building`/`build_error` + button disabled/label + local
  scan counters that are not in `state` at all; app.js:1497-1613
- **Transitions**: `loadSimilar` arms the poll, `scanSimilar` loops up to 100 batches,
  `startSimilarBuild` starts the server job, `show()` clears the timer
- **Illegal combos**: two independent writers of one status line (`scanSimilar` at 1567, the
  poll at 1501); the scan is **not** cancelled by leaving the view; a failed build leaves the
  button stale because only `loadSimilar` writes it
- **Decision**: **codify** - name the states and give the scan an abort flag; the full
  redesign is larger than this pass

### C7. Scope filter — all / one-of-many / plus-query / plus-date

- **States**: all, plus exactly one discriminator (month, kind, favourite, archived, album, tag,
  place, camera, lens, missing, format, day), plus optional `query` and date range
- **Truth**: `state.scope` (14 nullable fields) + `state.query` + `state.profile`; `setScope`
  rebuilds atomically (518-528) but `deleteAlbum` (1142) and `selectPerson` (700) rebuild
  **literal** objects that omit `missing` and `format`
- **Transitions**: `setScope` is the good one; the two literals bypass it
- **Illegal combos**: three readers disagree about "narrowed" (`renderScope` 430, `markScope`
  488, `narrowed` 446); `state.query` is never cleared by `setScope`
- **Decision**: **fix** - route every scope rebuild through one builder so the field list cannot
  drift again

### C8. Active view — one of 13

- **States**: one of 13 views
- **Truth**: 13 `hidden` flags set in a loop (2726-2729) + `aria-selected` + `localStorage`
- **Transitions**: `show(view)` only; `start()` returns early on a failed status fetch, leaving
  **both** `#shell` and `#login` hidden (2856) - a blank page with one toast
- **Decision**: **fix** - fall back to the sign-in screen when the first status fetch fails

### C9. Popover menus — closed / open, nine times

- **States**: closed, open, per popover
- **Truth**: nine independent `hidden` booleans plus mirrored `aria-expanded` attributes
- **Transitions**: mutual exclusion is hand-coded at each opener (1820, 1845, 1870, 536, 2341,
  2399, 2431) - O(n^2) edit sites for one invariant
- **Illegal combos**: `toggleTagMenu` (2431) hides the album panel but does not reset
  `#viewer-album-add`'s `aria-expanded`, so the button reports expanded with no panel
- **Decision**: **fix** the aria leak; **codify** the rest

### C10. Day virtualisation — layout-only / rendered / frame-scheduled

- **States**: layout-only (geometry computed), rendered (section in DOM), frame scheduled
- **Truth**: `state.dayEls`/`dayList`/`dayWindowFrame` + per-group flags; app.js:192-307
- **Transitions**: `layoutDays` -> `renderWindow` -> `renderDay`/`unrenderDay`
- **Illegal combos**: `addPhotos` renders a day before `layoutDays` (307 then 309), so tiles are
  briefly laid out against the previous column count; `ResizeObserver` watches the topbar, not
  the grid
- **Decision**: **document** - cosmetic and transient; the reorder costs more than it saves

---

## Summary

Nineteen implicit machines: eleven backend, ten client findings covering thirteen
lifecycles. Seven are **fix** (one backend, six client), nine are **codify**, three are
**document**.

The two highest-severity were verified by execution, not by reading:

1. **C1** - one user action against a failing endpoint produced 61 requests and 61 toasts and
   starved the event loop.
2. **C2** - a scope change replaces `state.photos` without closing the viewer, silently
   disabling every viewer action while the stage still shows the previous photo.
