"""Shared ReportLab ParagraphStyle builders, driven by the Theme."""

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT  # noqa: F401  (re-exported)
from reportlab.lib.styles import ParagraphStyle

from reporting.core.fonts import register_fonts
from reporting.core.theme import Theme


def body_style(
    theme: Theme,
    name: str = "cell",
    size: float | None = None,
    color: str | None = None,
    bold: bool = False,
    align: int = TA_LEFT,
) -> ParagraphStyle:
    """A paragraph style for body/table-cell text."""
    register_fonts()  # ensure PDF fonts exist before any Paragraph is built
    pt = size or theme.body_pt
    return ParagraphStyle(
        name=name,
        fontName=theme.pdf_font_bold if bold else theme.pdf_font,
        fontSize=pt,
        leading=pt * 1.25,
        textColor=HexColor(color or theme.text),
        alignment=align,
    )


def heading_style(theme: Theme, size: float = 14.0) -> ParagraphStyle:
    """A paragraph style for section headings."""
    register_fonts()
    return ParagraphStyle(
        name="heading",
        fontName=theme.pdf_font_bold,
        fontSize=size,
        leading=size * 1.2,
        textColor=HexColor(theme.primary),
    )
