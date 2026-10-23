"""Centralised theme: one object drives brand + typography for every module.

A rebrand edits BASE_THEME and propagates everywhere. WEB_THEME and
PRINT_THEME are variants off the same base, so the detailed HTML and the
summary PDF can look slightly different without diverging the brand.
"""

from dataclasses import dataclass, replace

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm


@dataclass(frozen=True)
class Theme:
    """Brand palette, typography and page geometry for a report render."""

    # Brand palette (hex strings — usable by both HTML CSS and ReportLab)
    primary: str = "#1f3b5c"          # EQSE navy
    text: str = "#222222"
    muted: str = "#666666"
    border: str = "#d0d7de"
    row_alt: str = "#f4f6f8"

    # Status palette
    ok: str = "#2e7d32"
    fail: str = "#c62828"
    warn: str = "#d39e00"
    ok_bg: str = "#d8f3dc"
    fail_bg: str = "#fde0dc"
    warn_bg: str = "#fff4d6"

    # Typography — the two mediums use different font machinery.
    # PDF uses bundled DejaVu Sans (Unicode: Greek, sub/superscripts, math);
    # see core/fonts.register_fonts(), called by the PDF engine.
    html_font_family: str = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
    pdf_font: str = "DejaVuSans"
    pdf_font_bold: str = "DejaVuSans-Bold"
    body_pt: float = 9.0

    # Page geometry (mm): top, right, bottom, left
    margins_mm: tuple[float, float, float, float] = (20.0, 15.0, 25.0, 15.0)

    # Page size in points, (width, height). Defaults to A4 portrait; a landscape
    # variant passes landscape(A4). Everything that needs page dimensions reads
    # it from here, so a theme is the single place orientation is decided.
    page_size: tuple[float, float] = A4

    # Opt-in document furniture, off by default so existing output is unchanged.
    # Enable per output: replace(PRINT_THEME, pdf_title_block=True).
    pdf_title_block: bool = False    # PDF draws the DocMeta title block
    html_footer_note: bool = False   # HTML shows DocMeta.footer_note

    def content_width_pt(self) -> float:
        """Usable width inside the page margins, in points."""
        _top, right, _bottom, left = self.margins_mm
        return self.page_size[0] - (left + right) * mm

    def content_height_pt(self) -> float:
        """Usable height inside the page margins, in points."""
        top, _right, bottom, _left = self.margins_mm
        return self.page_size[1] - (top + bottom) * mm


# Single source of brand truth.
BASE_THEME = Theme()

# Web view: the full, richer report. Same brand as base.
WEB_THEME = BASE_THEME

# Print/PDF view: leaner variant off the same base (tighter body text).
PRINT_THEME = replace(BASE_THEME, body_pt=8.5)

# Landscape print variant — for wide content (force-diagram appendices, very
# wide tables) that will not read at portrait width. Same brand and typography;
# only the page geometry differs, so a document can switch orientation by
# switching theme with no component changes.
PRINT_THEME_LANDSCAPE = replace(PRINT_THEME, page_size=landscape(A4))
