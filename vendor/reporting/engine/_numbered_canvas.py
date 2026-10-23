"""Running page furniture: a centred header (element title) and a left footer
(reference/mark, with an optional per-page caveat beneath it).

Page numbers are intentionally NOT drawn. Element reports are combined
downstream by `sed_reporting`, which numbers the *combined* document — so any
per-element "Page X of Y" would be wrong. `sed_reporting` draws "Page X of Y" in
the bottom-right, on the `footer_left` baseline, which is why element PDFs leave
that corner clear. It places that stamp by the geometry constants below, so they
are a contract: move the footer and the stamp no longer lines up.

`draw_furniture` is a PageTemplate `onPageEnd` callback. It runs after each
page's content, so the furniture sits on top of it, and before the page is
emitted, so every bookmark binds to the page its heading is on.
"""

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm

from reporting.core.document import DocMeta
from reporting.core.theme import Theme

# Furniture geometry in points, measured from the page margin lines.
HEADER_SIZE_PT = 8
HEADER_RAISE_PT = 6            # header baseline, above the top margin line
FOOTER_LEFT_SIZE_PT = 7
FOOTER_LEFT_DROP_PT = 12       # footer_left baseline, below the bottom margin line
FOOTER_NOTE_SIZE_PT = 6.5
FOOTER_NOTE_DROP_PT = 21       # first footer_note baseline, below the bottom margin line
FOOTER_NOTE_LEADING_PT = 8


def draw_furniture(canv, _doc, *, theme: Theme, meta: DocMeta) -> None:
    """Draw the header and footer on the current page.

    Bind `theme` and `meta` with functools.partial for `PageTemplate(onPageEnd=…)`.
    Platypus does not wrap page callbacks in saveState/restoreState, so this does.
    """
    width, height = theme.page_size
    top, _right, bottom, left = theme.margins_mm
    canv.saveState()
    canv.setFillColor(HexColor(theme.muted))

    if meta.header_text:
        canv.setFont(theme.pdf_font, HEADER_SIZE_PT)
        canv.drawCentredString(width / 2.0, height - top * mm + HEADER_RAISE_PT, meta.header_text)

    # Left footer = element reference/mark. No page number (sed_reporting numbers
    # the combined document); the bottom-right strip is left clear for it.
    if meta.footer_left:
        canv.setFont(theme.pdf_font, FOOTER_LEFT_SIZE_PT)
        canv.drawString(left * mm, bottom * mm - FOOTER_LEFT_DROP_PT, meta.footer_left)

    # A per-page caveat sits beneath the reference, clear of the bottom-right
    # strip. Long notes are split rather than truncated: a scope limitation
    # that runs off the page edge is worse than no note at all.
    if meta.footer_note:
        canv.setFont(theme.pdf_font, FOOTER_NOTE_SIZE_PT)
        y = bottom * mm - FOOTER_NOTE_DROP_PT
        for line in _wrap(canv, meta.footer_note, theme.content_width_pt(), FOOTER_NOTE_SIZE_PT):
            canv.drawString(left * mm, y, line)
            y -= FOOTER_NOTE_LEADING_PT

    canv.restoreState()


def _wrap(canvas, text: str, width_pt: float, size: float) -> list[str]:
    """Greedy word wrap measured in the canvas's current font."""
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if line and canvas.stringWidth(trial, canvas._fontname, size) > width_pt:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines
