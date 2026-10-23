"""Merge element PDFs into one combined report:

    contents page(s)  ->  element 1  ->  element 2  ->  …

with bookmarks (Table of Contents, then one per element) and "Page X of Y" on every
page. Elements keep the order they are given in; ordering is the caller's call.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter
from pypdf.generic import IndirectObject

from reporting import PRINT_THEME, Theme, render_pdf

from sed_reporting.contents import CONTENTS_TITLE, contents_document
from sed_reporting.element import ElementInfo, Section, read_element
from sed_reporting.stamp import stamp_page_numbers

# The contents page count decides every start page, and the start pages are
# printed on the contents page — so it is rendered until its own length settles.
# One extra pass is normal; more than a few means something is wrong.
_MAX_CONTENTS_PASSES = 5


@dataclass(frozen=True)
class ReportMeta:
    """Identity of the combined report: shown on the contents page and in PDF metadata."""

    title: str
    reference: str = ""
    site_address: str = ""
    engineer: str = ""
    date: str = ""


def assemble(
    elements: Sequence[bytes],
    meta: ReportMeta,
    *,
    names: Sequence[str] | None = None,
    theme: Theme = PRINT_THEME,
    section_bookmarks: bool = True,
    lead: bytes | None = None,
) -> bytes:
    """Return the combined report PDF for `elements`, in the order given.

    names: one label per element for error messages (default "element 1", …).
    lead: a report body to put first, before the contents (e.g. the SCR, whose
        Appendix A is the contents plus the element reports). Its own bookmarks
        are kept, the contents leaves out the project details the body already
        has, and page numbers run across everything.
    section_bookmarks: nest each element's own section bookmarks under it (the
        default). An element rendered before `reporting` 0.2.0 has every
        bookmark on its first page (a bug since fixed upstream, Change C), so
        its sections would all jump to the same place: for such an element the
        nested bookmarks are left out and it keeps only its own (`_outline_is_sound`).

    Raises ElementError (a ValueError) naming the first element that fails the
    contract; nothing is assembled from a partly-valid set.
    """
    if not elements:
        raise ValueError("nothing to assemble: no element PDFs given")
    if not meta.title.strip():
        raise ValueError("the combined report needs a title")
    names = list(names) if names is not None else [f"element {i}" for i in range(1, len(elements) + 1)]
    if len(names) != len(elements):
        raise ValueError(f"{len(names)} names given for {len(elements)} elements")

    infos = [read_element(pdf, name) for pdf, name in zip(elements, names)]
    lead_pages = len(PdfReader(io.BytesIO(lead)).pages) if lead else 0
    contents_pdf, starts = _render_contents(meta, infos, theme, lead_pages=lead_pages, with_details=lead is None)

    writer = PdfWriter()
    if lead:
        writer.append(PdfReader(io.BytesIO(lead)), import_outline=True)
    writer.append(PdfReader(io.BytesIO(contents_pdf)), import_outline=False)
    writer.add_outline_item(CONTENTS_TITLE, lead_pages)
    for pdf, info, start in zip(elements, infos, starts):
        first = len(writer.pages)
        # The contents page has already printed `start`; a mismatch here would
        # publish a wrong page reference, so refuse rather than continue.
        if first != start - 1:
            raise RuntimeError(f"contents lists {info.title!r} at page {start}, but it would land on page {first + 1}")
        writer.append(PdfReader(io.BytesIO(pdf)), import_outline=False)
        parent = writer.add_outline_item(info.title, first)
        if section_bookmarks and _outline_is_sound(info):
            _add_sections(writer, _below_title(info), first, parent)

    stamp_page_numbers(writer, theme)
    writer.add_metadata({"/Title": meta.title, "/Keywords": f"ref={meta.reference}"})
    writer.page_mode = "/UseOutlines"

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def start_pages(front_pages: int, elements: Sequence[ElementInfo]) -> list[int]:
    """1-based start page of each element, after `front_pages` of contents."""
    starts, cursor = [], front_pages + 1
    for info in elements:
        starts.append(cursor)
        cursor += info.page_count
    return starts


def _render_contents(meta: ReportMeta, infos: list[ElementInfo], theme: Theme, *,
                     lead_pages: int = 0, with_details: bool = True) -> tuple[bytes, list[int]]:
    front = 1
    for _ in range(_MAX_CONTENTS_PASSES):
        starts = start_pages(lead_pages + front, infos)
        buf = io.BytesIO()
        render_pdf(contents_document(meta, infos, starts, with_details=with_details), buf, theme=theme)
        pages = len(PdfReader(io.BytesIO(buf.getvalue())).pages)
        if pages == front:
            return buf.getvalue(), starts
        front = pages
    raise RuntimeError(f"contents page count did not settle after {_MAX_CONTENTS_PASSES} renders")


def _below_title(info: ElementInfo) -> tuple[Section, ...]:
    """`reporting` puts the element title at the top of its outline with the
    sections beneath; the assembler already adds that title, so skip a level."""
    s = info.sections
    if len(s) == 1 and s[0].title == info.title:
        return s[0].children
    return s


def _outline_is_sound(info: ElementInfo) -> bool:
    """False when the element's bookmarks show the old `reporting` bug: a
    multi-page element whose sections all point at its first page. Re-rendering
    the element with `reporting` 0.2.0 or later fixes it."""
    pages, todo = [], list(_below_title(info))
    while todo:
        s = todo.pop()
        pages.append(s.page)
        todo.extend(s.children)
    return not (info.page_count > 1 and len(pages) > 1 and all(p == 0 for p in pages))


def _add_sections(writer: PdfWriter, sections: Sequence[Section], first: int, parent: IndirectObject) -> None:
    for s in sections:
        item = writer.add_outline_item(s.title, first + s.page, parent=parent)
        _add_sections(writer, s.children, first, item)
