"""Register bundled Unicode TTF fonts (DejaVu Sans) with ReportLab.

The base-14 PDF fonts (Helvetica) lack engineering glyphs — Greek letters
(φ, μ, ξ), superscript-minus (⁻), sub/superscripts and common math symbols
render as tofu. DejaVu Sans covers all of these and is redistributable
(see assets/fonts/LICENSE_DEJAVU). Registration is idempotent.
"""

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# registered name -> filename
_FACES = {
    "DejaVuSans": "DejaVuSans.ttf",
    "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
    "DejaVuSans-Oblique": "DejaVuSans-Oblique.ttf",
    "DejaVuSans-BoldOblique": "DejaVuSans-BoldOblique.ttf",
}

_registered = False


def register_fonts() -> None:
    """Register DejaVu faces + the family mapping. Safe to call repeatedly."""
    global _registered
    if _registered:
        return
    known = set(pdfmetrics.getRegisteredFontNames())
    for name, filename in _FACES.items():
        if name not in known:
            pdfmetrics.registerFont(TTFont(name, str(_FONT_DIR / filename)))
    # Family mapping so <b>/<i> markup inside Paragraphs resolves correctly.
    pdfmetrics.registerFontFamily(
        "DejaVuSans",
        normal="DejaVuSans",
        bold="DejaVuSans-Bold",
        italic="DejaVuSans-Oblique",
        boldItalic="DejaVuSans-BoldOblique",
    )
    _registered = True
