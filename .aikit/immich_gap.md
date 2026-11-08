# Immich gap analysis (2026-11-08)

Reference: Immich's public feature table (`github.com/immich-app/immich`, README, fetched
2026-11-08) and docs feature pages. Immich is a Docker/Postgres/Redis service with a separate
machine-learning worker; Photo-Harbor is a stdlib-only Windows server that keeps plain folders.

## Feature comparison

| Immich feature | Photo-Harbor today | Worth it here? | Decision |
|---|---|---|---|
| Upload/view photos and videos | Yes | - | Keep |
| Auto backup when the mobile app opens | Android background/sync, Shortcuts automations | - | Keep |
| Prevent duplication of assets | SHA-256 catalog + hard links | - | Keep |
| Download originals | One-time ZIP and original links | - | Keep |
| Multi-user | Per-person profiles, keys, private galleries and a read-only People overview | - | Keep |
| Albums | Personal albums, favorites and a cover/count overview tab | - | Keep |
| Explore / statistics | Read-only overview of years, places, cameras, lenses and counts | - | **Implemented now** |
| Activity / audit log | Read-only recent journal events with person labels | - | **Implemented now** |
| Shared albums / public sharing | No | Low: home-network privacy is the product promise; public links add auth and abuse surface | Not now |
| Scrubbable bar / virtual scroll | Year/month scrubber plus windowed day sections with placeholder heights | - | **Implemented now** |
| RAW / 360 / LivePhoto / MotionPhoto | HEIC via optional Pillow; no RAW/360/pairing | Low-medium: needs decoders or paired-file model | Not now |
| Metadata view (EXIF, map) | EXIF facts; GPS point and Places rail, no map | Medium: GPS extraction and coarse place grouping are local; map tiles would be a network dependency | **Places implemented**, map later |
| Search by metadata/objects/faces/CLIP | File-name, date, person, album, tag, place, camera and lens filters; no ML | Low for ML (RAM/CPU/extra services); local metadata search is worthwhile | **Camera/lens search implemented**, ML later |
| Admin/user management | Owner manages people, passwords and keys | - | Keep |
| OAuth / API keys | Profile keys and browser sessions | Low for a home LAN | Not now |
| User-defined storage structure | Fixed readable `<Person>/<YYYY>/<YYYY-MM>` layout | Low: the plain layout is a deliberate feature | Not now |
| Archive | Yes: per-person hidden state, rail view, single/bulk restore | - | **Implemented now** |
| Favorites | Yes | - | Keep |
| Global Map | Offline SVG outline with Places markers | - | **Implemented now** |
| Partner sharing | No | Low: per-person folders already cover the household use case | Not now |
| Facial recognition/clustering | No | Low here: ML worker, model downloads and training data | Not now |
| Memories (x years ago) | No | High: one filter over existing dates, high user value | **Implemented now** |
| Tags | Yes: per-person tags, rail filter, overview tab, viewer/selection apply | - | **Implemented now** |
| Folder view | Read-only Folders tab over the real person/year/month paths | - | **Implemented now** |
| Offline support | PWA shell only; Android has local queue state | Medium: offline write queue is a large state machine | Not now |
| Read-only gallery | No separate role | Medium: could reuse a share token, but conflicts with private profiles | Later |
| Duplicates utility | Exact SHA-256 dedupe plus read-only dHash Similar review | - | **Implemented now** |
| XMP sidecars | Yes: read-only JSON/XMP ZIP export; originals untouched | - | **Implemented now** |
| Editing / transcoding / casting / monitoring | No | Low for this lightweight server | Not now |

## Implemented in this pass: Memories and Archive

`GET /api/photos?day=MM-DD` matches the month/day across every year, with a real calendar check
that still permits `02-29`. The gallery's **On this day** rail button uses the browser's current
month/day, composes with person/query/sort filters and shows an explicit empty message.

Archive adds per-person hidden state (`archived` table, `archived=1` filter, `POST /api/archive`).
The rail **Archive** view lists only the viewer's hidden photos; the viewer and selection bars
archive or restore single photos and batches. Files never move, copies stay intact, and Storage
still counts them. Month counts, favorites and the timeline hide archived photos. This is the
second cheap high-value Immich feature: no ML and no file movement.

## Implemented in this pass: Tags

Format 9 adds per-person `tags` and `photo_tags`. A tag is a named mark on any photo the person
can see; `GET /api/photos?tag=ID` narrows the gallery, the rail lists **Tags** with visible
counts, and the viewer plus selection bar apply or remove them. Creating the same name is
case-insensitive and idempotent. Tags stay private, never move files, and the marks disappear
with the person's last copy; archived photos leave the rail count.

## Implemented in this pass: Places

Format 10 stores `latitude`/`longitude` from EXIF GPS at ingest (optional Pillow). The outline
returns coarse one-decimal buckets, the rail lists **Places** with counts, and
`GET /api/photos?place=LAT,LON` narrows the gallery. The Details panel shows the exact point.
No map tiles, reverse geocoding or network lookup are involved; archived photos leave the list.

## Implemented in this pass: Sidecars

`POST /api/sidecar` validates selected hashes through the same privacy/selection path as other
bulk actions and returns a ZIP of per-photo JSON or XMP files. Each sidecar carries the viewer's
tags, stored GPS point, camera, lens and file facts. The selection bar offers both formats; the
viewer's **Sidecar** button exports JSON. Originals are never modified and no sidecar is written
back to the library folders.

## Implemented in this pass: Virtual day grid

The Photos grid now keeps only day sections intersecting the viewport (plus a buffer) in the
DOM. `state.photos` remains the source of truth; each day has a computed placeholder height and
windowed sections are positioned absolutely inside a tall `#days` container. Scroll and resize
refresh the window, while selection, favorites, viewer indices and the sentinel continue to use
the in-memory list. A 50k synthetic run keeps the tile count bounded.

## Implemented in this pass: Timeline scrubber

The Photos view now has a **Year/Month** scrubber plus **Newer** and **Older** buttons derived
from the existing outline months and counts. It jumps through the same month scope as the
sidebar, stays in sync with it, and adds no backend or schema state.

## Implemented in this pass: Folders

The **Folders** tab calls `/api/folders` and renders the real `<Person>/<YYYY>/<YYYY-MM>`
paths with month counts. Owner sees every person; non-owners see only themselves. Clicking a
month opens the gallery with that person and month selected. Archived photos are absent, and no
folder or file is created, moved or renamed.

## Implemented in this pass: Offline map

The **Map** tab projects the stored one-decimal Places onto an embedded equirectangular SVG
world outline. Markers use the same `/api/outline` data as the Places rail, scale with photo
counts, and a clickable list opens a place's gallery view. No tiles, CDN, reverse geocoding or
network lookup are used; the map is read-only and respects the signed-in person's visible pairs.

## Implemented in this pass: Activity overview

`GET /api/activity` exposes a bounded, newest-first slice of the existing `events` journal.
The **Activity** tab labels uploads, duplicates, rejects, finished syncs, scans, checks, removals,
damage and missing reports with relative time, detail and person. Owner sees everyone; other
people see only their own events. It is read-only and adds no schema.

## Implemented in this pass: People overview

The **People** tab reads the existing `/api/profiles` response and shows each person's initials,
name, folder, item/byte count and last-sync value. Clicking a card opens the existing person
gallery scope; password/key management stays in Setup. It is read-only and adds no endpoint,
schema or state.

## Implemented in this pass: Tags overview

The **Tags** tab reads the existing `/api/tags` response and renders one card per tag with its
name and visible count; clicking a card opens the existing tag scope. Creation/editing stays in
Photos. It is read-only and adds no endpoint, schema or state.

## Implemented in this pass: Albums overview

The **Albums** tab fetches the existing `/api/albums` response and renders each album's cover,
name and count as a card; clicking a card opens the existing album scope. Creation and editing
remain in the Photos experience, so the overview is read-only and adds no schema or endpoint.

## Implemented in this pass: Explore

The **Explore** tab derives every number from the existing `/api/outline`: photos, favorites,
videos, archive, years, months, places, cameras and lenses. Year rows use proportional bars;
place/camera/lens rows open their filtered gallery views. It is read-only and adds no endpoint
or schema state.

## Implemented in this pass: Similar comparison

Each cached Similar group has a **Compare side by side** action. It opens a read-only overlay
with the group's full media URLs, names and dates, plus a Close button and Escape support. No
delete, selection or mutation action exists in the overlay; it reuses the group response already
tested by the Similar API.

## Implemented in this pass: Similar review

Format 12 adds a `photo_hashes` cache. **Similar** is a separate tab: **Scan library** computes
an optional Pillow difference hash for visible photos in batches, unreadable files are marked
`skip`, and groups are cached connected components whose 64-bit hashes differ by at most 8
bits. **Scan library** hashes in bounded batches; **Build groups** recomputes the SQLite cache in
a background worker, and **Similar** reads SQL groups instead of comparing hashes on page load.
The view is read-only: each photo links to its original and there is no delete action. This
catches re-encoded or resized copies that SHA-256 dedupe misses, without automatic deletion.
A synthetic 50k-photo cache with 25k groups loaded through `similar_groups` in 0.87 s.

## Implemented in this pass: Cameras

Format 11 stores `camera` and `lens` from EXIF once at ingest (Pillow optional). The outline
returns camera and lens names with visible counts, the rails list **Cameras** and **Lenses**, and
`GET /api/photos?camera=NAME` or `?lens=NAME` narrows the gallery. Details already shows the same
camera/lens facts. Archived photos leave both counts; no ML, network or file rewrite is involved.

## Decision summary

Implemented in this pass: **Memories, Archive, Tags, Places, Cameras, Similar review and
comparison, sidecars, an offline map, a read-only Folders tab, Explore statistics, Albums/Tags/
People overviews, Activity, a year/month timeline scrubber and a virtualized day grid**. All
seventeen reuse local data, avoid ML services and network dependencies, and never move or rewrite
originals. Archive and Tags add only private per-person marks; Places stores the camera's point
once; Cameras stores the EXIF make/model and lens once; Similar uses an optional perceptual hash
cache and a read-only overlay; sidecars are generated in memory; the map is an embedded SVG
outline; Folders mirrors the existing disk layout; Explore reads outline counts; Albums/Tags/
People read their existing lists; Activity reads the journal; the scrubber reads outline months;
the grid windows day sections. They compose with the existing person, album, date, kind, name and
sort filters.

Deliberately not now:

- **Sharing, OAuth, RAW/360/LivePhoto, storage templates, transcoding and offline write queues**
  - each breaks the home-network privacy or plain-folder/lightweight-server promise, or is a
  much larger state machine than the value justifies here.
