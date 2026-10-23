"""The response to a council RFI as a PDF: a draft for review, or the issued copy.

    build_rfi_pdf(pd, number, fetch)   a draft, at any time before submission,
                                       even with errors outstanding (they show
                                       as "[not entered: …]" markers): images
                                       and logo fetched, unsigned
    issue_rfi(pd, number, fetch)       the issued copy, when the engineer submits
                                       it to the architect: the reviewing
                                       engineer's signature and the date, then
                                       locked

The letter alone: the documents it cites (revised drawings, the SCR, the PS1)
stay in the portal, where the architect downloads them. An issued letter is
never regenerated; the portal keeps the signed copy.
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
from sed_reporting.rfi.document import build_document, image_urls, rfi_id, rfi_tag
from sed_reporting.scr.build import Fetch, fetch_url
from sed_reporting.stamp import stamp_page_numbers


class RfiBlocked(Exception):
    """The response has errors to fix first."""

    def __init__(self, issues: list[Issue]):
        super().__init__("; ".join(i.message for i in issues))
        self.issues = issues


class RfiIssued(Exception):
    """The response was already submitted; the portal holds the signed copy."""


def rfi_errors(pd: ProjectData, number: int) -> list[Issue]:
    """Errors blocking the response to RFI <number>: its own, and those blocking every report."""
    return ([i for i in pd.issues() if i.severity == "error" and i.report == "all"]
            + [i for i in pd.rfi_issues(number) if i.severity == "error"])


def _images(pd: ProjectData, number: int, fetch: Fetch) -> tuple[dict[str, bytes], bytes | None]:
    """Fetch every answer's images (an error names any that fail) and the logo (left off if it fails)."""
    images, errors = {}, []
    for url in dict.fromkeys(image_urls(pd, number)):
        try:
            images[url] = fetch_image(fetch, url, f"image {url}")
        except ImageError as e:
            errors.append(Issue("error", "rfi", str(e)))
    if errors:
        raise RfiBlocked(errors)
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


def _not_submitted(pd: ProjectData, number: int) -> None:
    r = pd.rfi_round(number)
    if r is not None and r.issued_at:
        raise RfiIssued(f"the response to {rfi_tag(number)} was submitted at {r.issued_at.isoformat()}; "
                        "the portal keeps the signed copy")


def _check(pd: ProjectData, number: int) -> None:
    _not_submitted(pd, number)
    if errors := rfi_errors(pd, number):
        raise RfiBlocked(errors)


def build_rfi_pdf(pd: ProjectData, number: int, fetch: Fetch = fetch_url) -> bytes:
    """A draft of the response to RFI <number>, unsigned. Errors don't block it:
    it is for reviewing the letter while answers and revisions are still in
    progress. Only an image that can't be fetched does (it can't be printed)."""
    _not_submitted(pd, number)
    images, logo = _images(pd, number, fetch)
    return _bytes(_render(pd, number, images=images, logo=logo))


def issue_rfi(pd: ProjectData, number: int, fetch: Fetch = fetch_url,
              now: datetime | None = None) -> tuple[bytes, datetime]:
    """Issue the response to RFI <number> (the engineer submits it): sign, date
    and lock it. Returns the PDF and the moment of issue (NZ time), which the
    portal saves as the round's issuedAt."""
    _check(pd, number)
    eng = pd.project.internal_reviewing_engineer
    if not eng.signature_url:
        raise RfiBlocked([Issue("error", "rfi", "the response can't be submitted without the reviewing engineer's "
                                                "signature (internalReviewingEngineer.signatureUrl)")])
    try:
        signature = fetch_image(fetch, eng.signature_url, "the reviewing engineer's signature")
    except ImageError as e:
        raise RfiBlocked([Issue("error", "rfi", str(e))]) from e
    images, logo = _images(pd, number, fetch)
    issued_at = now or nz_now()
    writer = _render(pd, number, images=images, logo=logo, signature=signature, issued_at=issued_at)
    writer.add_metadata({"/Title": f"{rfi_id(pd, number)} (issued {issued_at.date().isoformat()})"})
    lock(writer)
    return _bytes(writer), issued_at
