"""The Component protocol — the single contract between structural modules
and the reporting engine.

A component knows only how to draw *itself* in each medium. It does not
decide where it appears (that is the View / assembler's job) nor the output
format (that is the engine's job). View, Medium and Theme are orthogonal.
"""

from typing import Protocol, runtime_checkable

from reportlab.platypus import Flowable

from reporting.core.theme import Theme


@runtime_checkable
class Component(Protocol):
    """A report element that can render itself to both mediums."""

    def render_html(self, theme: Theme) -> str:
        """Return an HTML fragment for the screen/detailed medium."""
        ...

    def render_pdf(self, theme: Theme) -> list[Flowable]:
        """Return ReportLab flowables for the PDF medium."""
        ...
