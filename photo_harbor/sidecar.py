"""Read-only JSON and XMP sidecars for selected photos; originals are never touched."""

import io
import json
import unicodedata
import zipfile
from xml.sax.saxutils import escape

from .catalog import Catalog
from .errors import HarborError
from .messages import Reply, Request
from .naming import safe_name
from .selection import visible
from .tags import TagBook


def _entry_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _sidecar_name(record, suffix: str, used: set) -> str:
    base = safe_name(record.original_name)
    stem = base.rsplit(".", 1)[0] or "photo"
    name = f"{stem}.{suffix}"
    if _entry_key(name) not in used:
        used.add(_entry_key(name))
        return name
    name = f"{stem}-{record.sha256[:8]}.{suffix}"
    if _entry_key(name) not in used:
        used.add(_entry_key(name))
        return name
    counter = len(used) + 1
    while True:
        name = f"{stem}-{counter}-{record.sha256[:8]}.{suffix}"
        if _entry_key(name) not in used:
            used.add(_entry_key(name))
            return name
        counter += 1


def json_sidecar(record, tags: list) -> bytes:
    payload = {
        "schema": 1,
        "generator": "Photo-Harbor",
        "sha256": record.sha256,
        "file": record.original_name,
        "type": record.media_type,
        "taken": record.taken_at,
        "received": record.received_at,
        "profile": record.profile,
        "camera": record.camera,
        "lens": record.lens,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "tags": tags,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _gps(value: float, positive: str, negative: str) -> str:
    direction = positive if value >= 0 else negative
    absolute = abs(float(value))
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60
    return f"{degrees},{minutes:.6f}{direction}"


def xmp_sidecar(record, tags: list) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">',
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        '  <rdf:Description rdf:about=""',
        '   xmlns:dc="http://purl.org/dc/elements/1.1/"',
        '   xmlns:exif="http://ns.adobe.com/exif/1.0/"',
        '   xmlns:tiff="http://ns.adobe.com/tiff/1.0/"',
        '   xmlns:aux="http://ns.adobe.com/exif/1.0/aux/"',
        '   xmlns:xmp="http://ns.adobe.com/xap/1.0/">',
    ]
    if tags:
        lines.append("   <dc:subject><rdf:Bag>")
        lines.extend(f"    <rdf:li>{escape(tag)}</rdf:li>" for tag in tags)
        lines.append("   </rdf:Bag></dc:subject>")
    lines.append(f"   <dc:title><rdf:Alt><rdf:li xml:lang=\"x-default\">"
                 f"{escape(record.original_name)}</rdf:li></rdf:Alt></dc:title>")
    if record.taken_at:
        lines.append(f"   <xmp:CreateDate>{escape(record.taken_at)}</xmp:CreateDate>")
    if record.camera:
        lines.append(f"   <tiff:Model>{escape(record.camera)}</tiff:Model>")
    if record.lens:
        lines.append(f"   <aux:Lens>{escape(record.lens)}</aux:Lens>")
    if record.latitude is not None and record.longitude is not None:
        lines.append(f"   <exif:GPSLatitude>{_gps(record.latitude, 'N', 'S')}"
                     "</exif:GPSLatitude>")
        lines.append(f"   <exif:GPSLongitude>{_gps(record.longitude, 'E', 'W')}"
                     "</exif:GPSLongitude>")
    lines.extend([
        "  </rdf:Description>",
        " </rdf:RDF>",
        "</x:xmpmeta>",
        '<?xpacket end="w"?>',
    ])
    return "\n".join(lines).encode("utf-8")


def sidecar_zip(entries: list, fmt: str) -> bytes:
    """Build a ZIP of JSON or XMP sidecars; ``entries`` are ``(record, tag names)`` pairs."""
    suffix = "json" if fmt == "json" else "xmp"
    builder = json_sidecar if fmt == "json" else xmp_sidecar
    buffer = io.BytesIO()
    used = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for record, tags in entries:
            archive.writestr(_sidecar_name(record, suffix, used), builder(record, tags))
    return buffer.getvalue()


class SidecarApi:
    def __init__(self, catalog: Catalog, tags: TagBook) -> None:
        self._catalog = catalog
        self._tags = tags

    def export(self, request: Request) -> Reply:
        body = request.json()
        fmt = str(body.get("format", "json")).lower()
        if fmt not in ("json", "xmp"):
            raise HarborError("format must be json or xmp", f"got {fmt!r}",
                              'send {"format": "json"}', status=400)
        sha256s = visible(request, self._catalog, body)
        entries = []
        for sha256 in sha256s:
            record = self._catalog.get(sha256)
            if record is not None:
                entries.append((record, self._tags.names(request.profile, sha256)))
        data = sidecar_zip(entries, fmt)
        name = f"harbor-sidecars-{fmt}.zip"
        return Reply(200, body=data, content_type="application/zip",
                     headers=(("Content-Disposition", f'attachment; filename="{name}"'),
                              ("Cache-Control", "no-store")))
