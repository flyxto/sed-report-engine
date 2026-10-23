"""Uniform "Page X of Y" across a combined report.

Element PDFs carry no page numbers on purpose: `reporting`'s page furniture
leaves the bottom-right corner clear, because only the combined document knows
final paging. The number is drawn on the same baseline, in the same font, size
and colour as `reporting`'s left footer (engine/_numbered_canvas.py), but
right-aligned at the right margin, so it reads as part of the same furniture.
That assumes the elements were rendered with the theme's margins; every theme
`reporting` ships shares them.
"""

from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from reporting.core.fonts import register_fonts
from reporting.core.theme import Theme

# Mirror reporting's left-footer placement: 7 pt, 12 pt below the bottom margin.
_FOOTER_PT = 7
_FOOTER_DROP_PT = 12


def stamp_page_numbers(writer: PdfWriter, theme: Theme) -> None:
    """Draw "Page i of N" on every page of `writer`, in place."""
    pages = list(writer.pages)
    total = len(pages)
    register_fonts()
    _top, right, bottom, _left = theme.margins_mm

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, page in enumerate(pages, start=1):
        if page.rotation:
            page.transfer_rotation_to_content()  # stamp in the page's upright frame
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        c.setPageSize((width, height))
        c.setFont(theme.pdf_font, _FOOTER_PT)
        c.setFillColor(HexColor(theme.muted))
        c.drawRightString(width - right * mm, bottom * mm - _FOOTER_DROP_PT, f"Page {i} of {total}")
        c.showPage()
    c.save()

    overlay = PdfReader(io.BytesIO(buf.getvalue()))
    for page, stamp in zip(pages, overlay.pages):
        page.merge_translated_page(stamp, float(page.mediabox.left), float(page.mediabox.bottom))
