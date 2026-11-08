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
| Multi-user | Per-person profiles, keys, private galleries | - | Keep |
| Albums | Personal albums and favorites | - | Keep |
| Shared albums / public sharing | No | Low: home-network privacy is the product promise; public links add auth and abuse surface | Not now |
| Scrubbable bar / virtual scroll | Paginated day grid with lazy images | Medium: current scale is measured at 50k photos (12-33 ms pages) | Later |
| RAW / 360 / LivePhoto / MotionPhoto | HEIC via optional Pillow; no RAW/360/pairing | Low-medium: needs decoders or paired-file model | Not now |
| Metadata view (EXIF, map) | EXIF facts; GPS point and Places rail, no map | Medium: GPS extraction and coarse place grouping are local; map tiles would be a network dependency | **Places implemented**, map later |
| Search by metadata/objects/faces/CLIP | File-name search + date/person/album/kind filters | Low for ML (RAM/CPU/extra services); tags/metadata search is worthwhile | Search metadata later |
| Admin/user management | Owner manages people, passwords and keys | - | Keep |
| OAuth / API keys | Profile keys and browser sessions | Low for a home LAN | Not now |
| User-defined storage structure | Fixed readable `<Person>/<YYYY>/<YYYY-MM>` layout | Low: the plain layout is a deliberate feature | Not now |
| Archive | Yes: per-person hidden state, rail view, single/bulk restore | - | **Implemented now** |
| Favorites | Yes | - | Keep |
| Global Map | Coarse Places list; no map surface | Medium: needs an offline tile story; GPS is now stored | Later |
| Partner sharing | No | Low: per-person folders already cover the household use case | Not now |
| Facial recognition/clustering | No | Low here: ML worker, model downloads and training data | Not now |
| Memories (x years ago) | No | High: one filter over existing dates, high user value | **Implemented now** |
| Tags | Yes: per-person tags, rail filter, viewer/selection apply | - | **Implemented now** |
| Folder view | Plain folders in Explorer; no web folder tree | Low: duplicate of the filesystem and current filters | Not now |
| Offline support | PWA shell only; Android has local queue state | Medium: offline write queue is a large state machine | Not now |
| Read-only gallery | No separate role | Medium: could reuse a share token, but conflicts with private profiles | Later |
| Duplicates utility | Exact SHA-256 dedupe only | Medium: near-duplicate detection needs perceptual hashes | Later |
| XMP sidecars | No | Medium: useful for interoperability; file mutation risk | Later |
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

## Next candidates

1. **Near-duplicate utility** - perceptual hash with a review/keep flow, not automatic deletion.
2. **Metadata search** - expose camera/lens filters once EXIF is parsed into columns.
3. **Global map** - only with an offline tile story that preserves the home-network promise.
