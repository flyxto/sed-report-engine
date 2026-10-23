"""HTTP layer (FastAPI). Stateless: every request carries the data it needs.

    GET  /health       -> {"status": "ok"}
    POST /assemble     -> a combined report from element PDFs, application/pdf
    POST /scr/preview  -> {"html": …, "issues": [...]}  for the review page
    POST /scr/pdf      -> the Structural Calculations Report, application/pdf
                          (422 with the issues while errors remain)

    POST /ps1/preview  -> {"html": …, "issues": [...], "form": …}  for the PS1 review page
    POST /ps1/pdf      -> a draft PS1 package (unsigned), application/pdf
    POST /ps1/issue    -> the latest PS1 revision, issued: signed, dated and locked;
                          X-Issued-At gives the moment of issue (ISO, NZ time),
                          X-Document-Id the revision ("P260703-PS1-Rev A"), and
                          X-Cites-Calculations / X-Cites-Drawings what it cites
    (all three: 422 with the issues while errors remain; the PDFs 409 once issued)

    POST /sir/preview?number=1  -> {"html": …, "issues": [...], "form": …}  for a SIR's review page
    POST /sir/pdf?number=1      -> a draft SIR (unsigned), application/pdf
    POST /sir/issue?number=1    -> the issued SIR: signed, dated and locked;
                                   X-Issued-At gives the moment of issue
    (404 for an unknown SIR number; 422 with the issues; the PDFs 409 once issued)

    POST /rfi/preview?number=1  -> {"html": …, "issues": [...], "form": …}  for an RFI response's review page
    POST /rfi/pdf?number=1      -> a draft response to RFI01 (unsigned), application/pdf;
                                   available even while errors remain (only submitting
                                   is blocked by them)
    POST /rfi/issue?number=1    -> the issued response (the engineer submits it to the
                                   architect): signed, dated and locked; X-Issued-At
                                   gives the moment of issue
    (404 for an unknown RFI number; /rfi/issue 422 with the issues; the PDFs 409 once issued)

    POST /ps4/preview  -> {"html": …, "issues": [...], "form": …}  for the PS4 review page
    POST /ps4/pdf      -> a draft PS4 package (unsigned) with its attachments, application/pdf
    POST /ps4/issue    -> the latest PS4 revision, issued: signed, dated and locked;
                          X-Issued-At, X-Document-Id, and X-Cites-Ps1 / X-Cites-Sirs
                          (comma-separated) what it covers
    (422 with the issues while errors remain; the PDFs 409 once issued)

Issuing the PS4: as the PS1. The package is the PS4's own pages followed by the
documents its Schedule lists: every issued SIR (from its pdfUrl), the PS3s and
the builder's Record of Work. The portal saves X-Issued-At, X-Cites-Ps1 and
X-Cites-Sirs on the latest revision (issuedAt, citesPs1, citesSirs).

Submitting an RFI response: as a SIR; the portal saves X-Issued-At as that
round's issuedAt and gives the architect the PDF. The letter alone: the
documents it cites stay in the portal. It can be submitted only when every item
is answered and every document it cites is issued (a revised one: since the
questions were received).

Issuing a SIR: as the PS1, but the portal saves X-Issued-At as that visit's
issuedAt. A SIR can be issued only when every observation has passed, or its
failure has the builder's correction approved by the engineer.

Issuing the PS1: the PS1 has a revision record (reports.ps1.revisions). The
portal calls /ps1/issue, keeps the returned PDF as that revision's issued copy,
saves X-Issued-At, X-Cites-Calculations and X-Cites-Drawings on the latest
revision (issuedAt, citesCalculations, citesDrawings) and locks the PS1 until a
new revision is added. An issued revision is never regenerated here. When the
SCR or the drawing set moves past what it cites, the PS1 needs a new revision.

Issuing a revision: the latest revision with no `issuedOn` is a draft and
prints today's date (New Zealand). The /scr/pdf response carries the document ID
and the date printed in X-Document-Id and X-Revision-Date (ISO), and the drawing
set it cites in X-Cites-Drawings ("" if none is reviewed). To issue the draft,
the portal saves X-Revision-Date as that revision's `issuedOn` and
X-Cites-Drawings as its `citesDrawings`; from then
on the revision, and every reprint of it, keeps that date.

The /scr endpoints take a project file as the body (see data/project_sample.json
and project_data/project.schema.json).

POST /assemble body (JSON):

    {
      "title": "House 3 — Structural Calculations",    required
      "reference": "SED-2026-H3",                      optional, as are site_address,
      "engineer": "…", "date": "…",                    engineer and date
      "filename": "house3",                            download name, default "report"
      "elements": [                                    report order, at least one
        {"name": "Beam B12", "pdf_base64": "JVBERi0…"}
      ]
    }

An element that is not base64, not a PDF, or not stamped is a 422 naming it.
Elements travel inline as base64 for now; fetching them from storage (R2 keys)
is the natural next step once the portal keeps element PDFs there.

Run from this repo's root (the parent dir must be importable, see README):

    .venv/bin/uvicorn sed_reporting.api:app --app-dir ..
"""

from __future__ import annotations

import base64
import binascii
import unicodedata
from dataclasses import asdict
from urllib.parse import quote

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from sed_reporting import __version__
from sed_reporting.assembly import ReportMeta, assemble
from sed_reporting.scr import TITLE as SCR_TITLE, ScrBlocked, build_scr_pdf, fetch_url, render_scr_html
from sed_reporting.scr.build import Fetch
from sed_reporting.scr.document import document_id, report_date
from sed_reporting.scr.form import form_context
from sed_reporting.element import ElementError
from sed_reporting.fonts import pdf_theme
from sed_reporting.project_data import Issue, Project, ProjectData, load_library, nz_today
from sed_reporting.ps1 import (
    TITLE as PS1_TITLE, Ps1Blocked, Ps1Issued, build_ps1_pdf, issue_ps1, ps1_citations, render_ps1_html,
)
from sed_reporting.ps1.form import form_context as ps1_form_context
from sed_reporting.sir import SirBlocked, SirIssued, build_sir_pdf, issue_sir, render_sir_html, sir_id
from sed_reporting.sir.form import form_context as sir_form_context
from sed_reporting.ps4 import Ps4Blocked, Ps4Issued, build_ps4_pdf, issue_ps4, ps4_citations, render_ps4_html
from sed_reporting.ps4.form import form_context as ps4_form_context
from sed_reporting.rfi import RfiBlocked, RfiIssued, build_rfi_pdf, issue_rfi, render_rfi_html, rfi_id
from sed_reporting.rfi.form import form_context as rfi_form_context


class ElementIn(BaseModel):
    name: str = Field("", description="Label used in error messages.")
    pdf_base64: str = Field(..., description="The stamped element PDF, base64-encoded.")


class AssembleRequest(BaseModel):
    title: str = Field(..., pattern=r"\S", description="Combined report title.")
    reference: str = ""
    site_address: str = ""
    engineer: str = ""
    date: str = ""
    filename: str = Field("report", description="Download name; .pdf is added if missing.")
    elements: list[ElementIn] = Field(..., min_length=1, description="Element PDFs in report order.")


def content_disposition(filename: str) -> str:
    """An attachment header that survives any filename.

    Starlette encodes headers as latin-1, so a raw "Ōtautahi.pdf" raises
    UnicodeEncodeError mid-response. Send an ASCII fallback (macrons and other
    accents stripped) plus the RFC 6266 `filename*` form, which browsers prefer.
    """
    name = (filename or "").strip().replace("/", "_").replace("\\", "_") or "report"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    fallback = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    fallback = "".join(ch for ch in fallback if ch.isprintable() and ch not in '"\\') or "report.pdf"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def health() -> dict:
    return {"status": "ok", "pdfFont": pdf_theme().pdf_font}   # "HelveticaNeue", or "DejaVuSans" if it isn't available


def assemble_report(req: AssembleRequest) -> Response:
    """Plain `def`, so FastAPI runs it on its threadpool, off the event loop."""
    names = [e.name or f"element {i}" for i, e in enumerate(req.elements, start=1)]
    pdfs = []
    for name, element in zip(names, req.elements):
        try:
            pdfs.append(base64.b64decode(element.pdf_base64, validate=True))
        except binascii.Error as e:
            raise HTTPException(status_code=422, detail=f"{name}: pdf_base64 is not valid base64 ({e})") from e

    meta = ReportMeta(req.title, req.reference, req.site_address, req.engineer, req.date)
    try:
        pdf = assemble(pdfs, meta, names=names, theme=pdf_theme())
    except ElementError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": content_disposition(req.filename)})


# --- Structural Calculations Report (SCR) ----------------------------------

def get_fetch() -> Fetch:
    """How element calculation reports are downloaded. A dependency, so the
    development server can serve local placeholders instead (dev/server.py)."""
    return fetch_url


def _issues(issues: list[Issue]) -> list[dict]:
    return [asdict(i) for i in issues]


def scr_preview(project: Project) -> dict:
    """The review preview: the report as HTML, every issue (errors block the PDF),
    and what an edit form needs to know (see scr/form.py)."""
    pd = ProjectData(project, load_library())
    return {"html": render_scr_html(pd), "issues": _issues(pd.issues()), "form": form_context(pd)}


def scr_pdf(project: Project, fetch=Depends(get_fetch)) -> Response:
    """The complete report PDF; a 422 listing the issues while errors remain."""
    pd = ProjectData(project, load_library())
    today = nz_today()
    try:
        pdf = build_scr_pdf(pd, fetch, today)
    except ScrBlocked as e:
        raise HTTPException(status_code=422, detail={"message": "the report has errors to fix first",
                                                     "issues": _issues(e.issues)}) from e
    except ElementError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    name = f"{project.project_id} - {SCR_TITLE}"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": content_disposition(name),
        "X-Document-Id": document_id(pd),
        "X-Revision-Date": report_date(pd, today).isoformat(),   # what issuing the draft stamps as issuedOn
        "X-Cites-Drawings": pd.drawing_set.reference if pd.drawing_set else "",   # ... and as citesDrawings
    })


# --- PS1 package -------------------------------------------------------------

def ps1_preview(project: Project) -> dict:
    """The PS1 review preview (a draft, unsigned), every issue, and what an edit
    form needs to know (see ps1/form.py)."""
    pd = ProjectData(project, load_library())
    return {"html": render_ps1_html(pd), "issues": _issues(pd.issues()), "form": ps1_form_context(pd)}


def _ps1_failure(e: Exception) -> HTTPException:
    if isinstance(e, Ps1Issued):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=422, detail={"message": "the PS1 has errors to fix first",
                                                  "issues": _issues(e.issues)})


def ps1_pdf(project: Project) -> Response:
    """A draft PS1 package: unsigned, marked as a draft in its header."""
    try:
        pdf = build_ps1_pdf(ProjectData(project, load_library()))
    except (Ps1Blocked, Ps1Issued) as e:
        raise _ps1_failure(e) from e
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": content_disposition(f"{project.project_id} - PS1 Design (draft)")})


def ps1_issue(project: Project, fetch=Depends(get_fetch)) -> Response:
    """Issue the PS1 package: the reviewing engineer's signature and the date on
    every signature line, then locked against editing."""
    try:
        pd = ProjectData(project, load_library())
        pdf, issued_at = issue_ps1(pd, fetch)
    except (Ps1Blocked, Ps1Issued) as e:
        raise _ps1_failure(e) from e
    cites = ps1_citations(pd)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": content_disposition(f"{pd.ps1_document_id} - {PS1_TITLE.replace('–', '-')}"),
        "X-Document-Id": pd.ps1_document_id,
        # The portal saves these on the latest revision: issuedAt, citesCalculations, citesDrawings.
        "X-Issued-At": issued_at.isoformat(),
        "X-Cites-Calculations": cites["calculations"],
        "X-Cites-Drawings": cites["drawings"],
    })


# --- Site Inspection Reports ------------------------------------------------------

def _visit(project: Project, number: int) -> ProjectData:
    pd = ProjectData(project, load_library())
    if pd.visit(number) is None:
        raise HTTPException(status_code=404, detail=f"the project has no SIR{number:02d}")
    return pd


def sir_preview(project: Project, number: int) -> dict:
    """A SIR's review preview, its issues (its own and those blocking every
    report), and what an edit form needs to know (see sir/form.py)."""
    pd = _visit(project, number)
    issues = [i for i in pd.issues() if i.report == "all"] + pd.sir_issues(number) + pd.office_check_issues()
    return {"html": render_sir_html(pd, number), "issues": _issues(issues), "form": sir_form_context(pd, number)}


def _sir_failure(e: Exception) -> HTTPException:
    if isinstance(e, SirIssued):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=422, detail={"message": "the SIR has errors to fix first",
                                                  "issues": _issues(e.issues)})


def sir_pdf(project: Project, number: int, fetch=Depends(get_fetch)) -> Response:
    """A draft SIR: photos and logo included, unsigned, marked as a draft."""
    pd = _visit(project, number)
    try:
        pdf = build_sir_pdf(pd, number, fetch)
    except (SirBlocked, SirIssued) as e:
        raise _sir_failure(e) from e
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": content_disposition(f"{sir_id(pd, number)} (draft)")})


def sir_issue(project: Project, number: int, fetch=Depends(get_fetch)) -> Response:
    """Issue a SIR: the inspection engineer's signature and the date, then locked."""
    pd = _visit(project, number)
    try:
        pdf, issued_at = issue_sir(pd, number, fetch)
    except (SirBlocked, SirIssued) as e:
        raise _sir_failure(e) from e
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": content_disposition(f"{sir_id(pd, number)} - Site Inspection Report"),
        "X-Issued-At": issued_at.isoformat(),      # the portal saves this as the visit's issuedAt
    })


# --- PS4 -------------------------------------------------------------------------------

def ps4_preview(project: Project) -> dict:
    """The PS4 review preview (its own pages), its issues (its own and those
    blocking every report), and what an edit form needs to know (see ps4/form.py)."""
    pd = ProjectData(project, load_library())
    issues = [i for i in pd.issues() if i.report == "all"] + pd.ps4_issues()
    return {"html": render_ps4_html(pd), "issues": _issues(issues), "form": ps4_form_context(pd)}


def _ps4_failure(e: Exception) -> HTTPException:
    if isinstance(e, Ps4Issued):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=422, detail={"message": "the PS4 has errors to fix first",
                                                  "issues": _issues(e.issues)})


def ps4_pdf(project: Project, fetch=Depends(get_fetch)) -> Response:
    """A draft PS4 package: unsigned, with its attachments, marked as a draft."""
    pd = ProjectData(project, load_library())
    try:
        pdf = build_ps4_pdf(pd, fetch)
    except (Ps4Blocked, Ps4Issued) as e:
        raise _ps4_failure(e) from e
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": content_disposition(f"{pd.ps4_document_id} - PS4 (draft)")})


def ps4_issue(project: Project, fetch=Depends(get_fetch)) -> Response:
    """Issue the PS4 package: the reviewing engineer's signature and the date, then locked."""
    pd = ProjectData(project, load_library())
    try:
        pdf, issued_at = issue_ps4(pd, fetch)
    except (Ps4Blocked, Ps4Issued) as e:
        raise _ps4_failure(e) from e
    cites = ps4_citations(pd)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": content_disposition(f"{pd.ps4_document_id} - PS4 Construction Review"),
        "X-Document-Id": pd.ps4_document_id,
        # The portal saves these on the latest revision: issuedAt, citesPs1, citesSirs (split on commas).
        "X-Issued-At": issued_at.isoformat(),
        "X-Cites-Ps1": cites["ps1"],
        "X-Cites-Sirs": ",".join(cites["sirs"]),
    })


# --- RFI responses ------------------------------------------------------------------

def _rfi_round(project: Project, number: int) -> ProjectData:
    pd = ProjectData(project, load_library())
    if pd.rfi_round(number) is None:
        raise HTTPException(status_code=404, detail=f"the project has no RFI{number:02d}")
    return pd


def rfi_preview(project: Project, number: int) -> dict:
    """An RFI response's review preview, its issues (its own and those blocking
    every report), and what an edit form needs to know (see rfi/form.py)."""
    pd = _rfi_round(project, number)
    issues = [i for i in pd.issues() if i.report == "all"] + pd.rfi_issues(number)
    return {"html": render_rfi_html(pd, number), "issues": _issues(issues), "form": rfi_form_context(pd, number)}


def _rfi_failure(e: Exception) -> HTTPException:
    if isinstance(e, RfiIssued):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=422, detail={"message": "the RFI response has errors to fix first",
                                                  "issues": _issues(e.issues)})


def rfi_pdf(project: Project, number: int, fetch=Depends(get_fetch)) -> Response:
    """A draft RFI response: images and logo included, unsigned, marked as a
    draft. Errors don't block it; outstanding items show as markers."""
    pd = _rfi_round(project, number)
    try:
        pdf = build_rfi_pdf(pd, number, fetch)
    except (RfiBlocked, RfiIssued) as e:
        raise _rfi_failure(e) from e
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": content_disposition(f"{rfi_id(pd, number)} (draft)")})


def rfi_issue(project: Project, number: int, fetch=Depends(get_fetch)) -> Response:
    """Submit an RFI response: the reviewing engineer's signature and the date, then locked."""
    pd = _rfi_round(project, number)
    try:
        pdf, issued_at = issue_rfi(pd, number, fetch)
    except (RfiBlocked, RfiIssued) as e:
        raise _rfi_failure(e) from e
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": content_disposition(f"{rfi_id(pd, number)} - RFI Response"),
        "X-Issued-At": issued_at.isoformat(),      # the portal saves this as the round's issuedAt
    })


PDF_RESPONSE = {"response_class": Response, "responses": {200: {"content": {"application/pdf": {}}}}}

router = APIRouter()
router.get("/health")(health)
router.post("/assemble", **PDF_RESPONSE)(assemble_report)
router.post("/scr/preview")(scr_preview)
router.post("/scr/pdf", **PDF_RESPONSE)(scr_pdf)
router.post("/ps1/preview")(ps1_preview)
router.post("/ps1/pdf", **PDF_RESPONSE)(ps1_pdf)
router.post("/ps1/issue", **PDF_RESPONSE)(ps1_issue)
router.post("/sir/preview")(sir_preview)
router.post("/sir/pdf", **PDF_RESPONSE)(sir_pdf)
router.post("/sir/issue", **PDF_RESPONSE)(sir_issue)
router.post("/ps4/preview")(ps4_preview)
router.post("/ps4/pdf", **PDF_RESPONSE)(ps4_pdf)
router.post("/ps4/issue", **PDF_RESPONSE)(ps4_issue)
router.post("/rfi/preview")(rfi_preview)
router.post("/rfi/pdf", **PDF_RESPONSE)(rfi_pdf)
router.post("/rfi/issue", **PDF_RESPONSE)(rfi_issue)

app = FastAPI(title="sed_reporting", version=__version__)
app.include_router(router)
