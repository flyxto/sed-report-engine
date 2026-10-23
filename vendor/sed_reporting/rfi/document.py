"""The response to a council's Request for Further Information (RFI01, RFI02, …),
built from a resolved project. Content follows the firm's RFI letter template
(samples/rfi_reference/), in our theme:

    letterhead · project reference and date · the council (To the Building
    Official) · subject: consent number and site address · each request: the
    council's heading and text in a quoted box, our answer, its images, and the
    documents it cites (revised or not) · closing · signature

The council's text is typed text, as the architect pasted it, not a screen
grab. Until issue, the date and signature are placeholders; on issue (the
engineer submits) they carry the reviewing engineer's signature and the date
(build.issue_rfi).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime

from reporting import DocMeta, ReportDocument, SectionHeader, render_html

from sed_reporting.components import Letterhead, Lines, Photos, Prose, Quote, Signature, missing
from sed_reporting.fonts import preview_numbers_in_body_font, web_theme
from sed_reporting.project_data import ProjectData
from sed_reporting.project_data.dates import long_date, nz_date
from sed_reporting.project_data.resolve import revision_letter
from sed_reporting.ps1.document import TITLE as PS1_TITLE
from sed_reporting.scr.document import TITLE as SCR_TITLE, drawings_cited, next_drawings_cited

TITLE = "Response to Request for Further Information"


def rfi_tag(number: int) -> str:
    return f"RFI{number:02d}"


def rfi_id(pd: ProjectData, number: int) -> str:
    """The document ID: "<job number>-RFI01"."""
    return f"{pd.project.project_id}-{rfi_tag(number)}"


def image_urls(pd: ProjectData, number: int) -> list[str]:
    """Every image in the answers."""
    return [u for it in pd.rfi_round(number).items for u in it.images]


@dataclass(frozen=True)
class AsSubmitted:
    """The documents as the letter will cite them when it is submitted. The
    letter goes out last, once everything it depends on has been amended, so a
    draft cites each document at the revision it will then have."""

    drawings: str                      # "Example Architects Ltd (P260703-DRG-Rev B)[, dated …]"
    calculations: str                  # "Structural Calculations Report P260703-SCR-Rev C[, dated …]"
    ps1: str                           # "Producer Statement – PS1 Design P260703-PS1-Rev B[, issued …]"


def as_submitted(pd: ProjectData, r) -> AsSubmitted:
    """Each document at the revision it will have when RFI round `r` is
    submitted. A revision that exists and is issued is cited with its date;
    one still to come (or a draft) without one.

    drawings      the next revision if an answer revises them and no review has
                  been completed since the RFI was received; else the current one
    calculations  the SCR's draft revision if there is one; else the next
                  revision if the RFI revises the calculations and none was
                  issued since it was received, or if the SCR cites drawings
                  other than those above; else the latest
    PS1           its draft revision if there is one; else the next revision if
                  an answer revises it and none was issued since the RFI was
                  received, or if the issued one cites other SCR or drawing
                  revisions than those above (or there is none); else the latest
    """
    p, pid = pd.project, pd.project.project_id
    reviews = p.drawing_reviews
    pending = (any(it.drawings == "revised" for it in r.items)
               and not any(d.completed_at > r.received_at for d in reviews))
    drawings_ref = f"{pid}-DRG-Rev {revision_letter(len(reviews))}" if pending else \
        (pd.drawing_set.reference if pd.drawing_set else "")
    drawings = next_drawings_cited(pd) if pending else drawings_cited(pd)

    scr = p.reports.scr.revisions
    if scr and scr[-1].issued_on is None:                      # a draft, to be issued before the letter
        scr_index, scr_date = len(scr) - 1, None
    else:
        calcs_revised = any(it.calculations == "revised" for it in r.items)
        needs_new = (not scr or (calcs_revised and scr[-1].issued_on < nz_date(r.received_at))
                     or (scr[-1].cites_drawings or "") != drawings_ref)
        scr_index, scr_date = (len(scr), None) if needs_new else (len(scr) - 1, scr[-1].issued_on)
    scr_ref = f"{pid}-SCR-Rev {revision_letter(scr_index)}"
    calculations = f"{SCR_TITLE} {scr_ref}" + (f", dated {long_date(scr_date)}" if scr_date else "")

    ps1 = p.reports.ps1.revisions
    if ps1 and ps1[-1].issued_at is None:                      # a draft, to be issued before the letter
        ps1_index, ps1_issued = len(ps1) - 1, None
    else:
        ps1_revised = any(it.ps1 == "revised" for it in r.items)
        needs_new = (not ps1 or (ps1_revised and ps1[-1].issued_at <= r.received_at)
                     or ps1[-1].cites_calculations != scr_ref or ps1[-1].cites_drawings != drawings_ref)
        ps1_index, ps1_issued = (len(ps1), None) if needs_new else (len(ps1) - 1, ps1[-1].issued_at)
    ps1_text = f"{PS1_TITLE} {pid}-PS1-Rev {revision_letter(ps1_index)}" + \
        (f", issued {long_date(ps1_issued.date())}" if ps1_issued else "")
    return AsSubmitted(drawings, calculations, ps1_text)


def cited(pd: ProjectData, r, it) -> list[str]:
    """The documents an answer cites, one line each, as the letter will cite
    them when it is submitted (as_submitted). Submitting is blocked until they
    are all issued, so the submitted letter carries every date."""
    docs, out = as_submitted(pd, r), []
    if it.drawings:
        sheets = f", sheets {it.drawing_sheets}" if it.drawing_sheets else ""
        out.append(f"{'Revised drawings' if it.drawings == 'revised' else 'Drawings'}: {docs.drawings}{sheets}.")
    if it.calculations:
        out.append(f"{'Revised calculations' if it.calculations == 'revised' else 'Calculations'}: {docs.calculations}.")
    if it.ps1:
        out.append(f"{'Revised PS1' if it.ps1 == 'revised' else 'PS1'}: {docs.ps1}.")
    return out


def build_document(pd: ProjectData, number: int, *, images: dict[str, bytes] | None = None,
                   logo: bytes | None = None, signature: bytes | None = None,
                   issued_at: datetime | None = None) -> ReportDocument:
    """The response to RFI <number>. `images` (url -> bytes) and `logo` are given
    for the PDF; `signature` and `issued_at` on issue only."""
    p, r = pd.project, pd.rfi_round(number)
    tag, cert, eng = rfi_tag(number), p.ps1_certificate_data, p.internal_reviewing_engineer
    firm = pd.firm_name or missing("engineering firm, from the portal")
    short = (cert.issuer_short_name or cert.issuer) if cert else firm
    consent = p.building_consent_number or missing("consent number, from the portal")
    council = pd.b2_addressee or [p.territorial_authority or missing("council")]
    phone = cert.issuer_phone if cert and cert.issuer_phone else missing("the firm's phone, from the portal")

    letterhead = [x for x in (cert.issuer if cert else "", cert.issuer_postal_address if cert else "",
                              cert.issuer_phone if cert else "", cert.issuer_website if cert else "") if x]
    body: list = [
        Letterhead(letterhead, logo_url=cert.issuer_logo_url if cert else "", logo=logo),
        Lines([f"Project Reference: {p.project_id}",
               long_date(issued_at.date()) if issued_at else "(dated when submitted)"]),
        Lines(["To the Building Official,", *council]),
        Prose("Dear Sir/Madam,"),
        Lines([f"{consent} – Request for Further Information", p.site_address], bold=True),
        Prose(f"Please find below our answers to the requests for further information raised on "
              f"{long_date(r.raised_on)}."),
    ]

    for k, it in enumerate(r.items, start=1):
        body += [SectionHeader(f"{k}. {it.heading}" if it.heading else f"Request {k}", level=3),
                 Quote(it.question),
                 Lines(["Our response"], bold=True),
                 Prose(it.answer, keep_lines=True) if it.answer.strip() else Prose(missing("the engineer's answer")),
                 Photos(it.images, images, max_height_mm=120.0, per_row=1, alt="image")]
        if refs := cited(pd, r, it):
            body.append(Lines(refs))

    name = eng.name if eng else missing("reviewing engineer, from the portal")
    chartered = ""
    if eng and eng.chartered_status:
        chartered = eng.chartered_status + (f" (CPEng {eng.cpeng_number})" if eng.cpeng_number else "")
    body += [Prose(f"If you have any questions, please feel free to call our office on {phone}."),
             Prose(f"For and on behalf of {short}"),
             Signature(image=signature, date=long_date(issued_at.date()) if issued_at else ""),
             Lines([x for x in (name, ", ".join(eng.qualifications) if eng else "", eng.position if eng else "",
                                chartered) if x])]

    header = p.building_consent_number or p.name
    meta = DocMeta(title=f"{TITLE} {tag}", reference=p.project_id, site_address=p.site_address,
                   engineer=eng.name if eng else "",
                   header_text=f"{header} – RFI Answers ({tag})" + ("" if issued_at else " – DRAFT, not submitted"),
                   footer_left=rfi_id(pd, number))
    return ReportDocument(meta=meta, body=body)


def render_rfi_html(pd: ProjectData, number: int) -> str:
    """The response to RFI <number> as one HTML page: the review preview. Images
    and the logo load from their URLs; never carries the signature (the portal
    keeps the signed PDF)."""
    out = io.StringIO()
    render_html(build_document(pd, number, issued_at=pd.rfi_round(number).issued_at), out, theme=web_theme())
    return preview_numbers_in_body_font(out.getvalue())
