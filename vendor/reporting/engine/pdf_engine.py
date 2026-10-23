"""PDF engine: ReportLab BaseDocTemplate spine.

Stateless and streaming — one call renders one document to a path or an open
binary stream, laying out page by page so per-render memory stays flat. Safe
to fan out across a bounded worker pool.
"""

from functools import partial
from html import escape
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

from reporting.core.document import DocMeta, ReportDocument
from reporting.core.fonts import register_fonts
from reporting.core.outline import OutlineEntry
from reporting.core.pdf_style import body_style
from reporting.core.theme import PRINT_THEME, Theme
from reporting.engine._numbered_canvas import draw_furniture


def render_pdf(doc: ReportDocument, sink, theme: Theme = PRINT_THEME) -> None:
    """Render `doc` to `sink` (a path or open binary stream) as PDF."""
    register_fonts()
    _top, _right, bottom, left = theme.margins_mm
    frame = Frame(
        left * mm,
        bottom * mm,
        theme.content_width_pt(),
        theme.content_height_pt(),
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    template = PageTemplate(
        id="main",
        frames=[frame],
        onPageEnd=partial(draw_furniture, theme=theme, meta=doc.meta),
    )
    rl_doc = BaseDocTemplate(
        _as_stream(sink),
        pagesize=theme.page_size,
        pageTemplates=[template],
        title=doc.meta.title,
        author=doc.meta.engineer or "SED Works",
    )

    story = []
    if doc.meta.title:
        # top-level bookmark = the element title; section headings nest beneath it
        story.append(OutlineEntry(doc.meta.title, level=0))
    if theme.pdf_title_block:
        story.extend(_title_block(doc.meta, theme))
    for component in doc.body:
        story.extend(component.render_pdf(theme))

    rl_doc.build(story)


def _title_block(meta: DocMeta, theme: Theme) -> list[Flowable]:
    """The title block the HTML header shows: a navy band with the title and one
    line of Ref / Site / Engineer / Date, leaving out empty fields."""
    rows = []
    if meta.title:
        rows.append([Paragraph(escape(meta.title), body_style(theme, size=17, color="#ffffff", bold=True))])
    fields = (("Ref:", meta.reference), ("Site:", meta.site_address), ("Engineer:", meta.engineer), ("Date:", meta.date))
    bits = [f"<b>{label}</b> {escape(value)}" for label, value in fields if value]
    if bits:
        # Non-breaking around each separator, so a line never starts or ends on "|".
        rows.append([Paragraph("&nbsp;&nbsp;|&nbsp;&nbsp;".join(bits), body_style(theme, size=8.5, color="#ffffff"))])
    if not rows:
        return []

    table = Table(rows, colWidths=[theme.content_width_pt()])
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(theme.primary)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]
    if len(rows) == 2:
        # Close the gap between the title and the line beneath it.
        style += [("BOTTOMPADDING", (0, 0), (-1, 0), 3), ("TOPPADDING", (0, 1), (-1, 1), 3)]
    table.setStyle(TableStyle(style))
    return [table, Spacer(1, 10)]


def _as_stream(sink):
    """Accept either a path-like or an already-open binary stream."""
    if isinstance(sink, (str, Path)):
        return str(sink)
    return sink
