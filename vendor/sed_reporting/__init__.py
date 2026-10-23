"""sed_reporting — assembles element report PDFs into one combined report.

Design modules (beams, pf, rafts, …) render their own element PDFs with
`reporting` and stamp each with `reporting.stamp_manifest`. This package takes a
set of those PDFs and returns one document: contents page(s), every element in
order, bookmarks, and uniform "Page X of Y" numbering. It never imports analysis
code.

Public API
----------
    assemble(elements, meta, names=None, theme=PRINT_THEME) -> bytes
    read_element(pdf, name) -> ElementInfo        validate one element PDF
    ReportMeta, ElementInfo, Section, ElementError

HTTP service: `sed_reporting.api:app` (FastAPI), see api.py.
"""

__version__ = "0.1.0"

from sed_reporting.assembly import ReportMeta, assemble  # noqa: E402
from sed_reporting.element import ElementError, ElementInfo, Section, read_element  # noqa: E402

__all__ = [
    "assemble",
    "read_element",
    "ReportMeta",
    "ElementInfo",
    "Section",
    "ElementError",
]
