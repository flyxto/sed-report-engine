"""A Site Inspection Report (SIR01, SIR02, …), built from a resolved project.
Content follows the sample in samples/sir_reference/, in our theme:

    letterhead · inspection details (report number, date, reference, project,
    site, CM level, site contact, inspected by, consent, council) · each item
    inspected: element, checklist item, drawing reference, observations (photos,
    Pass/Fail, and for a failure the required correction, the notices sent,
    and each correction with the engineer's review) ·
    actions required · sign-off

Until issue, the signature line shows a placeholder; on issue it carries the
inspection engineer's signature and the issue date (build.issue_sir).
"""

from __future__ import annotations

import io
from datetime import datetime

from reporting import DocMeta, InfoCard, ReportDocument, SectionHeader, render_html

from sed_reporting.components import Letterhead, Lines, Photos, Prose, Signature, missing
from sed_reporting.fonts import preview_numbers_in_body_font, web_theme
from sed_reporting.project_data import ProjectData
from sed_reporting.project_data.dates import long_date, long_date_time

TITLE = "Site Inspection Report"


def sir_tag(number: int) -> str:
    return f"SIR{number:02d}"


def sir_id(pd: ProjectData, number: int) -> str:
    """The document ID: "<job number>-SIR01"."""
    return f"{pd.project.project_id}-{sir_tag(number)}"


def council_name(pd: ProjectData) -> str:
    return pd.council.name if pd.council else pd.project.territorial_authority


def action_text(pd: ProjectData, action: str) -> str:
    """A standard action with the project's council filled in."""
    return action.replace("{council}", council_name(pd) or "the council")


def photo_urls(pd: ProjectData, number: int) -> list[str]:
    """Every photo in a SIR: observations' and corrections'."""
    v = pd.visit(number)
    urls = []
    for it in v.items:
        for o in it.observations:
            urls += o.photos + [u for c in o.corrections for u in c.photos]
    return urls


def build_document(pd: ProjectData, number: int, *, images: dict[str, bytes] | None = None,
                   logo: bytes | None = None, signature: bytes | None = None,
                   issued_at: datetime | None = None) -> ReportDocument:
    """SIR <number>. `images` (url -> bytes) and `logo` are given for the PDF;
    `signature` and `issued_at` on issue only."""
    p, v = pd.project, pd.visit(number)
    tag, cert, eng = sir_tag(number), p.ps1_certificate_data, p.inspection_engineer
    firm = pd.firm_name or missing("engineering firm, from the portal")
    inspector = eng.name if eng else missing("inspection engineer, from the portal")
    contact = (" · ".join(x for x in (v.site_contact.name, v.site_contact.phone) if x) if v.site_contact
               else missing("site contact, from the inspection order"))
    ds = pd.drawing_set

    letterhead = [x for x in (cert.issuer if cert else "", cert.issuer_postal_address if cert else "",
                              cert.issuer_phone if cert else "", cert.issuer_website if cert else "") if x]
    body: list = [
        Letterhead(letterhead, logo_url=cert.issuer_logo_url if cert else "", logo=logo),
        SectionHeader(f"{TITLE} {tag}", level=2),
        InfoCard("Inspection", [
            ("Report number", tag),
            ("Inspection date", long_date(v.inspection_date) or missing("inspection date, from the app")),
            ("Reference", p.project_id), ("Project", p.name), ("Site address", p.site_address),
            ("Construction monitoring level", p.reports.ps1.construction_monitoring_level),
            ("Site contact", contact), ("Inspected by", inspector),
            ("Consent number", p.building_consent_number or missing("consent number, from the portal")),
            ("Territorial authority", council_name(pd) or missing("council")),
        ]),
    ]

    for n, it in enumerate(v.items, start=1):
        drawing = (f"{ds.reference}" if ds else missing("reviewed drawing set")) + \
                  (f", {it.drawing_sheets}" if it.drawing_sheets else "")
        body += [
            SectionHeader(f"{n}. {it.element or it.inspection}", level=3),
            InfoCard("Structural element inspected", [
                ("Element", it.element or it.inspection), ("Checklist item", it.inspection),
                *([("Elements covered", "; ".join(pd.element_label(e) for e in it.elements))] if it.elements else []),
                ("Drawing reference", drawing)]),
            Prose("Observations:"),
        ]
        for k, o in enumerate(it.observations, start=1):
            body += [Prose(f"{n}.{k}  {o.text}"), Photos(o.photos, images),
                     Prose(f"Result: {o.result or missing('Pass or Fail')}")]
            if o.result == "Fail":
                body += _failure_trail(o, images)
        if not it.observations:
            body.append(Prose(missing("observations")))

    body += [SectionHeader("Actions Required", level=3),
             Lines([f"{k}. {action_text(pd, a)}" for k, a in enumerate(v.actions, start=1)] or ["None."]),
             Prose(f"Inspected by: {inspector}"),
             Signature(image=signature, date=long_date(issued_at.date()) if issued_at else ""),
             Prose(f"For and on behalf of: {firm}")]

    meta = DocMeta(title=f"{TITLE} {tag}", reference=p.project_id, site_address=p.site_address,
                   engineer=eng.name if eng else "",
                   header_text=f"{p.name} – {TITLE} {tag}" + ("" if issued_at else " – DRAFT, not issued"),
                   footer_left=sir_id(pd, number))
    return ReportDocument(meta=meta, body=body)


def _failure_trail(o, images) -> list:
    """A failed observation's record: what to correct, the notices sent, each
    correction attempt and the engineer's review of it."""
    out = [Prose(f"Correction required: {o.required_correction or missing('what the builder must correct')}")]
    out += [Prose(f"Builder notified by email ({n.sent_to}) on {long_date_time(n.sent_at)}.") for n in o.notices]
    for a, c in enumerate(o.corrections, start=1):
        out += [Prose(f"Correction {a}, submitted by {c.submitted_by} on {long_date_time(c.submitted_at)}: "
                      f"{c.notes or 'see photos'}"),
                Photos(c.photos, images)]
        r = c.review
        if r is None:
            out.append(Prose(missing("the engineer's review of this correction")))
        elif r.decision == "Approved":
            out.append(Prose(f"Approved by {r.reviewed_by} on {long_date_time(r.reviewed_at)}."
                             + (f" {r.comment}" if r.comment else "")))
        else:
            out.append(Prose(f"Rejected by {r.reviewed_by} on {long_date_time(r.reviewed_at)}: {r.comment}"))
    if not o.corrections:
        out.append(Prose(missing("the builder's correction (requested by email)")))
    return out


def render_sir_html(pd: ProjectData, number: int) -> str:
    """SIR <number> as one HTML page: the review preview. Photos and the logo load
    from their URLs; never carries the signature (the portal keeps the signed PDF)."""
    out = io.StringIO()
    render_html(build_document(pd, number, issued_at=pd.visit(number).issued_at), out, theme=web_theme())
    return preview_numbers_in_body_font(out.getvalue())
