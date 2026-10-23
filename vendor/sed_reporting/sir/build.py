"""A Site Inspection Report as a PDF: a draft for review, or the issued copy.

    build_sir_pdf(pd, number, fetch)   a draft: photos and logo fetched, the
                                       signature line shows a placeholder
    issue_sir(pd, number, fetch)       the issued copy: the inspection engineer's
                                       signature and the issue date, then locked

A SIR can be issued only once every observation has passed, or its failure has
the builder's correction approved by the engineer. An issued SIR is never
regenerated; the portal keeps the signed copy.
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
from sed_reporting.scr.build import Fetch, fetch_url
from sed_reporting.sir.document import build_document, photo_urls, sir_id, sir_tag
from sed_reporting.stamp import stamp_page_numbers


class SirBlocked(Exception):
    """The SIR has errors to fix first."""

    def __init__(self, issues: list[Issue]):
        super().__init__("; ".join(i.message for i in issues))
        self.issues = issues


class SirIssued(Exception):
    """The SIR was already issued; the portal holds the signed copy."""


def sir_errors(pd: ProjectData, number: int) -> list[Issue]:
    """Errors blocking SIR <number>: its own, and those blocking every report."""
    return ([i for i in pd.issues() if i.severity == "error" and i.report == "all"]
            + [i for i in pd.sir_issues(number) if i.severity == "error"])


def _images(pd: ProjectData, number: int, fetch: Fetch) -> tuple[dict[str, bytes], bytes | None]:
    """Fetch every photo (an error names any that fail) and the logo (left off if it fails)."""
    images, errors = {}, []
    for url in dict.fromkeys(photo_urls(pd, number)):
        try:
            images[url] = fetch_image(fetch, url, f"photo {url}")
        except ImageError as e:
            errors.append(Issue("error", "sir", str(e)))
    if errors:
        raise SirBlocked(errors)
    cert = pd.project.ps1_certificate_data
    logo = None
    if cert and cert.issuer_logo_url:
        try:
            logo = fetch_image(fetch, cert.issuer_logo_url, "the firm's logo")
        except ImageError:
            logo = None
    return images, logo


def _render(pd: ProjectData, number: int, **kw) -> PdfWriter:
    theme = pdf_theme()
    body = io.BytesIO()
    render_pdf(build_document(pd, number, **kw), body, theme=theme)
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(body.getvalue())))
    stamp_page_numbers(writer, theme)
    return writer


def _bytes(writer: PdfWriter) -> bytes:
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _check(pd: ProjectData, number: int) -> None:
    v = pd.visit(number)
    if v is not None and v.issued_at:
        raise SirIssued(f"{sir_tag(number)} was issued at {v.issued_at.isoformat()}; the portal keeps the signed copy")
    if errors := sir_errors(pd, number):
        raise SirBlocked(errors)


def build_sir_pdf(pd: ProjectData, number: int, fetch: Fetch = fetch_url) -> bytes:
    """A draft of SIR <number>, unsigned."""
    _check(pd, number)
    images, logo = _images(pd, number, fetch)
    return _bytes(_render(pd, number, images=images, logo=logo))


def issue_sir(pd: ProjectData, number: int, fetch: Fetch = fetch_url,
              now: datetime | None = None) -> tuple[bytes, datetime]:
    """Issue SIR <number>: sign, date and lock it. Returns the PDF and the moment
    of issue (NZ time), which the portal saves as the visit's issuedAt."""
    _check(pd, number)
    eng = pd.project.inspection_engineer
    if not eng.signature_url:
        raise SirBlocked([Issue("error", "sir", "the SIR can't be issued without the inspection engineer's "
                                                "signature (inspectionEngineer.signatureUrl)")])
    try:
        signature = fetch_image(fetch, eng.signature_url, "the inspection engineer's signature")
    except ImageError as e:
        raise SirBlocked([Issue("error", "sir", str(e))]) from e
    images, logo = _images(pd, number, fetch)
    issued_at = now or nz_now()
    writer = _render(pd, number, images=images, logo=logo, signature=signature, issued_at=issued_at)
    writer.add_metadata({"/Title": f"{sir_id(pd, number)} (issued {issued_at.date().isoformat()})"})
    lock(writer)
    return _bytes(writer), issued_at
