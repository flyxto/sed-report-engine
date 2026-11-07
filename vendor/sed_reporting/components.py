"""Report components the reports need and `reporting` doesn't provide: prose,
a quoted box, a bullet list, lines, tick lines, a cover page, a page break, a
signature, photos and a letterhead. Each renders to both HTML and PDF, like
`reporting`'s own components. Shared by the reports.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from html import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Image, PageBreak as RLPageBreak, Paragraph, Spacer, Table, TableStyle

from reporting import DataTable, Theme
from reporting.core.pdf_style import body_style

MISSING = "[not entered: {}]"


def missing(label: str) -> str:
    """A visible marker for a value the engineer still has to enter."""
    return MISSING.format(label)


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _lines_kept(text: str, br: str) -> str:
    """Escaped text with its line breaks kept (`br`: "<br>" or "<br/>")."""
    return br.join(escape(l) for l in text.split("\n"))


@dataclass
class Prose:
    """One or more paragraphs; a blank line separates paragraphs. With
    `keep_lines`, a single line break is kept too (typed or pasted text, such
    as a council's RFI or the engineer's answer)."""

    text: str
    keep_lines: bool = False

    def render_html(self, theme: Theme) -> str:
        return "".join(f'<p style="margin:0 0 8px">{_lines_kept(p, "<br>") if self.keep_lines else escape(p)}</p>'
                       for p in _paragraphs(self.text))

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        style = body_style(theme, name="prose")
        out: list[Flowable] = []
        for p in _paragraphs(self.text):
            out += [Paragraph(_lines_kept(p, "<br/>") if self.keep_lines else escape(p), style), Spacer(1, 5)]
        return out


@dataclass
class Quote:
    """Quoted text in a shaded box with a rule down its left side: a council's
    request, printed as typed text (line breaks kept) above the answer."""

    text: str

    def render_html(self, theme: Theme) -> str:
        paras = "".join(f'<p style="margin:0 0 6px">{_lines_kept(p, "<br>")}</p>' for p in _paragraphs(self.text))
        return (f'<blockquote style="margin:4px 0 10px;padding:8px 12px 2px;background:{theme.row_alt};'
                f'border-left:3px solid {theme.primary}">{paras}</blockquote>')

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        style = body_style(theme, name="quote")
        cell = [Paragraph(_lines_kept(p, "<br/>"), style) for p in _paragraphs(self.text)]
        table = Table([[cell]], colWidths=[theme.content_width_pt()], hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor(theme.row_alt)),
                                   ("LINEBEFORE", (0, 0), (0, -1), 2.5, HexColor(theme.primary)),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                                   ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        return [table, Spacer(1, 8)]


@dataclass
class Bullets:
    items: list[str] = field(default_factory=list)

    def render_html(self, theme: Theme) -> str:
        items = "".join(f"<li>{escape(i)}</li>" for i in self.items)
        return f'<ul style="margin:0 0 8px 20px">{items}</ul>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        style = body_style(theme, name="bullet")
        style.leftIndent, style.bulletIndent = 12, 2
        style.bulletFontName = theme.pdf_font      # else ReportLab's base-14 font, whose "•" copies out as \x7f
        return [Paragraph(escape(i), style, bulletText="•") for i in self.items] + [Spacer(1, 5)]


@dataclass
class CoverLine:
    text: str
    size: float = 11.0
    bold: bool = False
    space_after: float = 4.0


@dataclass
class CoverPage:
    """Centred cover lines, followed by a page break."""

    lines: list[CoverLine] = field(default_factory=list)
    logo_url: str = ""                                # the logo shown in the preview
    logo: bytes | None = None                         # the fetched logo, for the PDF
    logo_height_mm: float = 22.0

    def render_html(self, theme: Theme) -> str:
        rows = "".join(
            f'<div style="font-size:{l.size}pt;{"font-weight:bold;" if l.bold else ""}margin-bottom:{l.space_after}pt">'
            f"{escape(l.text)}</div>" for l in self.lines)
        logo = (f'<img alt="logo" src="{escape(self.logo_url)}" style="height:{self.logo_height_mm}mm;margin-bottom:24px">'
                if self.logo_url else "")
        return f'<div style="text-align:center;padding:40px 0">{logo}{rows}</div><div class="page-break"></div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        out: list[Flowable] = []
        if self.logo:
            height = self.logo_height_mm * mm
            w, h = ImageReader(io.BytesIO(self.logo)).getSize()
            out += [Spacer(1, 40), Image(io.BytesIO(self.logo), width=height * w / h, height=height), Spacer(1, 40)]
        else:
            out.append(Spacer(1, 120))
        for l in self.lines:
            style = body_style(theme, name="cover", size=l.size, bold=l.bold, align=TA_CENTER,
                               color=theme.primary if l.bold else None)
            out += [Paragraph(escape(l.text), style), Spacer(1, l.space_after)]
        return out + [RLPageBreak()]


@dataclass
class LogoHeader:
    """The firm's logo, left-aligned above the first heading (no page break)."""

    logo_url: str = ""                                # the logo shown in the preview
    logo: bytes | None = None                         # the fetched logo, for the PDF
    height_mm: float = 16.0

    def render_html(self, theme: Theme) -> str:
        if not self.logo_url:
            return ""
        return f'<div style="margin-bottom:12px"><img alt="logo" src="{escape(self.logo_url)}" style="height:{self.height_mm}mm"></div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        if not self.logo:
            return []
        height = self.height_mm * mm
        w, h = ImageReader(io.BytesIO(self.logo)).getSize()
        image = Image(io.BytesIO(self.logo), width=height * w / h, height=height)
        image.hAlign = "LEFT"
        return [image, Spacer(1, 10)]


@dataclass
class PageBreak:
    def render_html(self, theme: Theme) -> str:
        return '<div class="page-break"></div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        return [RLPageBreak()]


@dataclass
class Lines:
    """Lines printed one under another, without paragraph spacing (an address block)."""

    lines: list[str] = field(default_factory=list)
    bold: bool = False                  # e.g. a letter's subject lines

    def render_html(self, theme: Theme) -> str:
        text = "<br>".join(escape(l) for l in self.lines)
        return f'<p style="margin:0 0 8px">{f"<b>{text}</b>" if self.bold else text}</p>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        text = "<br/>".join(escape(l) for l in self.lines)
        return [Paragraph(f"<b>{text}</b>" if self.bold else text, body_style(theme, name="lines")), Spacer(1, 5)]


@dataclass
class Ticks:
    """Statements with a tick box: ✔ when it applies, ☐ when it doesn't."""

    items: list[tuple[bool, str]] = field(default_factory=list)

    def render_html(self, theme: Theme) -> str:
        rows = "".join(f'<div style="margin:0 0 6px 4px"><span style="display:inline-block;width:1.4em">'
                       f'{"✔" if on else "☐"}</span>{escape(text)}</div>' for on, text in self.items)
        return f'<div style="margin:0 0 8px">{rows}</div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        style = body_style(theme, name="tick")
        style.leftIndent, style.bulletIndent = 16, 2
        style.bulletFontName = "DejaVuSans"     # Helvetica Neue has no tick or box; reporting registers DejaVu Sans
        return [Paragraph(escape(text), style, bulletText="✔" if on else "☐") for on, text in self.items] + [Spacer(1, 5)]


SIGNATURE_PLACEHOLDER = "Signed electronically on issue"


@dataclass
class Signature:
    """A signature line: the engineer's signature image and the date once the
    document is issued; a placeholder until then."""

    image: bytes | None = None          # PNG or JPEG
    date: str = ""                      # the issue date, e.g. "10 October 2026"
    label: str = "Signature"
    height_mm: float = 14.0

    def render_html(self, theme: Theme) -> str:
        if self.image:
            kind = "png" if self.image[:8] == b"\x89PNG\r\n\x1a\n" else "jpeg"
            mark = (f'<img alt="signature" style="height:{self.height_mm}mm" '
                    f'src="data:image/{kind};base64,{base64.b64encode(self.image).decode()}">')
        else:
            mark = (f'<span style="display:inline-block;border:1px dashed {theme.border};padding:8px 14px;'
                    f'color:{theme.muted}">{SIGNATURE_PLACEHOLDER}</span>')
        date = escape(self.date) if self.date else f'<span style="color:{theme.muted}">on issue</span>'
        return (f'<table style="margin:6px 0 10px;border:none"><tr>'
                f'<td style="border:none;padding-right:10px"><b>{escape(self.label)}:</b></td>'
                f'<td style="border:none;padding-right:30px">{mark}</td>'
                f'<td style="border:none"><b>Date:</b> {date}</td></tr></table>')

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        style = body_style(theme, name="signature")
        if self.image:
            w, h = ImageReader(io.BytesIO(self.image)).getSize()
            height = self.height_mm * mm
            mark: Flowable | Paragraph = Image(io.BytesIO(self.image), width=height * w / h, height=height)
        else:
            mark = Paragraph(f'<font color="{theme.muted}">{SIGNATURE_PLACEHOLDER}</font>', style)
        date = escape(self.date) if self.date else f'<font color="{theme.muted}">on issue</font>'
        table = Table([[Paragraph(f"<b>{escape(self.label)}:</b>", style), mark, Paragraph(f"<b>Date:</b> {date}", style)]],
                      colWidths=[25 * mm, 75 * mm, None], hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return [table, Spacer(1, 8)]


@dataclass
class SizedTable(DataTable):
    """A DataTable with set column widths, as ratios of the content width. Its
    content-based sizing lets one long text column squeeze the others to a few
    letters wide; a form's tables need fixed proportions."""

    widths: list[float] = field(default_factory=list)

    def _column_widths(self, theme: Theme, size: float) -> list[float] | None:
        if len(self.widths) != len(self.columns):
            return super()._column_widths(theme, size)
        total = theme.content_width_pt()
        return [w / sum(self.widths) * total for w in self.widths]


def downscale(image: bytes, max_px: int = 1600, quality: int = 82) -> bytes:
    """A site photo made fit for a PDF: upright (EXIF orientation applied), at most
    `max_px` on its long side, JPEG. Phone photos are ~3 MB each; this keeps a
    report with a dozen of them to a few MB."""
    from PIL import Image as PILImage, ImageOps
    with PILImage.open(io.BytesIO(image)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_px, max_px))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=quality, optimize=True)
        return out.getvalue()


@dataclass
class Photos:
    """Photos two to a row (or `per_row`). The preview loads them from their
    URLs; the PDF uses the fetched images (`images`: url -> bytes), scaled down.
    One to a row suits screenshots, whose text must stay legible."""

    urls: list[str] = field(default_factory=list)
    images: dict[str, bytes] | None = None
    max_height_mm: float = 55.0
    per_row: int = 2
    alt: str = "site photo"

    def render_html(self, theme: Theme) -> str:
        if not self.urls:
            return ""
        width = 100 / self.per_row - 2
        imgs = "".join(f'<img alt="{escape(self.alt)}" src="{escape(u)}" style="width:{width:g}%;'
                       f'max-height:{self.max_height_mm}mm;object-fit:contain;margin:0 1% 6px 0;'
                       f'border:1px solid {theme.border}">' for u in self.urls)
        return f'<div style="margin:4px 0 8px">{imgs}</div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        if not self.urls:
            return []
        n, gap = self.per_row, 4 * mm
        cell_w = (theme.content_width_pt() - gap * (n - 1)) / n
        cells = []
        for u in self.urls:
            data = downscale((self.images or {})[u])
            w, h = ImageReader(io.BytesIO(data)).getSize()
            scale = min(cell_w / w, self.max_height_mm * mm / h)
            cells.append(Image(io.BytesIO(data), width=w * scale, height=h * scale))
        rows = [cells[i:i + n] + [""] * (n - len(cells[i:i + n])) for i in range(0, len(cells), n)]
        table = Table(rows, colWidths=[cell_w + gap] * (n - 1) + [cell_w], hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return [table, Spacer(1, 6)]


@dataclass
class Letterhead:
    """The firm's logo and details across the top of a letter-style report."""

    lines: list[str] = field(default_factory=list)    # firm name first, then address, phone, website
    logo_url: str = ""
    logo: bytes | None = None                         # the fetched logo, for the PDF
    height_mm: float = 16.0

    def render_html(self, theme: Theme) -> str:
        logo = (f'<img alt="logo" src="{escape(self.logo_url)}" style="height:{self.height_mm}mm;margin-right:14px">'
                if self.logo_url else "")
        text = "<br>".join(f"<b>{escape(l)}</b>" if i == 0 else escape(l) for i, l in enumerate(self.lines))
        return (f'<div style="display:flex;align-items:center;border-bottom:2px solid {theme.primary};'
                f'padding-bottom:8px;margin-bottom:12px">{logo}<div style="font-size:9pt">{text}</div></div>')

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        style = body_style(theme, name="letterhead", size=8.5)
        text = Paragraph("<br/>".join(f"<b>{escape(l)}</b>" if i == 0 else escape(l)
                                      for i, l in enumerate(self.lines)), style)
        if self.logo:
            w, h = ImageReader(io.BytesIO(self.logo)).getSize()
            height = self.height_mm * mm
            row, widths = [Image(io.BytesIO(self.logo), width=height * w / h, height=height), text], [height * w / h + 6 * mm, None]
        else:
            row, widths = [text], [None]
        table = Table([row], colWidths=widths, hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("LINEBELOW", (0, 0), (-1, -1), 1.5, HexColor(theme.primary))]))
        return [table, Spacer(1, 10)]
