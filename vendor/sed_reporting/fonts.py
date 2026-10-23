"""The reports' typeface: Helvetica Neue, in the PDF and in the preview.

Helvetica Neue is a licensed typeface, so it is not in this repo. The PDF engine
(ReportLab) reads TrueType outlines only, not CFF/PostScript-flavoured .otf
files. It needs a .ttc collection with Regular, Bold, Italic and Bold Italic as
faces 0–3, which is the layout of macOS's /System/Library/Fonts/HelveticaNeue.ttc:

    SED_REPORTING_FONT=/path/to/HelveticaNeue.ttc   a licensed copy (servers)
    (unset)                                         macOS's own copy, if present (local development)

Without either, the PDF falls back to reporting's bundled DejaVu Sans, and
GET /health says which font is in use. A configured path that is missing, or
whose faces are not in that order, is an error rather than a silent fallback.

The preview asks the browser for Helvetica Neue first, and shows table numbers
in it too (the PDF has no monospace numbers). A viewer without the font sees
Helvetica or Arial.
"""

from __future__ import annotations

import functools
import os
from dataclasses import replace
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFontFile

from reporting import PRINT_THEME, WEB_THEME, Theme

FAMILY = "HelveticaNeue"
_FACES = {"HelveticaNeue": 0, "HelveticaNeue-Bold": 1, "HelveticaNeue-Italic": 2, "HelveticaNeue-BoldItalic": 3}
_MACOS_COPY = Path("/System/Library/Fonts/HelveticaNeue.ttc")
ENV_VAR = "SED_REPORTING_FONT"

HTML_FONT_FAMILY = "'Helvetica Neue', Helvetica, Arial, sans-serif"
# reporting's preview CSS sets Consolas/Monaco for numeric cells; the PDF uses the body font.
_PREVIEW_NUMBERS_CSS = "<style>td.right, .calc-work, .util-pct { font-family: inherit; }</style>"


def font_file() -> Path | None:
    """Where Helvetica Neue is read from: SED_REPORTING_FONT, else macOS's copy, else None."""
    configured = os.environ.get(ENV_VAR)
    if configured:
        return Path(configured)
    return _MACOS_COPY if _MACOS_COPY.exists() else None


@functools.cache
def register() -> bool:
    """Register Helvetica Neue with ReportLab (once). False when no copy is available."""
    path = font_file()
    if path is None:
        return False
    if not path.is_file():
        raise FileNotFoundError(f"{ENV_VAR} is set to {path}, which does not exist")
    for name, index in _FACES.items():
        found = TTFontFile(str(path), subfontIndex=index).name
        found = found.decode() if isinstance(found, bytes) else found
        if found != name:
            raise ValueError(f"{path}: face {index} is {found!r}, expected {name!r} "
                             "(Regular, Bold, Italic, Bold Italic as faces 0-3)")
        pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=index))
    # So <b>/<i> inside paragraphs resolve to the right faces.
    pdfmetrics.registerFontFamily(FAMILY, normal="HelveticaNeue", bold="HelveticaNeue-Bold",
                                  italic="HelveticaNeue-Italic", boldItalic="HelveticaNeue-BoldItalic")
    return True


def pdf_theme() -> Theme:
    """The print theme in Helvetica Neue; reporting's own (DejaVu Sans) if no copy is available."""
    if register():
        return replace(PRINT_THEME, pdf_font="HelveticaNeue", pdf_font_bold="HelveticaNeue-Bold")
    return PRINT_THEME


def web_theme() -> Theme:
    return replace(WEB_THEME, html_font_family=HTML_FONT_FAMILY)


def preview_numbers_in_body_font(html: str) -> str:
    """Show the preview's numeric cells in the body font, as in the PDF."""
    assert "</head>" in html, "the preview HTML has no </head>"
    return html.replace("</head>", _PREVIEW_NUMBERS_CSS + "\n</head>", 1)
