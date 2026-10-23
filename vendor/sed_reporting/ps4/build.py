"""The PS4 package as a PDF: a draft for checking, or the issued, signed copy.

    build_ps4_pdf(pd, fetch)   a draft: the signature line shows a placeholder,
                               the header says "DRAFT, not issued"
    issue_ps4(pd, fetch)       the issued copy of the latest revision: the
                               reviewing engineer's signature and the issue
                               date, then the whole package is locked
    ps4_citations(pd)          what the issued copy covers (the PS1 revision and
                               the SIRs), which the portal stores on the revision

The package: the PS4's own pages (numbered among themselves, "Page 1 of 3"), then
the documents its Schedule lists, as they are, each with a bookmark: every
issued SIR (the portal keeps each signed PDF: pdfUrl), the PS3s from the steel
fabricator, the builder's Record of Work. Issued SIRs are locked but open
without a password, so they can be appended; a document that needs a password
to open can't, and blocks the package, named.

As for the PS1: a revision record (reports.ps4.revisions); each revision is
issued once and then locked; a new PS1 revision, or a SIR issued since, means a
new PS4 revision.
"""

from __future__ import annotations

import io
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from pypdf.errors import DependencyError

from reporting import render_pdf

from sed_reporting.fonts import pdf_theme
from sed_reporting.issuing import ImageError, fetch_image, lock
from sed_reporting.project_data import Issue, ProjectData
from sed_reporting.project_data.dates import nz_now
from sed_reporting.ps4.document import attachments, build_document
from sed_reporting.scr.build import Fetch, fetch_url
from sed_reporting.stamp import stamp_page_numbers


class Ps4Blocked(Exception):
    """The PS4 has errors to fix first."""

    def __init__(self, issues: list[Issue]):
        super().__init__("; ".join(i.message for i in issues))
        self.issues = issues


class Ps4Issued(Exception):
    """The PS4's latest revision was already issued; the portal holds the signed copy."""


def ps4_errors(pd: ProjectData) -> list[Issue]:
    """Errors blocking the PS4: its own, and those blocking every report."""
    return ([i for i in pd.issues() if i.severity == "error" and i.report == "all"]
            + [i for i in pd.ps4_issues() if i.severity == "error"])


def ps4_citations(pd: ProjectData) -> dict[str, object]:
    """What the PS4 covers as it stands: the PS1's latest issued revision and the
    issued SIRs. The portal stores them on the revision it issues (citesPs1,
    citesSirs), so a later PS1 revision or SIR shows the PS4 is out of date."""
    return {"ps1": pd.ps1_issued_id or "", "sirs": [pd.sir_id(v.number) for v in pd.issued_sirs]}


def _not_issued(pd: ProjectData) -> None:
    if pd.ps4_issued_at:
        raise Ps4Issued(f"{pd.ps4_document_id} was issued at {pd.ps4_issued_at.isoformat()}; the portal keeps the "
                        "signed copy (add a revision to revise the PS4)")


def _attached(pd: ProjectData, fetch: Fetch) -> list[tuple[str, PdfReader]]:
    """Fetch and open every attachment; an error names each that fails."""
    out, errors = [], []
    for label, url in attachments(pd):
        try:
            reader = PdfReader(io.BytesIO(fetch(url)))
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("it needs a password to open")
            out.append((label, reader))
        except DependencyError:           # AES-encrypted: pypdf needs `cryptography` (a declared dependency)
            errors.append(Issue("error", "ps4", f"{label}: could not attach {url}: it is AES-encrypted and the "
                                                "`cryptography` package is missing from this installation"))
        except Exception as e:  # noqa: BLE001 - any failure blocks the package, naming the document
            errors.append(Issue("error", "ps4", f"{label}: could not attach {url} ({type(e).__name__}: {e})"))
    if errors:
        raise Ps4Blocked(errors)
    return out


def _package(pd: ProjectData, fetch: Fetch, **kw) -> PdfWriter:
    """The PS4's pages, numbered among themselves, then the attachments, bookmarked."""
    theme = pdf_theme()
    attached = _attached(pd, fetch)
    body = io.BytesIO()
    render_pdf(build_document(pd, **kw), body, theme=theme)
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(body.getvalue())), import_outline=True)    # the PS4's title, its sections nested
    stamp_page_numbers(writer, theme)                      # "Page 1 of N": the form's own pages
    for label, reader in attached:
        start = len(writer.pages)
        writer.append(reader, import_outline=False)
        writer.add_outline_item(label, start)
    return writer


def _bytes(writer: PdfWriter) -> bytes:
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def build_ps4_pdf(pd: ProjectData, fetch: Fetch = fetch_url, now: datetime | None = None) -> bytes:
    """A draft PS4 package, unsigned, with its attachments. Raises Ps4Blocked
    while errors remain, and Ps4Issued once the latest revision is issued."""
    _not_issued(pd)
    if errors := ps4_errors(pd):
        raise Ps4Blocked(errors)
    return _bytes(_package(pd, fetch, now=now))


def issue_ps4(pd: ProjectData, fetch: Fetch = fetch_url, now: datetime | None = None) -> tuple[bytes, datetime]:
    """Issue the PS4 package: sign, date and lock it. Returns the PDF and the
    moment of issue (NZ time), which the portal saves on the latest revision
    with ps4_citations(pd)."""
    _not_issued(pd)
    errors = ps4_errors(pd)
    eng = pd.project.internal_reviewing_engineer
    if eng is not None:
        for label, value in (("signature (internalReviewingEngineer.signatureUrl)", eng.signature_url),
                             ("CPEng number (internalReviewingEngineer.cpengNumber)", eng.cpeng_number)):
            if not value:
                errors.append(Issue("error", "ps4", f"the PS4 can't be issued without the reviewing engineer's {label}"))
    if errors:
        raise Ps4Blocked(errors)
    try:
        signature = fetch_image(fetch, eng.signature_url, "the reviewing engineer's signature")
    except ImageError as e:
        raise Ps4Blocked([Issue("error", "ps4", str(e))]) from e
    issued_at = now or nz_now()
    writer = _package(pd, fetch, signature=signature, issued_at=issued_at)
    writer.add_metadata({"/Title": f"{pd.ps4_document_id} - PS4 Construction Review (issued {issued_at.date().isoformat()})"})
    lock(writer)
    return _bytes(writer), issued_at
