"""The complete Structural Calculations Report PDF: the report body, then
Appendix A, a table of contents followed by each element's calculation report,
merged with page numbers and bookmarks across the whole document.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Callable
from datetime import date

from sed_reporting.assembly import ReportMeta, assemble
from sed_reporting.fonts import pdf_theme
from sed_reporting.scr.document import TITLE, render_scr_body_pdf
from sed_reporting.element import ElementError
from sed_reporting.project_data import Issue, ProjectData

Fetch = Callable[[str], bytes]


class ScrBlocked(ValueError):
    """The report can't be issued while errors remain; `issues` lists them."""

    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


def fetch_url(url: str) -> bytes:
    """Download an element's calculation report (e.g. from Cloudflare R2)."""
    if not url.startswith("https://"):
        raise ValueError(f"refusing to fetch {url!r}: only https URLs are allowed")
    with urllib.request.urlopen(url, timeout=30) as response:   # noqa: S310 - https enforced above
        return response.read()


def build_scr_pdf(pd: ProjectData, fetch: Fetch = fetch_url, today: date | None = None) -> bytes:
    """The complete report PDF. Raises ScrBlocked while SCR errors remain, and
    ElementError naming any element whose calculation report can't be fetched
    or isn't stamped."""
    errors = [i for i in pd.issues() if i.severity == "error" and i.report in ("scr", "all")]
    if errors:
        raise ScrBlocked(errors)

    pdfs, names = [], []
    for r in pd.design_items:                       # the order of section 4
        name = f"element {r.element.id} ({r.element.type})"
        try:
            pdfs.append(fetch(r.element.calculation_report_url))
        except Exception as e:  # noqa: BLE001 - any fetch failure blocks the report, naming the element
            raise ElementError(f"{name}: could not fetch its calculation report ({type(e).__name__}: {e})") from e
        names.append(name)

    p = pd.project
    meta = ReportMeta(TITLE, reference=p.project_id, site_address=p.site_address)
    return assemble(pdfs, meta, names=names, lead=render_scr_body_pdf(pd, today), theme=pdf_theme())
