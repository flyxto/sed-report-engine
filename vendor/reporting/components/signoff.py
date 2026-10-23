"""Engineering sign-off block (shared): the conditions of the sign-off, then the
engineer's signature line, name and CPEng number beside a date line.

A missing name or CPEng number prints a fill-in line — those are completed by
hand, so the blank is intentional. There is no date value: the signing date is
handwritten, and a pre-filled date would be wrong if the report is signed later.
The block is kept together on one page in both mediums.
"""

from dataclasses import dataclass, field
from html import escape

from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable, KeepTogether, Paragraph, Spacer, Table, TableStyle

from reporting.core.pdf_style import body_style
from reporting.core.theme import Theme

_BLANK = "_______________________"
_PAD = 12          # outer box padding (pt)
_GAP = 30          # gap between the engineer and date columns (pt)
_SIGN_SPACE = 28   # height left above the signature line (pt)


@dataclass
class Signoff:
    """A sign-off block. Blank `engineer` / `cpeng` print as fill-in lines."""

    engineer: str = ""
    cpeng: str = ""
    conditions: list[str] = field(default_factory=list)
    title: str = "Engineering Sign-Off"

    def render_html(self, theme: Theme) -> str:
        conditions = ""
        if self.conditions:
            items = "".join(f"<li>{escape(c)}</li>" for c in self.conditions)
            conditions = f'<ul class="signoff-conditions">{items}</ul>'
        return (
            '<div class="signoff">'
            f'<div class="signoff-title">{escape(self.title)}</div>'
            f"{conditions}"
            '<div class="signoff-grid">'
            '<div><div class="signoff-label">Structural Engineer:</div><div class="signoff-line"></div>'
            f"<div>Name: {escape(self.engineer) or _BLANK}</div>"
            f"<div>CPEng #: {escape(self.cpeng) or _BLANK}</div></div>"
            '<div><div class="signoff-label">Date:</div><div class="signoff-line"></div></div>'
            "</div></div>"
        )

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        text_s = body_style(theme)
        label_s = body_style(theme, bold=True)
        bullet_s = body_style(theme)
        bullet_s.leftIndent, bullet_s.bulletIndent, bullet_s.bulletFontName = 12, 2, theme.pdf_font

        inner_w = theme.content_width_pt() - 2 * _PAD
        col_w = (inner_w - _GAP) / 2
        sign = Table(
            [
                [Paragraph("Structural Engineer:", label_s), "", Paragraph("Date:", label_s)],
                [Spacer(1, _SIGN_SPACE), "", Spacer(1, _SIGN_SPACE)],
                [Paragraph(f"Name: {escape(self.engineer) or _BLANK}", text_s), "", ""],
                [Paragraph(f"CPEng #: {escape(self.cpeng) or _BLANK}", text_s), "", ""],
            ],
            colWidths=[col_w, _GAP, col_w],
        )
        sign.setStyle(TableStyle([
            ("LINEBELOW", (0, 1), (0, 1), 0.75, HexColor(theme.text)),
            ("LINEBELOW", (2, 1), (2, 1), 0.75, HexColor(theme.text)),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        stack: list[Flowable] = [
            Paragraph(escape(self.title), body_style(theme, size=theme.body_pt + 2, bold=True, color=theme.primary)),
            Spacer(1, 6),
        ]
        for condition in self.conditions:
            stack.append(Paragraph(escape(condition), bullet_s, bulletText="•"))
        if self.conditions:
            stack.append(Spacer(1, 8))
        stack.append(sign)

        box = Table([[stack]], colWidths=[theme.content_width_pt()])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor(theme.row_alt)),
            ("BOX", (0, 0), (-1, -1), 0.75, HexColor(theme.border)),
            ("LEFTPADDING", (0, 0), (-1, -1), _PAD),
            ("RIGHTPADDING", (0, 0), (-1, -1), _PAD),
            ("TOPPADDING", (0, 0), (-1, -1), _PAD),
            ("BOTTOMPADDING", (0, 0), (-1, -1), _PAD),
        ]))
        return [KeepTogether([box, Spacer(1, 10)])]
