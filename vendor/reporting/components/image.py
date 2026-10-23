"""Diagram / image component (shared across all structural modules).

Renders a vector (or raster) diagram to both mediums from one payload:
- `render_html`: inline SVG (responsive) or a base64 <img> for PNG, with an
  optional caption.
- `render_pdf`: SVG -> `svglib.svg2rlg` -> a ReportLab Drawing (vector),
  uniformly scaled to a fraction of the content width; or PNG -> an Image.

Modules produce diagrams however they like — Plotly SVG (beams `plotting.py`),
matplotlib, a raw PNG — and hand the result here via `from_svg` / `from_png` /
`from_matplotlib`. The component is source-agnostic; only the payload differs.

`DiagramGrid` arranges several diagrams N-up in a row (e.g. load-case pages).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from html import escape
from io import BytesIO

from reportlab.graphics.shapes import Drawing
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from svglib.svglib import svg2rlg

from reporting.core.pdf_style import TA_CENTER, body_style
from reporting.core.theme import Theme


def _svg_to_drawing(svg: str) -> Drawing | None:
    return svg2rlg(BytesIO(svg.encode("utf-8")))


def _scale_drawing(drawing: Drawing, target_w: float, max_h: float | None = None) -> Drawing:
    """Uniformly scale a Drawing to `target_w` (respecting `max_h`), centred."""
    w0 = drawing.width or 1.0
    h0 = drawing.height or 1.0
    s = target_w / w0
    if max_h and h0 * s > max_h:
        s = max_h / h0
    drawing.width = w0 * s
    drawing.height = h0 * s
    drawing.scale(s, s)
    drawing.hAlign = "CENTER"
    return drawing


def _svg_inline(svg: str) -> str:
    """Strip any XML/doctype prolog so the <svg> embeds cleanly in HTML flow."""
    i = svg.find("<svg")
    return svg[i:] if i != -1 else svg


@dataclass
class Diagram:
    """A single diagram, rendered vector-first to both mediums.

    width_frac: fraction of the content width to occupy (0-1).
    max_height_pt: optional cap on PDF height (keeps tall plots on the page).
    """

    svg: str | None = None
    png: bytes | None = None
    caption: str | None = None
    width_frac: float = 1.0
    max_height_pt: float | None = None

    # --- constructors ------------------------------------------------------
    @classmethod
    def from_svg(cls, svg: str, **kw) -> "Diagram":
        return cls(svg=svg, **kw)

    @classmethod
    def from_png(cls, png: bytes, **kw) -> "Diagram":
        return cls(png=png, **kw)

    @classmethod
    def from_matplotlib(cls, fig, dpi: int = 200, **kw) -> "Diagram":
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        return cls(png=buf.getvalue(), **kw)

    # --- rendering ---------------------------------------------------------
    def render_html(self, theme: Theme) -> str:
        if self.svg:
            inner = _svg_inline(self.svg)
        elif self.png:
            b64 = base64.b64encode(self.png).decode("ascii")
            inner = f'<img src="data:image/png;base64,{b64}" alt="diagram">'
        else:
            return ""
        cap = f"<figcaption>{escape(self.caption)}</figcaption>" if self.caption else ""
        return f'<figure class="diagram">{inner}{cap}</figure>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        target_w = theme.content_width_pt() * max(0.05, min(self.width_frac, 1.0))
        flow = self._flowable(target_w)
        if flow is None:
            return []
        out: list[Flowable] = [flow]
        if self.caption:
            cap_s = body_style(theme, size=max(theme.body_pt - 1, 6), color=theme.muted, align=TA_CENTER)
            out += [Spacer(1, 2), Paragraph(escape(self.caption), cap_s)]
        out.append(Spacer(1, 8))
        return [KeepTogether(out)]

    def _flowable(self, target_w: float) -> Flowable | None:
        if self.svg:
            drawing = _svg_to_drawing(self.svg)
            if drawing is None:
                return None
            return _scale_drawing(drawing, target_w, self.max_height_pt)
        if self.png:
            ir = ImageReader(BytesIO(self.png))
            iw, ih = ir.getSize()
            w, h = target_w, target_w * ih / iw
            if self.max_height_pt and h > self.max_height_pt:
                h, w = self.max_height_pt, self.max_height_pt * iw / ih
            img = RLImage(BytesIO(self.png), width=w, height=h)
            img.hAlign = "CENTER"
            return img
        return None


@dataclass
class DiagramGrid:
    """Several diagrams arranged `per_row`-up in a row (e.g. load cases 3-up)."""

    diagrams: list[Diagram] = field(default_factory=list)
    per_row: int = 3

    def render_html(self, theme: Theme) -> str:
        cells = "".join(d.render_html(theme) for d in self.diagrams)
        return f'<div class="diagram-grid" style="--cols:{self.per_row}">{cells}</div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        if not self.diagrams:
            return []
        n = max(self.per_row, 1)
        cell_w = theme.content_width_pt() / n
        target_w = cell_w * 0.92  # scale each diagram to its COLUMN (minus a gutter)
        cap_s = body_style(theme, size=max(theme.body_pt - 1, 6), color=theme.muted, align=TA_CENTER)
        rows: list[list] = []
        for i in range(0, len(self.diagrams), n):
            chunk = self.diagrams[i : i + n]
            cells: list = []
            for d in chunk:
                stack: list[Flowable] = []
                f = d._flowable(target_w)
                if f is not None:
                    stack.append(f)
                if d.caption:
                    stack += [Spacer(1, 2), Paragraph(escape(d.caption), cap_s)]
                cells.append(stack or Spacer(1, 1))
            while len(cells) < n:
                cells.append(Spacer(1, 1))
            rows.append(cells)
        table = Table(rows, colWidths=[cell_w] * n)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return [table, Spacer(1, 6)]
