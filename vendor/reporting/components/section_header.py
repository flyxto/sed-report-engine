"""Section heading component (shared across all structural modules)."""

from dataclasses import dataclass
from html import escape

from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable, HRFlowable, PageBreak, Paragraph, Spacer

from reporting.core.outline import OutlineEntry
from reporting.core.pdf_style import heading_style
from reporting.core.theme import Theme


@dataclass
class SectionHeader:
    """A numbered/section heading. `level` 2 -> h2 (ruled), 3 -> h3."""

    title: str
    level: int = 2
    page_break_before: bool = False

    def render_html(self, theme: Theme) -> str:
        cls = ' class="page-break"' if self.page_break_before else ""
        return f"<h{self.level}{cls}>{escape(self.title)}</h{self.level}>"

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        out: list[Flowable] = []
        if self.page_break_before:
            out.append(PageBreak())
        # PDF bookmark: h2 -> outline level 1, h3 -> level 2 (below the doc title at 0).
        out.append(OutlineEntry(self.title, level=max(1, self.level - 1)))
        size = 14.0 if self.level <= 2 else 11.0
        out.append(Paragraph(escape(self.title), heading_style(theme, size=size)))
        if self.level <= 2:
            out.append(HRFlowable(color=HexColor(theme.primary), thickness=2, spaceBefore=2, spaceAfter=8, width="100%"))
        else:
            out.append(Spacer(1, 4))
        return out
