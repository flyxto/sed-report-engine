"""The contents page(s) at the front of a combined report, built from `reporting`
components so it shares the elements' theme, fonts and page furniture.

The project details go in a plain key/value DataTable. `reporting` 0.2.0 has an
InfoCard (the PS1 and PS4 use it); this page could switch to it too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reporting import Column, DataTable, DocMeta, ReportDocument, SectionHeader

from sed_reporting.element import ElementInfo

if TYPE_CHECKING:
    from sed_reporting.assembly import ReportMeta

CONTENTS_TITLE = "Table of Contents"      # the page heading and its PDF bookmark


def contents_rows(elements: list[ElementInfo], start_pages: list[int]) -> list[list[str]]:
    """One row per element: title, reference, and its 1-based start page."""
    return [[e.title, e.reference or "—", str(page)] for e, page in zip(elements, start_pages)]


def contents_document(meta: ReportMeta, elements: list[ElementInfo], start_pages: list[int], *,
                      with_details: bool = True) -> ReportDocument:
    """The contents document for `elements`, whose pages start at `start_pages`.

    with_details: open with the report title and project details. Off when the
    contents follows a report body that already carries them (e.g. the SCR's
    Appendix A).
    """
    if not with_details:
        return ReportDocument(
            meta=DocMeta(title=meta.title, reference=meta.reference, header_text=meta.title, footer_left=meta.reference),
            body=[SectionHeader(CONTENTS_TITLE, level=2),
                  DataTable([Column("Element"), Column("Ref"), Column("Page", align="right")],
                            contents_rows(elements, start_pages), autosize=True)],
        )
    details = [
        [label, value]
        for label, value in (
            ("Reference", meta.reference),
            ("Site", meta.site_address),
            ("Engineer", meta.engineer),
            ("Date", meta.date),
        )
        if value
    ]
    body = [SectionHeader(meta.title, level=2)]
    if details:
        body.append(DataTable([Column("Item"), Column("Detail")], details, autosize=True))
    body.append(SectionHeader(CONTENTS_TITLE, level=2))
    body.append(
        DataTable(
            [Column("Element"), Column("Ref"), Column("Page", align="right")],
            contents_rows(elements, start_pages),
            autosize=True,
        )
    )
    return ReportDocument(
        meta=DocMeta(title=meta.title, reference=meta.reference, header_text=meta.title, footer_left=meta.reference),
        body=body,
    )
