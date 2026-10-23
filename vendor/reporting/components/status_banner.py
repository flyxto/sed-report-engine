"""Pass/fail status banner (shared)."""

from dataclasses import dataclass
from html import escape

from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from reporting.core.pdf_style import body_style
from reporting.core.theme import Theme


@dataclass
class StatusBanner:
    """A prominent PASS/FAIL banner with a headline and optional subtext."""

    passed: bool
    headline: str
    subtext: str = ""

    def render_html(self, theme: Theme) -> str:
        state = "pass" if self.passed else "fail"
        badge = "status-pass" if self.passed else "status-fail"
        label = "PASS" if self.passed else "FAIL"
        sub = f"<p>{escape(self.subtext)}</p>" if self.subtext else ""
        return (
            f'<div class="status-banner {state}">'
            f'<h2><span class="status-badge status-badge-large {badge}">{label}</span> {escape(self.headline)}</h2>'
            f"{sub}</div>"
        )

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        badge = theme.ok if self.passed else theme.fail
        bg = theme.ok_bg if self.passed else theme.fail_bg
        label = "PASS" if self.passed else "FAIL"
        cells = [[Paragraph(f'<font color="{badge}"><b>{label}</b></font> &nbsp; <b>{escape(self.headline)}</b>', body_style(theme, size=13))]]
        if self.subtext:
            cells.append([Paragraph(escape(self.subtext), body_style(theme))])
        table = Table(cells, colWidths=[theme.content_width_pt()])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor(bg)),
                    ("BOX", (0, 0), (-1, -1), 1.2, HexColor(badge)),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        return [table, Spacer(1, 10)]
