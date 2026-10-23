"""Design check table (shared): Check | Demand | Capacity | Utilisation | Status.

The calculation module supplies each utilisation; the component never computes
it. Interaction checks (e.g. N*/φNc + M*/φMs <= 1) have no single
demand/capacity pair, so only the module knows the ratio. Demand and capacity
are display strings, already formatted with their units; "" shows as "—".

Validation, pass/fail and the % label follow the one utilisation rule in
core/utilisation.py, which every other place a report shows a utilisation uses
too. Bar colour is this component's own: ok at <= 70 %, warn above 70 % up to
100 %, fail above 100 %. The bar fills min(pct, 100) % of its track.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from reporting.core.pdf_style import TA_CENTER, TA_RIGHT, body_style
from reporting.core.theme import Theme
from reporting.core.utilisation import _ratio, util_label, util_passed, util_pct, util_status

_EMPTY = "—"
_HEADERS = ("Check", "Demand", "Capacity", "Utilisation", "Status")
_WIDTHS = (0.32, 0.16, 0.16, 0.24, 0.12)   # fractions of the content width
_CELL_PAD = 5


@dataclass
class DesignCheck:
    """One design check. `util` is the utilisation ratio the module computed."""

    name: str
    demand: str      # pre-formatted, e.g. "30.1 kNm"; "" renders as "—"
    capacity: str    # pre-formatted; "" renders as "—" (e.g. interaction checks)
    util: float      # utilisation RATIO: 1.0 == 100 %

    def __post_init__(self) -> None:
        self.util = _ratio(self.util, self.name)

    @property
    def pct(self) -> float:
        return util_pct(self.util)

    @property
    def passed(self) -> bool:
        return util_passed(self.util)

    @property
    def label(self) -> str:
        return util_label(self.util)

    @property
    def level(self) -> str:
        """Bar colour class: "ok", "warn" or "fail"."""
        if self.pct > 100:
            return "fail"
        return "warn" if self.pct > 70 else "ok"


@dataclass
class DesignCheckTable:
    """A table of design checks with utilisation bars and OK/FAIL status."""

    checks: list[DesignCheck] = field(default_factory=list)
    font_scale: float = 1.0

    def render_html(self, theme: Theme) -> str:
        if not self.checks:
            return ""
        head = "".join(f"<th>{h}</th>" for h in _HEADERS)
        rows = []
        for c in self.checks:
            cls = "" if c.passed else ' class="fail"'
            badge = "status-pass" if c.passed else "status-fail"
            bar = (
                '<div class="util-cell"><div class="util-bar">'
                f'<div class="util-fill {c.level}" style="width:{min(c.pct, 100):g}%"></div></div>'
                f'<span class="util-pct">{c.label}</span></div>'
            )
            rows.append(
                f"<tr{cls}><td>{escape(c.name)}</td>"
                f'<td class="right">{escape(c.demand or _EMPTY)}</td>'
                f'<td class="right">{escape(c.capacity or _EMPTY)}</td>'
                f"<td>{bar}</td>"
                f'<td class="center"><span class="status-badge {badge}">{util_status(c.util)}</span></td></tr>'
            )
        return f'<table class="design-check-table"><tr>{head}</tr>{"".join(rows)}</table>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        if not self.checks:
            return []
        size = theme.body_pt * self.font_scale
        widths = [theme.content_width_pt() * f for f in _WIDTHS]
        header_s = body_style(theme, size=size, color="#ffffff", bold=True)
        name_s = body_style(theme, size=size)
        num_s = body_style(theme, size=size, align=TA_RIGHT)
        # One label width for the whole table, so every bar track is the same length.
        label_w = max(stringWidth(t, theme.pdf_font, size) for t in ["100%"] + [c.label for c in self.checks])
        bar_w = widths[3] - 2 * _CELL_PAD

        data = [[Paragraph(h, header_s) for h in _HEADERS]]
        for c in self.checks:
            status_s = body_style(theme, size=size, bold=True, color=theme.ok if c.passed else theme.fail, align=TA_CENTER)
            data.append([
                Paragraph(escape(c.name), name_s),
                Paragraph(escape(c.demand or _EMPTY), num_s),
                Paragraph(escape(c.capacity or _EMPTY), num_s),
                _util_bar(c, theme, bar_w, label_w, size),
                Paragraph(util_status(c.util), status_s),
            ])

        table = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(theme.primary)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor(theme.border)),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), _CELL_PAD),
            ("RIGHTPADDING", (0, 0), (-1, -1), _CELL_PAD),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor(theme.row_alt)]),
        ]
        for i, c in enumerate(self.checks):
            if not c.passed:
                style.append(("BACKGROUND", (0, i + 1), (-1, i + 1), HexColor(theme.fail_bg)))
        table.setStyle(TableStyle(style))
        return [table, Spacer(1, 8)]


def _util_bar(check: DesignCheck, theme: Theme, width: float, label_w: float, size: float) -> Drawing:
    """A rounded grey track, a coloured fill and the % label right-aligned beside it."""
    colour = {"ok": theme.ok, "warn": theme.warn, "fail": theme.fail}[check.level]
    height = size * 1.4
    bar_h = size * 0.75
    y = (height - bar_h) / 2
    track_w = max(width - label_w - 4, 1)
    fill_w = track_w * min(check.pct, 100) / 100

    d = Drawing(width, height)
    d.add(Rect(0, y, track_w, bar_h, rx=bar_h / 2, ry=bar_h / 2, fillColor=HexColor(theme.border), strokeColor=None))
    if fill_w > 0:
        r = min(bar_h, fill_w) / 2
        d.add(Rect(0, y, fill_w, bar_h, rx=r, ry=r, fillColor=HexColor(colour), strokeColor=None))
    d.add(String(width, height / 2 - size * 0.35, check.label, fontName=theme.pdf_font, fontSize=size,
                 fillColor=HexColor(theme.text), textAnchor="end"))
    return d
