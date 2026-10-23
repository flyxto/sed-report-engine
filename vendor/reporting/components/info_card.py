"""Titled key/value cards (shared), single or N-up in a grid.

An `InfoCard` is a boxed title over label/value rows — site details, design
parameters, material properties. `InfoCardGrid` arranges cards `per_row`-up.

An empty value (`None` or "") renders as "—", so a missing value is visible
rather than blank. Anything else goes through `str()` — 0 shows as "0".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from html import escape

from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from reporting.core.pdf_style import body_style
from reporting.core.theme import Theme

_EMPTY = "—"
_GUTTER = 8   # space between cards in a grid (pt)


def _display(value) -> str:
    return _EMPTY if value is None or (isinstance(value, str) and value == "") else str(value)


@dataclass
class InfoCard:
    """A titled card of label/value rows. `rows` may be a mapping or a sequence
    of pairs; it is normalised to a list of (label, value) pairs."""

    title: str
    rows: Sequence[tuple[str, object]] | Mapping[str, object]

    def __post_init__(self) -> None:
        pairs = self.rows.items() if isinstance(self.rows, Mapping) else self.rows
        self.rows = [(str(label), value) for label, value in pairs]

    def render_html(self, theme: Theme) -> str:
        # <td><strong> for labels, not <th>: the global th rule paints header cells navy.
        rows = "".join(
            f"<tr><td><strong>{escape(label)}</strong></td><td>{escape(_display(value))}</td></tr>"
            for label, value in self.rows
        )
        return (
            '<div class="info-card">'
            f'<div class="info-card-title">{escape(self.title)}</div>'
            f"<table>{rows}</table></div>"
        )

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        return [self._flowable(theme, theme.content_width_pt()), Spacer(1, 8)]

    def _flowable(self, theme: Theme, width: float) -> Flowable:
        title_s = body_style(theme, bold=True, color=theme.primary)
        label_s = body_style(theme, bold=True)
        value_s = body_style(theme)
        data = [[Paragraph(escape(self.title), title_s), ""]]
        data += [[Paragraph(escape(label), label_s), Paragraph(escape(_display(value)), value_s)]
                 for label, value in self.rows]
        table = Table(data, colWidths=[width * 0.4, width * 0.6])
        table.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor(theme.border)),
            ("LINEBELOW", (0, 0), (-1, 0), 1, HexColor(theme.primary)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table


@dataclass
class InfoCardGrid:
    """Several info cards arranged `per_row`-up."""

    cards: list[InfoCard] = field(default_factory=list)
    per_row: int = 2

    def render_html(self, theme: Theme) -> str:
        if not self.cards:
            return ""
        cells = "".join(c.render_html(theme) for c in self.cards)
        return f'<div class="info-grid" style="--cols:{self.per_row}">{cells}</div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        if not self.cards:
            return []
        n = max(self.per_row, 1)
        card_w = (theme.content_width_pt() - _GUTTER * (n - 1)) / n
        rows: list[list] = []
        for i in range(0, len(self.cards), n):
            cells: list = [c._flowable(theme, card_w) for c in self.cards[i : i + n]]
            while len(cells) < n:
                cells.append(Spacer(1, 1))
            rows.append(cells)
        # The gutter sits right of every column but the last, so the outer cards
        # line up with the content edges, and with a full-width InfoCard.
        table = Table(rows, colWidths=[card_w + _GUTTER] * (n - 1) + [card_w])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), _GUTTER),
            ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), _GUTTER),
        ]))
        return [table, Spacer(1, 4)]
