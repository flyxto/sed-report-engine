"""Summary card grid — demonstrates the grid-as-Table emulation.

HTML uses real CSS grid. PDF emulates the same layout with a single-row
ReportLab Table of N equal columns, each cell a stacked label/value/detail.
This is the core trick for porting grid/flex layouts to ReportLab.
"""

from dataclasses import dataclass, field
from html import escape

from reportlab.lib.colors import HexColor, white
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from reporting.core.pdf_style import TA_CENTER, body_style
from reporting.core.theme import Theme


@dataclass
class Card:
    """A single summary card: an uppercase label, a big value, a small detail."""

    label: str
    value: str
    detail: str = ""


@dataclass
class SummaryCardGrid:
    """A row of equal-width cards."""

    cards: list[Card] = field(default_factory=list)

    def render_html(self, theme: Theme) -> str:
        items = "".join(
            '<div class="summary-card">'
            f'<div class="label">{escape(c.label)}</div>'
            f'<div class="value">{escape(c.value)}</div>'
            f'<div class="detail">{escape(c.detail)}</div>'
            "</div>"
            for c in self.cards
        )
        return f'<div class="summary-grid">{items}</div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        label_s = body_style(theme, size=7, color=theme.muted, align=TA_CENTER)
        value_s = body_style(theme, size=13, color=theme.primary, bold=True, align=TA_CENTER)
        detail_s = body_style(theme, size=7, color=theme.muted, align=TA_CENTER)

        row = []
        for c in self.cards:
            stack: list[Flowable] = [
                Paragraph(escape(c.label).upper(), label_s),
                Spacer(1, 3),
                Paragraph(escape(c.value), value_s),
            ]
            if c.detail:
                stack.extend([Spacer(1, 3), Paragraph(escape(c.detail), detail_s)])
            row.append(stack)

        n = max(len(self.cards), 1)
        col_w = theme.content_width_pt() / n
        table = Table([row], colWidths=[col_w] * n)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor(theme.row_alt)),
                    ("BOX", (0, 0), (-1, -1), 0.5, HexColor(theme.border)),
                    # White inner grid fakes the inter-card gap.
                    ("INNERGRID", (0, 0), (-1, -1), 4, white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return [table, Spacer(1, 10)]
