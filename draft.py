"""Draft PDFs for review.

`sed_reporting` refuses a PDF while errors remain, so an incomplete portal
project can be previewed but not downloaded. A draft uses the same document
the preview shows, including the "[not entered]" markers. Issuing stays
refused until those errors are fixed.
"""

from __future__ import annotations

from sed_reporting.project_data import ProjectData, load_library
from sed_reporting.project_data.project import Project
from sed_reporting.ps1.build import _bytes, _render
from sed_reporting.scr.document import render_scr_body_pdf


def draft_pdf(kind: str, project: Project) -> bytes | None:
    """The review PDF, or None when this kind has no draft path."""
    pd = ProjectData(project, load_library())
    if kind == "ps1":
        writer, _theme = _render(pd)
        return _bytes(writer)
    if kind == "scr":
        return render_scr_body_pdf(pd)
    return None
