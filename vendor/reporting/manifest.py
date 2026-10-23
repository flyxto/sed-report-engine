"""Report manifest — the identity `sed_reporting` uses to assemble element PDFs
into a combined report and build its contents pages.

`sed_reporting` reads everything it needs from EACH element PDF — nothing extra
travels alongside the file:

    /Title      -> the contents-row label                (required)
    /Keywords   -> "ref=…; module=…; type=…"             (all three keys required)
    page tree   -> element length, for page offsets
    outline     -> section bookmarks, nested under the element's own bookmark

`stamp_manifest()` writes those Info fields, so the whole contract lives INSIDE
the PDF — no sidecar file. `sed_reporting` rejects a PDF whose /Keywords lack any
of the three keys, because only the stamp writes them. The stamp also sets
/Subject (the element type) and attaches the full identity as `manifest.json`;
`sed_reporting` reads neither — they are an informative and an archival copy.

Design notes:
- **One contents row per element file.** The assembler orders the files, reads
  each Title + page count, and sums page counts for offsets.
- **No absolute page numbers** — the assembler owns final paging.
- Pure-Python (pypdf) — no native deps, keeps the deploy image light.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass
from typing import Optional

_ATTACHMENT_NAME = "manifest.json"
SCHEMA_VERSION = "1.0"


@dataclass
class ReportManifest:
    """The per-element report contract — identity only. Everything positional
    (page_count, section anchors) is read from the PDF itself: the page tree
    gives page_count, the PDF outline/bookmarks give the section anchors. Stable
    shape — evolve via schema_version."""

    id: str                                   # stable unique id for this element report
    module: str                               # "beams" | "rafts" | "pf" | "rw"
    element_type: str                         # "beam" | "column" | "connection" | "foundation" | "raft"
                                              # | "frame" | "retaining_wall" — keep to this list
    title: str                                # human title for the TOC row
    reference: str = ""                       # structural mark (grouping/sorting)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def _keywords(m: dict) -> str:
    return "; ".join([f"ref={m.get('reference', '')}", f"module={m.get('module', '')}",
                      f"type={m.get('element_type', '')}"])


def stamp_manifest(pdf_bytes: bytes, manifest, *, set_metadata: bool = True) -> bytes:
    """Return `pdf_bytes` with the element identity written into the PDF.

    Primary contract: sets the standard Info fields `sed_reporting` reads —
    /Title (contents label) and /Keywords (parseable tags) — plus /Subject
    (type, informative). Also attaches the full identity as `manifest.json`, an
    archival copy `sed_reporting` does not read. page_count is NOT written; the
    assembler reads it from the PDF page tree.

    `manifest` is a ReportManifest or a plain dict.
    """
    from pypdf import PdfReader, PdfWriter

    m = manifest.to_dict() if isinstance(manifest, ReportManifest) else dict(manifest)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.append(reader)  # copies pages + any existing outline/bookmarks
    writer.add_attachment(_ATTACHMENT_NAME, json.dumps(m, indent=2).encode("utf-8"))
    if set_metadata:
        # sed_reporting reads /Title and /Keywords; /Subject is informative:
        writer.add_metadata({
            "/Title": m.get("title", ""),            # contents-row label
            "/Subject": m.get("element_type", ""),   # element type
            "/Keywords": _keywords(m),               # "ref=…; module=…; type=…"
        })

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def read_manifest(pdf_bytes: bytes) -> Optional[dict]:
    """Extract the embedded `manifest.json` — a reference reader for the archival
    copy. Returns the dict, or None if absent."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    att = getattr(reader, "attachments", {}) or {}
    if _ATTACHMENT_NAME not in att:
        return None
    data = att[_ATTACHMENT_NAME]
    raw = data[0] if isinstance(data, list) else data
    return json.loads(raw)
