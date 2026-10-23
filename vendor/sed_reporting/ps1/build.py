"""The PS1 package as a PDF: a draft for review, or the issued, signed copy.

    build_ps1_pdf(pd)          a draft: signature lines show a placeholder, the
                               header says "DRAFT, not issued"
    issue_ps1(pd, fetch)       the issued copy of the latest revision: the
                               reviewing engineer's signature image and the
                               issue date on every signature line, then the
                               PDF is locked
    ps1_citations(pd)          what the issued copy cites (the SCR revision and
                               the drawing set), which the portal stores on the
                               revision

The PS1 has a revision record (reports.ps1.revisions): Rev A, B, … Each is
issued once. After issue the portal keeps the PDF and the PS1 is locked: a
project whose latest PS1 revision is issued is refused here, until a new
revision is added. A new revision is needed when the SCR or the drawing set
moves past what the issued PS1 cites.

Locking: see issuing.py (printable and copyable, not editable; not a
cryptographic signature).
"""

from __future__ import annotations

import io
from datetime import datetime

from pypdf import PdfReader, PdfWriter

from reporting import render_pdf

from sed_reporting.fonts import pdf_theme
from sed_reporting.issuing import ImageError, fetch_image, lock
from sed_reporting.project_data import Issue, ProjectData
from sed_reporting.project_data.dates import nz_now
from sed_reporting.ps1.document import build_document
from sed_reporting.scr.build import Fetch, fetch_url
from sed_reporting.scr.document import document_id
from sed_reporting.stamp import stamp_page_numbers


class Ps1Blocked(Exception):
    """The PS1 has errors to fix first."""

    def __init__(self, issues: list[Issue]):
        super().__init__("; ".join(i.message for i in issues))
        self.issues = issues


class Ps1Issued(Exception):
    """The PS1 was already issued; the portal holds the signed copy."""


def _errors(pd: ProjectData) -> list[Issue]:
    return [i for i in pd.issues() if i.severity == "error" and i.report in ("ps1", "all")]


def _render(pd: ProjectData, **kw) -> tuple[PdfWriter, object]:
    theme = pdf_theme()
    body = io.BytesIO()
    render_pdf(build_document(pd, **kw), body, theme=theme)
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(body.getvalue())))
    stamp_page_numbers(writer, theme)
    return writer, theme


def _bytes(writer: PdfWriter) -> bytes:
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def build_ps1_pdf(pd: ProjectData, now: datetime | None = None) -> bytes:
    """A draft PS1 package, unsigned. Raises Ps1Blocked while PS1 errors remain,
    and Ps1Issued once it has been issued."""
    if pd.ps1_issued_at:
        raise Ps1Issued(f"{pd.ps1_document_id} was issued at {pd.ps1_issued_at.isoformat()}; the portal keeps "
                        "the signed copy (add a revision to revise the PS1)")
    if errors := _errors(pd):
        raise Ps1Blocked(errors)
    writer, _theme = _render(pd, now=now)
    return _bytes(writer)


def issue_ps1(pd: ProjectData, fetch: Fetch = fetch_url, now: datetime | None = None) -> tuple[bytes, datetime]:
    """Issue the PS1 package: sign, date and lock it. Returns the PDF and the
    moment of issue (New Zealand time), which the portal saves as the latest
    revision's issuedAt, with ps1_citations(pd)."""
    if pd.ps1_issued_at:
        raise Ps1Issued(f"{pd.ps1_document_id} was already issued at {pd.ps1_issued_at.isoformat()}; "
                        "add a revision to revise the PS1")
    errors = _errors(pd)
    eng = pd.project.internal_reviewing_engineer
    if eng is not None:
        for label, value in (("signature (internalReviewingEngineer.signatureUrl)", eng.signature_url),
                             ("CPEng number (internalReviewingEngineer.cpengNumber)", eng.cpeng_number)):
            if not value:
                errors.append(Issue("error", "ps1", f"the PS1 can't be issued without the reviewing engineer's {label}"))
    # Everything the PS1 cites must be ready: the SCR revision issued, the drawing set reviewed.
    revisions = pd.project.reports.scr.revisions
    if revisions and not revisions[-1].issued_on:
        errors.append(Issue("error", "ps1", "the PS1 can't be issued while the Structural Calculations Report "
                                            "revision it cites is a draft: issue that revision first"))
    if pd.drawing_set is None:
        errors.append(Issue("error", "ps1", "the PS1 can't be issued before the drawing set it cites has a "
                                            "completed review (drawingReviews)"))
    elif revisions and revisions[-1].issued_on and (changes := pd.scr_out_of_date):
        errors.append(Issue("error", "ps1", f"the PS1 can't be issued while the SCR revision it cites "
                                            f"({pd.scr_last_issued_label}) cites drawings that have since been "
                                            f"revised ({'; '.join(changes)}): issue a new SCR revision first"))
    if errors:
        raise Ps1Blocked(errors)

    try:
        image = fetch_image(fetch, eng.signature_url, "the reviewing engineer's signature")
    except ImageError as e:
        raise Ps1Blocked([Issue("error", "ps1", str(e))]) from e

    issued_at = now or nz_now()
    writer, _theme = _render(pd, signature=image, issued_at=issued_at)
    writer.add_metadata({"/Title": f"{pd.ps1_document_id} - PS1 Design (issued {issued_at.date().isoformat()})"})
    lock(writer)
    return _bytes(writer), issued_at


def ps1_citations(pd: ProjectData) -> dict[str, str]:
    """What the PS1 cites as it stands, which issuing requires to be ready: the
    SCR's latest revision and the drawing set's. The portal stores them on the
    revision it issues (citesCalculations, citesDrawings), so a later SCR or
    drawing revision shows the PS1 is out of date."""
    return {"calculations": document_id(pd) or "", "drawings": pd.drawing_set.reference if pd.drawing_set else ""}
