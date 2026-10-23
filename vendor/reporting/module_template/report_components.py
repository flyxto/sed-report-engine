"""Domain-specific components for THIS module.

Most domain components just *arrange shared components* — see RibEdgeTable,
which turns this module's edge results into the shared DataTable. Only drop to
raw ReportLab if no shared component can express what you need.
"""

from dataclasses import dataclass
from typing import Any

from reportlab.platypus import Flowable

from reporting import Column, DataTable, Theme, util_label, util_passed, util_status


@dataclass
class RibEdgeTable:
    """Example domain component: a per-edge table specific to this module."""

    edges: list[Any]

    def _as_table(self) -> DataTable:
        cols = [
            Column("Edge"),
            Column("M* (kNm)", align="right"),
            Column("φMn⁻ (kNm)", align="right"),
            Column("Util", align="right"),
            Column("Status", align="center"),
        ]
        # Labels, statuses and fail rows all come from the one utilisation rule.
        rows = [[e.name, e.m_star, e.phi_mn, util_label(e.util), util_status(e.util)] for e in self.edges]
        fails = {i for i, e in enumerate(self.edges) if not util_passed(e.util)}
        return DataTable(cols, rows, fail_rows=fails, font_scale=0.95)

    # A component just delegates both mediums — here, to a shared component.
    def render_html(self, theme: Theme) -> str:
        return self._as_table().render_html(theme)

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        return self._as_table().render_pdf(theme)
