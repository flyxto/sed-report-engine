"""Read one element PDF and check it meets the assembler contract.

An element PDF is one design element's report (a beam, a raft, …), rendered by
its design module with `reporting` and stamped by `reporting.render_report` (or
`reporting.stamp_manifest`). The assembler needs:

    the stamp   proof the PDF came through the module's render path, and its
                identity: the title (contents-row label) and reference
    page tree   page count, for page offsets
    outline     section bookmarks, for navigation   (optional)

The stamp is written twice. The identity is read from the attached
`manifest.json`, the exact copy. The /Title and /Keywords ("ref=…; module=…;
type=…") are the fallback, for a PDF whose attachment was stripped by later
processing. The keywords cannot hold a ";" inside a value — "B12; rev C" would
come back as "B12" — which is why the attachment comes first.

The element type is in the stamp too, but the assembler does not use it.

An unstamped `reporting` PDF still has a /Title (ReportLab copies
DocMeta.title), so /Title alone does not prove the stamp: without the
attachment, all three keyword keys must be present.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, replace

from pypdf import PdfReader

from reporting import read_manifest

_STAMP_KEYS = ("ref", "module", "type")


class ElementError(ValueError):
    """An element PDF that cannot be assembled. The message names it and says why."""


@dataclass(frozen=True)
class Section:
    """One outline entry: title, page within the element (0-based), children."""

    title: str
    page: int
    children: tuple[Section, ...] = ()


@dataclass(frozen=True)
class ElementInfo:
    """What the assembler reads from one element PDF."""

    title: str
    reference: str
    module: str
    page_count: int
    sections: tuple[Section, ...] = ()


def parse_keywords(text: str) -> dict[str, str]:
    """Parse "ref=B12; module=beams; type=beam" into a dict. Parts without "=" are ignored."""
    out: dict[str, str] = {}
    for part in (text or "").split(";"):
        key, sep, value = part.partition("=")
        if sep:
            out[key.strip()] = value.strip()
    return out


def read_element(pdf: bytes, name: str = "element") -> ElementInfo:
    """Read and validate `pdf`. `name` identifies it in error messages."""
    try:
        reader = PdfReader(io.BytesIO(pdf))
        if reader.is_encrypted:
            raise ElementError(f"{name}: is encrypted; assemble unencrypted element PDFs")
        page_count = len(reader.pages)
        meta = reader.metadata
        info_title = ((meta.title if meta else None) or "").strip()
        keywords = parse_keywords((meta.keywords if meta else None) or "")
        sections = _sections(reader, reader.outline)
    except ElementError:
        raise
    except Exception as e:  # pypdf raises many types on malformed input; all mean "unreadable"
        raise ElementError(f"{name}: not a readable PDF ({type(e).__name__}: {e})") from e

    if page_count == 0:
        raise ElementError(f"{name}: has no pages")

    manifest = _manifest(pdf, name)
    if manifest is not None:
        title = str(manifest.get("title") or "").strip()
        reference = str(manifest.get("reference") or "")
        module = str(manifest.get("module") or "")
    else:
        missing = [k for k in _STAMP_KEYS if k not in keywords]
        if missing:
            raise ElementError(f"{name}: not stamped (no manifest.json, and /Keywords lacks {', '.join(missing)}); "
                               "render it with reporting.render_report()")
        title, reference, module = info_title, keywords["ref"], keywords["module"]

    if not title:
        raise ElementError(f"{name}: its stamp has no title to label its contents row")

    return ElementInfo(title=title, reference=reference, module=module, page_count=page_count, sections=sections)


def _manifest(pdf: bytes, name: str) -> dict | None:
    """The stamp's attached manifest.json, or None if there is none."""
    try:
        manifest = read_manifest(pdf)
    except Exception as e:  # a corrupt attachment is a broken stamp, not a missing one
        raise ElementError(f"{name}: its stamp (manifest.json) is unreadable ({type(e).__name__}: {e})") from e
    if manifest is not None and not isinstance(manifest, dict):
        raise ElementError(f"{name}: its stamp (manifest.json) is not a JSON object")
    return manifest


def _sections(reader: PdfReader, outline: list) -> tuple[Section, ...]:
    """Convert pypdf's outline, where a list following an item holds that item's children.

    A bookmark whose destination cannot be resolved is dropped and its children
    are promoted a level, rather than being attached to the wrong parent.
    """
    out: list[Section] = []
    attach = False  # does a following child list belong to the last section added?
    for item in outline:
        if isinstance(item, list):
            children = _sections(reader, item)
            if attach:
                last = out.pop()
                out.append(replace(last, children=last.children + children))
            else:
                out.extend(children)
        else:
            page = reader.get_destination_page_number(item)
            attach = page is not None and page >= 0
            if attach:
                out.append(Section(str(item.title), page))
    return tuple(out)
