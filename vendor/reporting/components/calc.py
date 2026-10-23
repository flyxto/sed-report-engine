"""Calculation block component (shared) — step-by-step engineering working.

A `CalcBlock` renders a sequence of `CalcRow`s as a calc sheet: for each step a
description, the working (formula → substitution → result as one expression),
and a code clause reference. This is what the *detailed* (HTML) report uses to
"break down every step"; the summary report leans on result tables instead.

Both mediums:
- render_html: a definition-style calc block; the working is monospace so
  aligned "=" reads like a hand calc.
- render_pdf: a 3-column ReportLab table (Description | Working = Result | Ref).
"""

from dataclasses import dataclass, field
from html import escape

from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from reporting.core.pdf_style import TA_LEFT, TA_RIGHT, body_style
from reporting.core.theme import Theme


@dataclass
class CalcRow:
    """One line of working. `expr` is the formula and/or substitution; `result`
    is the value; `ref` is the clause. Any may be empty."""

    label: str
    expr: str = ""
    result: str = ""
    ref: str = ""


@dataclass
class CalcBlock:
    """A titled block of calc rows (a single derivation / check)."""

    title: str
    rows: list[CalcRow] = field(default_factory=list)

    def _working(self, r: CalcRow) -> str:
        if r.expr and r.result:
            return f"{r.expr} = {r.result}"
        return r.expr or r.result

    def render_html(self, theme: Theme) -> str:
        head = f'<div class="calc-title">{escape(self.title)}</div>' if self.title else ""
        rows = []
        for r in self.rows:
            ref = f'<span class="calc-ref">{escape(r.ref)}</span>' if r.ref else ""
            rows.append(
                '<div class="calc-row">'
                f'<span class="calc-label">{escape(r.label)}</span>'
                f'<span class="calc-work">{escape(self._working(r))}</span>'
                f"{ref}</div>"
            )
        return f'<div class="calc-block">{head}{"".join(rows)}</div>'

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        out: list[Flowable] = []
        if self.title:
            out.append(Paragraph(escape(self.title), body_style(theme, bold=True, color=theme.primary)))
            out.append(Spacer(1, 3))

        label_s = body_style(theme, align=TA_LEFT)
        work_s = body_style(theme, align=TA_LEFT)
        ref_s = body_style(theme, size=max(theme.body_pt - 1, 6), color=theme.muted, align=TA_RIGHT)

        data = [[
            Paragraph(escape(r.label), label_s),
            Paragraph(escape(self._working(r)), work_s),
            Paragraph(escape(r.ref), ref_s),
        ] for r in self.rows]

        cw = theme.content_width_pt()
        table = Table(data, colWidths=[cw * 0.26, cw * 0.58, cw * 0.16])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, HexColor(theme.border)),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
        ]))
        out += [table, Spacer(1, 8)]
        return out
