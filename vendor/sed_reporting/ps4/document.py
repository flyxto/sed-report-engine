"""The PS4, built from a resolved project: the same four pages as the ACE New
Zealand / Engineering New Zealand form (PS4 – Construction Review, January 2024,
Rev 01), in our theme, as the PS1 is.

    1–2  Producer Statement PS4 – Construction Review
    3    Schedule to PS4: the documents attached (the issued SIRs, the PS3s,
         the builder's Record of Work) and the limited scope of engagement
    4    Guidance on use of producer statements

Wording is the form's, as in the sample in samples/ps4_reference/. Most of the
data is shared with the PS1 (clauses, engagement, CM level, liability cap) or
comes from the portal. The documents listed in the Schedule are attached after
these pages (build.py). Until issue, the signature line shows a placeholder; on
issue it carries the reviewing engineer's signature and the issue date.
"""

from __future__ import annotations

import io
from datetime import datetime

from reporting import DocMeta, InfoCard, ReportDocument, SectionHeader, render_html

from sed_reporting.components import Bullets, PageBreak, Prose, Signature, missing
from sed_reporting.fonts import preview_numbers_in_body_font, web_theme
from sed_reporting.project_data import ProjectData
from sed_reporting.project_data.dates import long_date, long_date_time, nz_now
from sed_reporting.ps1.document import _or, guidance

TITLE = "Producer Statement – PS4 Construction Review"
FORM_VERSION = "PS4 - Construction Review – January 2024 (Rev 01)"


def scope_of_monitoring(pd: ProjectData) -> str:
    """"Construction monitoring of the SED foundations, beams and portal frames":
    the PS1's scope, the element categories present."""
    cats = [c.lower() for c in pd.categories]
    if not cats:
        return missing("element categories")
    listed = cats[0] if len(cats) == 1 else ", ".join(cats[:-1]) + " and " + cats[-1]
    return f"Construction monitoring of the SED {listed}"


def attachments(pd: ProjectData) -> list[tuple[str, str]]:
    """What the PS4 attaches, in order, as (label, url): each issued SIR, the
    PS3s, the builder's Record of Work. The Schedule lists the labels."""
    p, ps4 = pd.project, pd.project.reports.ps4
    out = [(f"Site Inspection Report {pd.sir_id(v.number)}, "
            f"{long_date(v.inspection_date) or long_date(v.issued_at.date())}", v.pdf_url) for v in pd.issued_sirs]
    out += [("PS3 – Construction: " + d.issued_by + (f", dated {long_date(d.issued_on)}" if d.issued_on else ""), d.file_url)
            for d in ps4.ps3s]
    if r := ps4.record_of_work:
        by = r.issued_by or (p.builder.name if p.builder else "")
        out.append(("Record of Work" + (f": {by}" if by else "") + (f", dated {long_date(r.issued_on)}" if r.issued_on else ""),
                    r.file_url))
    return out


def build_document(pd: ProjectData, *, signature: bytes | None = None, issued_at: datetime | None = None,
                   now: datetime | None = None) -> ReportDocument:
    """The PS4's own pages. `signature` and `issued_at` are given on issue only."""
    p, ps1, ps4 = pd.project, pd.project.reports.ps1, pd.project.reports.ps4
    eng, cert = p.internal_reviewing_engineer, p.ps1_certificate_data
    firm = _or(pd.firm_name, "engineering firm, from the portal")
    client = p.client.name
    engaged_by = ps1.engaged_by or client
    council = _or(pd.council.name if pd.council else p.territorial_authority, "council")
    address = p.site_address
    description = p.project_description or p.name
    name = _or(eng.name if eng else "", "reviewing engineer, from the portal")
    clauses = ", ".join(ps1.code_clauses)
    consent = _or(p.building_consent_number, "consent number, from the portal")
    amendments = ", ".join(p.building_consent_amendments) or "N/A"
    pi = cert.issuer_pi_insurance_nzd if cert else None
    ace = cert.issuer_ace_nz_member if cert else None
    doc_id = pd.ps4_document_id

    body: list = [
        # --- 1–2. Producer Statement PS4 – Construction Review ---------------------------
        SectionHeader(TITLE, level=2),
        InfoCard("Producer statement", [
            ("Building Code Clause(s)", clauses), ("Job number", p.project_id),
            ("Document", _or(f"{doc_id} ({ps4.revisions[-1].description})" if ps4.revisions else "", "a PS4 revision")),
            ("Issued by (construction monitoring firm)", firm), ("To (client)", client),
            ("To be supplied to (Building Consent Authority)", council),
            ("In respect of (description of building work)", description),
            ("At (address)", address), ("Legal description", _or(p.legal_description, "legal description")),
        ]),
        Prose(f"We have been engaged by {engaged_by} to provide {ps1.construction_monitoring_level} level of "
              "construction monitoring relating to the Clause(s) named above of the Building Code for the building work "
              "which is covered by PS1(s)"),
        Bullets([f"issued by {firm} and",
                 f"which is described in the documents relating to the Building Consent No. {consent} and",
                 f"those relating to Building Consent Amendment(s) No. {amendments}"]),
        Prose("issued during the course of the works."),
        Prose("We have sighted these Building Consents and the conditions attached to them."),
        Prose("Authorised instructions/variation(s) detailed/listed in the attached Schedule have been issued during "
              "the course of the works."),
        Prose(f"On the basis of these review(s) and information supplied by the contractor during the course of the "
              f"works and on behalf of {firm}, I believe on reasonable grounds that the building works covered by the "
              "above mentioned PS1(s) have been completed in accordance with the relevant requirements of the Building "
              "Consent and Building Consent Amendments identified above or in the attached Schedule, with respect to "
              f"Clause(s) {clauses} of the Building Code. I also believe on reasonable grounds that the persons who "
              "have undertaken this construction review have the necessary competence to do so."),
        Prose(f"I, {name} am:"),
        Bullets([f"CPEng number {_or(eng.cpeng_number if eng else '', 'CPEng number, from the portal')}",
                 "and hold the following qualifications: "
                 + _or(", ".join(eng.qualifications) if eng else "", "qualifications, from the portal")]),
        Prose(f"{firm} holds a current policy of Professional Indemnity Insurance no less than "
              + (f"${pi:,}." if pi else missing("PI insurance, from the portal") + ".")),
        Prose(f"{firm} is a member of ACE New Zealand." if ace else f"{firm} is not a member of ACE New Zealand."
              if ace is False else f"{firm} " + missing("ACE NZ membership, from the portal") + "."),
        Prose(f"SIGNED BY: {name}"),
        Signature(image=signature, date=long_date(issued_at.date()) if issued_at else ""),
        Prose(f"ON BEHALF OF: {firm}"),
        Prose(f"Note: This statement has been prepared solely for {council} above and shall not be relied upon by any "
              f"other person or entity. Any liability in relation to this statement accrues to {firm} only. As a "
              f"condition of reliance on this statement, {council} accepts that the total maximum amount of liability "
              f"of any kind arising from this statement and all other statements provided to {council} in relation to "
              f"this building work, whether in tort or otherwise, is limited to the sum of ${ps1.liability_cap_nzd:,}."),
        Prose("This form is to accompany Forms 6 or 8 of the Building (Forms) Regulations 2004 for the issue of a Code "
              "Compliance Certificate"),
        PageBreak(),

        # --- 3. Schedule -----------------------------------------------------------------------
        SectionHeader("Schedule to PS4", level=2),
        Prose("Please include an itemised list of all referenced documents, drawings, or other supporting materials in "
              "relation to this producer statement below:"),
        Bullets([f"{label} (attached)" for label, _url in attachments(pd)] or [missing("issued SIRs")]),
        SectionHeader("Limited Scope of Engagement", level=3),
        Prose("The engagement is in respect of the following parts of the building work:"),
        Prose(scope_of_monitoring(pd)),
        PageBreak(),

        # --- 4. Guidance -------------------------------------------------------------------------
        SectionHeader("Guidance on Use of Producer Statements", level=2),
        *guidance("the Engineering Design Firm", nzs3910_mark=""),
    ]

    compiled = long_date_time(issued_at or now or nz_now())
    meta = DocMeta(title=TITLE, reference=p.project_id, site_address=address, engineer=name if eng else "",
                   header_text=f"{p.name} – PS4 Construction Review" + (f" {doc_id}" if doc_id else "")
                               + ("" if issued_at else " – DRAFT, not issued"),
                   footer_left=FORM_VERSION,
                   footer_note=f"Job number: {p.project_id} · Job address: {address} · "
                               f"Compilation date and time: {compiled}")
    return ReportDocument(meta=meta, body=body)


def render_ps4_html(pd: ProjectData) -> str:
    """The PS4's own pages as one HTML page: the review preview (the attached
    documents are listed in its Schedule, not shown). Never carries the
    signature image; once issued it shows the issue date."""
    out = io.StringIO()
    render_html(build_document(pd, issued_at=pd.ps4_issued_at), out, theme=web_theme())
    return preview_numbers_in_body_font(out.getvalue())
