"""Generic data table (shared) with per-column alignment, zebra striping,
repeating header across page breaks, and per-row fail highlighting.

Column widths are distributed equally across the content width by default; set
`autosize=True` for content-proportional widths (each column sized to the wider
of its header and its widest cell, then scaled to fill). Equal widths remain the
default so that existing reports are unaffected — opt in per table. Cells are
Paragraphs, so anything too long wraps rather than overflowing the page.

A header may contain "\\n" to force an explicit line break. Wide tables often
cannot fit their headers on one line at any column width (13 engineering columns
need ~660pt against A4 portrait's 510pt), so the header *must* break — and
breaking it where the author intends beats letting it split mid-token
("w* (k / N/m)"). Write Column("w*\\n(kN/m)") and you get exactly that.

Only headers get the line-break treatment; cell values are escaped as before.
"""

from dataclasses import dataclass, field
from html import escape

from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from reporting.core.pdf_style import TA_CENTER, TA_LEFT, TA_RIGHT, body_style
from reporting.core.theme import Theme

_ALIGN = {"left": TA_LEFT, "right": TA_RIGHT, "center": TA_CENTER}

# Horizontal padding applied per cell by the TableStyle below (LEFT + RIGHT).
_CELL_PADDING_PT = 10.0


def _header_markup(text: str) -> str:
    """Escape a header, then re-introduce its explicit line breaks."""
    return escape(str(text)).replace("\n", "<br/>")


@dataclass
class Column:
    """A table column: header text and cell alignment.

    `header` may contain "\\n" to force a line break at that point.
    """

    header: str
    align: str = "left"       # left | right | center


@dataclass
class DataTable:
    """A tabular block. `rows` are lists of already-formatted strings."""

    columns: list[Column]
    rows: list[list[str]] = field(default_factory=list)
    fail_rows: set[int] = field(default_factory=set)   # 0-based row indices to flag
    font_scale: float = 1.0
    autosize: bool = False    # True -> content-proportional column widths (PDF)

    def render_html(self, theme: Theme) -> str:
        head = "".join(f"<th>{_header_markup(col.header)}</th>" for col in self.columns)
        body_rows = []
        for r, row in enumerate(self.rows):
            cls = ' class="fail"' if r in self.fail_rows else ""
            cells = "".join(
                f'<td class="{col.align}">{escape(str(val))}</td>' if col.align != "left" else f"<td>{escape(str(val))}</td>"
                for col, val in zip(self.columns, row)
            )
            body_rows.append(f"<tr{cls}>{cells}</tr>")
        return f'<table class="data-table"><tr>{head}</tr>{"".join(body_rows)}</table>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        size = theme.body_pt * self.font_scale
        header_s = body_style(theme, size=size, color="#ffffff", bold=True)
        cell_styles = [body_style(theme, size=size, align=_ALIGN[col.align]) for col in self.columns]

        data = [[Paragraph(_header_markup(col.header), header_s) for col in self.columns]]
        for row in self.rows:
            data.append([Paragraph(escape(str(val)), cell_styles[i]) for i, val in enumerate(row)])

        table = Table(data, colWidths=self._column_widths(theme, size), repeatRows=1)

        style = [
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(theme.primary)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor(theme.border)),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor(theme.row_alt)]),
        ]
        for idx in self.fail_rows:
            style.append(("BACKGROUND", (0, idx + 1), (-1, idx + 1), HexColor(theme.fail_bg)))
        table.setStyle(TableStyle(style))
        return [table, Spacer(1, 8)]

    def _column_widths(self, theme: Theme, size: float) -> list[float] | None:
        """Column widths in points.

        Equal by default. With `autosize=True`, each column's natural width is
        the widest of its header lines and its cells plus padding, scaled to
        fill the content width. Scaling preserves the ratios whether the natural
        total is under the page width (columns grow) or over it (they shrink
        together, so a narrow column is never squeezed to fit a wide neighbour).
        """
        n = len(self.columns)
        if n == 0:
            return None

        content_w = theme.content_width_pt()
        if not self.autosize:
            return [content_w / n] * n

        natural = []
        for j, col in enumerate(self.columns):
            widest = max(
                stringWidth(part, theme.pdf_font_bold, size)
                for part in col.header.split("\n")
            )
            for row in self.rows:
                if j < len(row):
                    for part in str(row[j]).split("\n"):
                        widest = max(widest, stringWidth(part, theme.pdf_font, size))
            natural.append(widest + _CELL_PADDING_PT)

        total = sum(natural)
        if total <= 0:
            return [content_w / n] * n
        return [w * content_w / total for w in natural]
