"""The PS1 package, built from a resolved project: the same nine pages as the
ACE New Zealand / Engineering New Zealand form (PS1 – Design, January 2024,
Rev 01), in our theme.

    1–2  Producer Statement PS1 – Design
    3    Schedule to PS1
    4    Guidance on use of producer statements
    5    Construction Monitoring Schedule
    6–7  Certificate of Design Work (memorandum from licensed building practitioner)
    8    Structural Maintenance Schedule
    9    B2 Letter in Lieu – Design

Wording is the form's, as in the sample in samples/ps1_reference/, with its
obvious slips fixed. Attachments not selected in reports.ps1.documents are left
out. Anything the portal doesn't send yet prints as a visible "[not entered: …]"
marker. Until issue, the signature lines show a placeholder; on issue they
carry the reviewing engineer's signature and the issue date (build.issue_ps1).
"""

from __future__ import annotations

import io
from datetime import datetime

from reporting import Column, DocMeta, InfoCard, ReportDocument, SectionHeader, render_html

from sed_reporting.components import Bullets, Lines, LogoHeader, PageBreak, Prose, Signature, SizedTable, Ticks, missing
from sed_reporting.fonts import preview_numbers_in_body_font, web_theme
from sed_reporting.project_data import ProjectData
from sed_reporting.project_data.dates import long_date, long_date_time, nz_now
from sed_reporting.scr.document import EQSE_LOGO_URL, calculations_cited, drawings_cited, geotechnical_report_cited

TITLE = "Producer Statement – PS1 Design"
FORM_VERSION = "PS1 - Design – January 2024 (Rev 01)"

DOCUMENT_LABELS = {      # the attachments that can be left out (reports.ps1.documents)
    "certificate_of_design_work": "Certificate of Design Work",
    "construction_monitoring_schedule": "Construction Monitoring Schedule",
    "b2_letter_in_lieu": "B2 Letter in Lieu - Design",
}
MAINTENANCE_LABEL = "Structural Maintenance Schedule"     # included when any of its items is ticked


def _or(value, label: str) -> str:
    return str(value) if value not in (None, "", []) else missing(label)


def build_document(pd: ProjectData, *, signature: bytes | None = None, issued_at: datetime | None = None,
                   now: datetime | None = None, logo: bytes | None = None) -> ReportDocument:
    """The PS1 package. `signature` and `issued_at` are given on issue only."""
    p, ps1 = pd.project, pd.project.reports.ps1
    eng, cert = p.internal_reviewing_engineer, p.ps1_certificate_data
    firm = _or(pd.firm_name, "engineering firm, from the portal")
    client = p.client.name
    engaged_by = ps1.engaged_by or client
    council = _or(pd.council.name if pd.council else p.territorial_authority, "council")
    address = p.site_address
    description = p.project_description or p.name
    name = _or(eng.name if eng else "", "reviewing engineer, from the portal")
    scope = ", ".join(pd.scope_labels) or missing("element categories")
    signed = Signature(image=signature, date=long_date(issued_at.date()) if issued_at else "")
    docs = ps1.documents
    clauses = ", ".join(ps1.code_clauses)

    body: list = []

    # --- 1–2. Producer Statement PS1 – Design ---------------------------------
    extent = ("part only, as specified in the attached Schedule, of the proposed building work."
              if ps1.extent == "part" else "all of the proposed building work.")
    compliance = [(True, "compliance documents issued by the Ministry of Business, Innovation & Employment "
                         f"(Verification method/acceptable solution): {pd.verification_methods}")]
    if pd.alternative_solution:
        compliance.append((True, "alternative solution as per the attached Schedule"))
    monitoring = (f"I recommend the {ps1.construction_monitoring_level} level of construction monitoring."
                  if ps1.construction_monitoring_level != "Nil" else "I recommend no construction monitoring (Nil).")
    pi = cert.issuer_pi_insurance_nzd if cert else None
    ace = cert.issuer_ace_nz_member if cert else None
    body += [
        LogoHeader(logo_url=EQSE_LOGO_URL, logo=logo),
        SectionHeader(TITLE, level=2),
        InfoCard("Producer statement", [
            ("Building Code Clause(s)", clauses), ("Job number", p.project_id),
            ("Document", _or(f"{pd.ps1_document_id} ({ps1.revisions[-1].description})" if ps1.revisions else "",
                             "a PS1 revision")),
            ("Issued by (engineering design firm)", firm), ("To (client)", client),
            ("To be supplied to (Building Consent Authority)", council),
            ("In respect of (description of building work)", description),
            ("At (address)", address), ("Legal description", _or(p.legal_description, "legal description")),
        ]),
        Prose(f"We have been engaged by {engaged_by} to provide:\n\n{scope}\n\n"
              "in respect of the requirements of the Clause(s) of the Building Code specified above for " + extent),
        Prose('In this document SED means "Specific Engineering Design".'),
        Prose(f"The design carried out by {firm} has been prepared in accordance with:"),
        Ticks(compliance),
        Prose("The proposed building work covered by this producer statement is described in the drawings specified "
              "in the attached Schedule, together with the specification, and other documents set out in the attached "
              "Schedule."),
        Prose(f"On behalf of {firm}, and subject to:"),
        Bullets(["all proprietary products meeting their performance specification requirements;"]),
        Prose("I believe on reasonable grounds that:"),
        Bullets(["the building, if constructed in accordance with the drawings, specifications, and other documents "
                 "provided or listed in the attached Schedule, will comply with the relevant provisions of the Building "
                 "Code specified above; and that",
                 "the persons who have undertaken the design have the necessary competence to do so."]),
        Prose(monitoring),
        Prose(f"I, {name}, am:"),
        Bullets([f"CPEng number {_or(eng.cpeng_number if eng else '', 'CPEng number, from the portal')}",
                 "and hold the following qualifications: "
                 + _or(", ".join(eng.qualifications) if eng else "", "qualifications, from the portal")]),
        Prose(f"{firm} holds a current policy of Professional Indemnity Insurance no less than "
              + (f"${pi:,}." if pi else missing("PI insurance, from the portal") + ".")),
        Prose(f"{firm} is a member of ACE New Zealand." if ace else f"{firm} is not a member of ACE New Zealand."
              if ace is False else f"{firm} " + missing("ACE NZ membership, from the portal") + "."),
        Prose(f"SIGNED BY: {name}"),
        signed,
        Prose(f"ON BEHALF OF: {firm}"),
        Prose(f"Note: This statement has been prepared solely for {council} and shall not be relied upon by any other "
              f"person or entity. Any liability in relation to this statement accrues to {firm} only. As a condition "
              f"of reliance on this statement, {council} accepts that the total maximum amount of liability of any kind "
              f"arising from this statement and all other statements provided to {council} in relation to this "
              f"building work, whether in tort or otherwise, is limited to the sum of ${ps1.liability_cap_nzd:,}."),
        Prose("This form is to accompany Form 2 of the Building (Forms) Regulations 2004 for the application of a "
              "Building Consent."),
        PageBreak(),
    ]

    # --- 3. Schedule ------------------------------------------------------------
    # The same drawings, calculations and geotechnical report the Structural Calculations Report cites.
    included = [label for key, label in DOCUMENT_LABELS.items() if getattr(docs, key)]
    if pd.has_maintenance_schedule:                     # the form's order: before the B2 letter
        included.insert(len(included) - (1 if docs.b2_letter_in_lieu else 0), MAINTENANCE_LABEL)
    items = [", ".join(included),
             f"Engineering Drawing Set: {drawings_cited(pd)}",
             f"Engineering Calculations: {calculations_cited(pd)}"]
    if geo := geotechnical_report_cited(pd):
        items.append(f"Geotechnical Report: {geo}")
    items += [f"Alternative solution: {a}" for a in p.reports.scr.alternative_solutions]
    items += [f"Design assumption: {a}" for a in ps1.design_assumptions]
    body += [
        SectionHeader("Schedule to PS1", level=2),
        Prose("Please include an itemised list of all referenced documents, drawings, or other supporting materials "
              "in relation to this producer statement below:"),
        Bullets([i for i in items if i]),
    ]
    if ps1.extent == "part":
        body += [SectionHeader("Limited Scope of Engagement", level=3),
                 Prose(f"We have been engaged by {engaged_by} to provide services in respect of the requirements of the "
                       "Clause(s) of the Building Code specified above for the following parts of the proposed "
                       f"building work:\n\n{scope}")]
    body.append(PageBreak())

    # --- 4. Guidance --------------------------------------------------------------
    body += [SectionHeader("Guidance on Use of Producer Statements", level=2), *guidance(firm), PageBreak()]

    # --- 5. Construction Monitoring Schedule ----------------------------------------
    if docs.construction_monitoring_schedule:
        rows = [[f"{n}.", i.item, i.timeframe, i.monitored_by] for n, i in enumerate(pd.inspections, start=1)]
        body += [
            SectionHeader("Construction Monitoring Schedule", level=2),
            InfoCard("Schedule of monitoring for", [("Address", address), ("Job number", p.project_id)]),
            Prose("We propose that at least the following site monitoring is undertaken to Engineering New "
                  f"Zealand/ACENZ {ps1.construction_monitoring_level}:"),
            SizedTable([Column("No."), Column("Item of monitoring"), Column("Timeframe"), Column("To be monitored by")],
                       rows or [["", missing("inspections, from the element library"), "", ""]],
                       widths=[0.07, 0.33, 0.37, 0.23]),
            Prose("Notes:"),
            Lines([
                "a) The above items of monitoring are the minimum required to enable the Engineer to issue a PS4 – "
                "Producer Statement Construction Review for the specific engineering design items.",
                "b) The above items of monitoring do not cover work constructed in accordance with NZS 3604:2011, for "
                "which monitoring is to be undertaken by the Building Consent Authority.",
                "c) The Contractor/Builder is to provide the Engineer at least 24 hours’ notice of the requirement for "
                "monitoring. The above timeframes are indicative, the Engineer and Contractor are to agree the timing of "
                "monitoring prior to work commencing on site.",
                "d) A copy of this monitoring schedule is to be held on site during the works, and the "
                "Contractor/Builder is to provide reasonable and safe access to enable works to be monitored according "
                "to the schedule.",
                "e) The above schedule does not necessarily represent the actual number of monitorings to be "
                "undertaken. The number of monitorings will depend on the construction method, sequence of the works "
                "and whether or not unforeseen conditions or difficulties are encountered on site.",
            ]),
            PageBreak(),
        ]

    # --- 6–7. Certificate of Design Work -------------------------------------------------
    if docs.certificate_of_design_work:
        rbw = [[l.row, "Yes" if l.applies else "No",
                (l.description or missing("description")) if l.applies else "Not applicable",
                (l.carried_out_or_supervised or missing("carried out or supervised")) if l.applies else "Not applicable"]
               for l in pd.rbw_lines]
        waivers = ps1.waivers
        body += [
            SectionHeader("Certificate of Design Work: Memorandum from Licensed Building Practitioner", level=2),
            SectionHeader("Section 30C and Section 45, Building Act 2004", level=3),
            InfoCard("The building", [
                ("Street address", _or(p.site_street_address, "street address, from the portal")),
                ("Suburb", p.site_suburb), ("Town/City", _or(p.site_town_city, "town/city, from the portal")),
                ("Postcode", p.site_postcode)]),
            InfoCard("The owner", [("Name(s)", client), ("Email", p.client.email), ("Phone", p.client.phone),
                                   ("Address", p.client.address)]),
            SectionHeader("Basis for providing this memorandum", level=3),
            Prose("I am providing this memorandum in my role as the specialist designer who carried out or supervised "
                  "specific Primary structure elements of restricted building work (RBW) design work as described in "
                  "this memorandum. Other designers will provide memoranda covering the remaining RBW design work. "
                  "Refer also to the attached PS1."),
            SectionHeader("Identification of restricted building work (RBW) design work", level=3),
            Prose(f"I, {name} carried out or supervised the following RBW design work:"),
            SectionHeader("Primary structure: B1", level=3),
            SizedTable([Column("Design work that is RBW"), Column("RBW"),
                        Column("Description (as required) and reference to plans and specifications"),
                        Column("Carried out or supervised")], rbw, widths=[0.2, 0.08, 0.5, 0.22]),
            Prose("Note: SED = Elements subject to Specific Engineering Design outside of the scope of NZS3604:2011, "
                  "unless otherwise noted."),
            SectionHeader("Waivers and modifications", level=3),
            InfoCard("Waivers and modifications", [
                ("Are waivers or modifications of the Building Code required?", "Yes" if waivers.required else "No"),
                ("If yes, please provide details of the waivers or modifications", waivers.details or "")]),
            SectionHeader("Issued by", level=3),
            InfoCard("Issued by", [
                ("Name", name), ("Design entity/company", firm),
                ("Chartered status", _or(eng.chartered_status if eng else "", "chartered status, from the portal")),
                ("Chartered no.", _or(eng.cpeng_number if eng else "", "CPEng number, from the portal")),
                ("Email", _or(eng.handle if eng else "", "email, from the portal")),
                ("Website", _or(cert.issuer_website if cert else "", "website, from the portal")),
                # As the Cognito form has it: the daytime and after-hours numbers are the firm's, the mobile the engineer's.
                ("Phone (daytime)", _or(cert.issuer_phone if cert else "", "firm's phone, from the portal")),
                ("Phone (after hours)", cert.issuer_phone_after_hours if cert else ""),
                ("Mobile", eng.mobile if eng else ""),
                ("Postal address", _or(cert.issuer_postal_address if cert else "", "postal address, from the portal")),
                ("Physical address", _or(cert.issuer_address if cert else "", "physical address, from the portal")),
            ]),
            SectionHeader("Declaration", level=3),
            Prose(f"I, {name}, LBP state that I have applied the skills and care reasonably required of a competent "
                  "design professional in carrying out or supervising the RBW described in this memorandum and that "
                  "based on this, I certify that the RBW described in this memorandum:"),
            Ticks([(not waivers.required, "complies with the Building Code"),
                   (waivers.required, "complies with the Building Code subject to any waiver or modification of the "
                                      "Building Code described in this memorandum.")]),
            signed,
            PageBreak(),
        ]

    # --- 8. Structural Maintenance Schedule ------------------------------------------------
    if pd.has_maintenance_schedule:
        rows = []
        for n, (label, items) in enumerate(pd.maintenance.items()):
            tag = f"({'abcdef'[n]}) {label}"
            rows += [[tag if i == 0 else "", item] for i, item in enumerate(items)] or [[tag, "Not applicable."]]
        body += [
            SectionHeader("Structural Maintenance Schedule", level=2),
            SectionHeader(f"{description} at {address}".upper(), level=3),
            Prose("This schedule of ongoing inspection and maintenance of structural elements shall be included with "
                  "the Operations and Maintenance manuals and provided to the Owner/Body Corporate and building managers."),
            SizedTable([Column("Inspection/maintenance timeframe"), Column("Item")], rows, widths=[0.3, 0.7]),
            PageBreak(),
        ]

    # --- 9. B2 Letter in Lieu ------------------------------------------------------------------
    if docs.b2_letter_in_lieu:
        body += [
            SectionHeader("Letter in Lieu – Design", level=2),
            Prose("To the Building Official,"),
            Lines(pd.b2_addressee or [council]),
            Prose(f"{description} at {address}"),
            SectionHeader("Compliance with Building Code Clause B2 – Durability", level=3),
            Prose("The purpose of this letter is to demonstrate how compliance with Clause B2 (Durability) of the "
                  "Building Code will be achieved for the above project. We can confirm that for specifically designed "
                  "structural elements that are included within our design documentation:"),
            SizedTable([Column("Material"), Column("Means of Compliance"), Column("Details")],
                       [[b.material, b.means_of_compliance, b.details or missing("B2 text, from the element library")]
                        for b in pd.b2_rows], widths=[0.22, 0.2, 0.58]),
            Prose("Yours faithfully,"),
            signed,
            Lines([name, "For and on behalf of", firm]),
        ]

    compiled = long_date_time(issued_at or now or nz_now())
    meta = DocMeta(title=TITLE, reference=p.project_id, site_address=address, engineer=name if eng else "",
                   header_text=f"{p.name} – PS1 Design" + (f" {pd.ps1_document_id}" if pd.ps1_document_id else "")
                               + ("" if issued_at else " – DRAFT, not issued"),
                   footer_left=FORM_VERSION,
                   footer_note=f"Job number: {p.project_id} · Job address: {address} · "
                               f"Compilation date and time: {compiled}")
    return ReportDocument(meta=meta, body=body)


def guidance(firm: str, nzs3910_mark: str = "¹") -> list:
    """Page 4: the form's guidance, as written by ACE New Zealand and Engineering
    New Zealand. The PS4's is the same text except where its sample differs:
    the last paragraph names "the Engineering Design Firm" (`firm`), and NZS
    3910 has no footnote mark (`nzs3910_mark=""`)."""
    return [
        Prose("Information on the use of Producer Statements and Construction Monitoring Guidelines can be found on "
              "either the ACE New Zealand or Engineering New Zealand websites."),
        Prose("Producer statements were first introduced with the Building Act 1991. The producer statements were "
              "developed by a combined task committee consisting of members of the New Zealand Institute of Architects "
              "(NZIA), Institution of Professional Engineers New Zealand (now Engineering New Zealand), Association of "
              "Consulting and Engineering New Zealand (ACE NZ) in consultation with the Building Officials Institute of "
              "New Zealand (BOINZ). The original suite of producer statements has been revised at the date of this form "
              "to ensure standard use within the industry."),
        Prose("The producer statement system is intended to provide Building Consent Authorities (BCAs) with part of "
              "the reasonable grounds necessary for the issue of a Building Consent or a Code Compliance Certificate, "
              "without necessarily having to duplicate review of design or construction monitoring undertaken by others."),
        Prose("PS1 DESIGN: Intended for use by a suitably qualified independent engineering design professional in "
              "circumstances where the BCA accepts a producer statement for establishing reasonable grounds to issue a "
              "Building Consent;"),
        Prose("PS2 DESIGN REVIEW: Intended for use by a suitably qualified independent engineering design review "
              "professional where the BCA accepts an independent design professional’s review as the basis for "
              "establishing reasonable grounds to issue a Building Consent;"),
        Prose("PS3 CONSTRUCTION: Forms commonly used as a certificate of completion of building work are Schedule 6 of "
              f"NZS 3910:2013{nzs3910_mark} or Schedules E1/E2 of NZIA’s SCC 2011²"),
        Prose("PS4 CONSTRUCTION REVIEW: Intended for use by a suitably qualified independent engineering construction "
              "monitoring professional who either undertakes or supervises construction monitoring of the building "
              "works where the BCA requests a producer statement prior to issuing a Code Compliance Certificate."),
        Prose("This must be accompanied by a statement of completion of building work (Schedule 6)."),
        Prose("The following guidelines are provided by ACE New Zealand and Engineering New Zealand to interpret the "
              "Producer Statement."),
        SectionHeader("Competence of Engineering Professional", level=3),
        Prose("This statement is made by an engineering firm that has undertaken a contract of services for the "
              "services named, and is signed by a person authorised by that firm to verify the processes within the firm "
              "and competence of its personnel."),
        Prose("The person signing the Producer Statement on behalf of the engineering firm will have a professional "
              "qualification and proven current competence through registration on a national competence-based register "
              "such as a Chartered Professional Engineer (CPEng)."),
        Prose("Membership of a professional body, such as Engineering New Zealand provides additional assurance of the "
              "designer’s standing within the profession. If the engineering firm is a member of ACE New Zealand, this "
              "provides additional assurance about the standing of the firm."),
        Prose("Persons or firms meeting these criteria satisfy the term “suitably qualified independent engineering "
              "professional”."),
        SectionHeader("Professional Indemnity Insurance", level=3),
        Prose("As part of membership requirements, ACE New Zealand requires all member firms to hold Professional "
              "Indemnity Insurance to a minimum level."),
        Prose("The PI Insurance minimum stated on the front of this form reflects standard practice for the "
              "relationship between the BCA and the engineering firm."),
        SectionHeader("Professional Services during Construction Phase", level=3),
        Prose("There are several levels of service that an engineering firm may provide during the construction phase "
              "of a project (CM1-CM5 for engineers³). The BCA is encouraged to require that the service to be provided by "
              "the engineering firm is appropriate for the project concerned."),
        SectionHeader("Requirement to provide Producer Statement PS4", level=3),
        Prose("BCAs should ensure that the applicant is aware of any requirement for producer statements for the "
              "construction phase of building work at the time the building consent is issued. No design professional "
              "should be expected to provide a producer statement unless such a requirement forms part of "
              f"{firm}’s engagement."),
        Prose("Refer Also:"),
        Lines(["1 Conditions of Contract for Building & Civil Engineering Construction NZS 3910: 2013",
               "2 NZIA Standard Conditions of Contract SCC 2011",
               "3 Guideline on the Briefing & Engagement for Consulting Engineering Services (ACE New Zealand/Engineering "
               "New Zealand 2004)",
               "4 PN01 Guidelines on Producer Statements"]),
        Lines(["www.acenz.org.nz", "www.engineeringnz.org"]),
    ]


def render_ps1_html(pd: ProjectData) -> str:
    """The PS1 package as one HTML page: the review preview. Never carries the
    signature image; once issued it shows the issue date (the portal keeps the
    signed PDF)."""
    out = io.StringIO()
    render_html(build_document(pd, issued_at=pd.ps1_issued_at), out, theme=web_theme())
    return preview_numbers_in_body_font(out.getvalue())
