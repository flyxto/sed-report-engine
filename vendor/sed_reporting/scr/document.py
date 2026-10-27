"""The Structural Calculations Report (the SCR), built from a resolved project.

Sections follow the firm's SCR template (its Design Features Report), plus the design-basis sections chosen
from the Cognito Design Features Report (docs/scr_cognito_sections.md):

    cover · document control · 1 project description · 2 general (scope,
    standards, alternative solutions) · 3 design basis (site information, dead,
    live and barrier loads, soil and foundations, durability) · 4 specific
    engineering design items (one section per element category) · 5 other
    considerations · Appendix A (calculations: table of contents and element
    reports, merged after this body)

Anything not yet entered prints as a visible "[not entered: …]" marker, so the
preview shows the gaps; issues() blocks the final PDF while errors remain.
"""

from __future__ import annotations

import io
from datetime import date

from reporting import Column, DataTable, DocMeta, InfoCard, ReportDocument, SectionHeader, render_html, render_pdf

from sed_reporting.components import Bullets, CoverLine, CoverPage, Prose, missing
from sed_reporting.fonts import pdf_theme, preview_numbers_in_body_font, web_theme
from sed_reporting.project_data import ProjectData, nz_today
from sed_reporting.project_data.dates import long_date
from sed_reporting.project_data.resolve import revision_letter

TITLE = "Structural Calculations Report"

# The platform the report is issued through: the same on every report. The
# engineering firm that signs off the design comes from the portal (issuer).
PORTAL = "sed.works"
PORTAL_OPERATOR = "SED Works Ltd"

# Which durability rows apply follows the elements' materials.
_DURABILITY_ROWS = {
    "Steel timber fixings": ("steel_fixings", [("Steel fixings exposure zone (NZS 3604 Table 4.1)", "exposure_zone")]),
    "Reinforced concrete": ("concrete", [("Concrete exposure classification (NZS 3101 Table 3.6)",
                                          "exposure_classification")]),
    "Reinforced masonry": ("concrete", [("Concrete exposure classification (NZS 3101 Table 3.6)",
                                         "exposure_classification")]),
    "Mild steel": ("steel", [("Steel macroclimate corrosion category (SNZ TS 3404)", "macroclimate_category"),
                        ("Steelwork construction category (SNZ TS 3404)", "construction_category")]),
}


def document_id(pd: ProjectData) -> str | None:
    """"<job number>-SCR-Rev <latest revision>", e.g. "P260703-SCR-Rev A"; None
    while the revision record is empty (an error that blocks the PDF)."""
    revisions = pd.project.reports.scr.revisions
    return f"{pd.project.project_id}-SCR-Rev {revision_letter(len(revisions) - 1)}" if revisions else None


def report_date(pd: ProjectData, today: date | None = None) -> date:
    """The latest revision's issue date; today's date in New Zealand while it is
    a draft (not issued yet), which is the date issuing it would stamp."""
    revisions = pd.project.reports.scr.revisions
    if revisions and revisions[-1].issued_on:
        return revisions[-1].issued_on
    return today or nz_today()



def _num(x: float) -> str:
    """At least one decimal place, no trailing zeros beyond it: 2 -> "2.0", 0.25 -> "0.25"."""
    s = f"{x:g}"
    return s if "." in s or "e" in s else s + ".0"


def _or_missing(value: str | None, label: str) -> str:
    return value if value else missing(label)


def person_label(person) -> str:
    """"Name, Position" (position only when the portal sends one); "" if absent."""
    if person is None:
        return ""
    return ", ".join(x for x in (person.name, person.position) if x)


# --- what the report cites: shared with the PS1's Schedule, so the two always agree ---

def _architect(pd: ProjectData) -> str:
    a = pd.project.architect
    return _or_missing((a.company_name or a.name) if a else "", "architect, from the portal")


def drawings_cited(pd: ProjectData) -> str:
    """The architect's drawings as last reviewed:
    "Example Architects Ltd (P260703-DRG-Rev A), dated 15 August 2026"."""
    ds = pd.drawing_set
    return f"{_architect(pd)} " + (f"({ds.reference}), dated {long_date(ds.reviewed_on)}" if ds
                                   else f"({missing('completed drawing review, from the portal')})")


def next_drawings_cited(pd: ProjectData) -> str:
    """The drawing set's next revision, before its review is completed:
    "Example Architects Ltd (P260703-DRG-Rev B)". No date: it has none yet. A
    draft cites it this way; nothing is issued until the review is completed."""
    letter = revision_letter(len(pd.project.drawing_reviews))
    return f"{_architect(pd)} ({pd.project.project_id}-DRG-Rev {letter})"


def geotechnical_report_cited(pd: ProjectData) -> str | None:
    """The uploaded geotechnical report: "Example Geotech Ltd (report ref G-0451
    Rev A, dated 20 July 2026)"; None when there is none."""
    g = pd.project.geotechnical_report
    if g is None:
        return None
    ref = " ".join(x for x in (g.reference, f"Rev {g.revision}" if g.revision else "") if x)
    details = ", ".join(x for x in (f"report ref {ref}" if ref else "",
                                    f"dated {long_date(g.issue_date)}" if g.issue_date else "") if x)
    return g.author_company + (f" ({details})" if details else "")


def calculations_cited(pd: ProjectData) -> str:
    """This report as the PS1 and an RFI response cite it: "Structural
    Calculations Report P260703-SCR-Rev B, dated 10 October 2026" (the latest
    revision). A draft revision has no date yet, so none is printed; nothing
    citing it can be issued until it is."""
    revisions = pd.project.reports.scr.revisions
    # Cite the latest issued revision even when a newer one is in draft.
    issued = [i for i, r in enumerate(revisions) if r.issued_on]
    if issued:
        i = issued[-1]
        return f"{TITLE} {pd.project.project_id}-SCR-Rev {revision_letter(i)}, dated {long_date(revisions[i].issued_on)}"
    doc = document_id(pd)
    if not doc:
        return f"{TITLE} {missing('a revision, which the document ID needs')}"
    return f"{TITLE} {doc}"


def basis_of_opinions(pd: ProjectData) -> list[str]:
    """What the report's opinions are based on, all from the portal: the
    architect's drawings as last reviewed, and the uploaded geotechnical report
    (left out when there is none)."""
    items = [f"Drawings supplied by {drawings_cited(pd)}."]
    if geo := geotechnical_report_cited(pd):
        items.append(f"Site-specific geotechnical assessment by {geo}.")
    items.append("Any other information used for our design that was given to us by a third party.")
    return items


def design_item_title(r) -> str:
    """A design item's section title (without its number):
    "Element 7 – Raft Foundations (Rafts): Raft foundation for the extension"."""
    return f"Element {r.element.id} – {r.type.name} ({r.type.code}): {r.element.description}"


EQSE_LOGO_URL = "https://res.cloudinary.com/vccpsacloud/image/upload/v1793127732/eqse-logo_j8pnxv.png"


def build_document(pd: ProjectData, today: date | None = None, logo: bytes | None = None) -> ReportDocument:
    p, scr = pd.project, pd.project.reports.scr
    cert = p.ps1_certificate_data
    firm = cert.issuer if cert else ""                                  # the engineering firm, not the portal
    short = (cert.issuer_short_name if cert else "") or firm            # "EQSE"; the full name until the portal sends it
    firm_intro = _or_missing(f"{firm} ({short})" if firm and short != firm else firm,
                             "engineering firm, from the portal")      # first mention in a section
    short = _or_missing(short, "engineering firm, from the portal")
    engineer = (p.internal_reviewing_engineer.name if p.internal_reviewing_engineer
                else cert.signed_by_name if cert else "")
    description = p.project_description or p.name
    day = report_date(pd, today)   # the latest revision's issue date, or today (NZ) for a draft
    printed = long_date(day)

    body: list = [
        CoverPage([
            CoverLine("Specific Engineering Design", 14, True),
            CoverLine(TITLE, 20, True, 24),
            CoverLine("for"), CoverLine(description, 13, True, 10),
            CoverLine("at"), CoverLine(p.site_address, 13, True, 10),
            CoverLine("on"), CoverLine(printed, 12, False, 24),
            CoverLine("Report Prepared For"), CoverLine(p.client.name, 13, True, 24),
            CoverLine(f"Project Reference – {p.project_id}"),
        ], logo_url=EQSE_LOGO_URL, logo=logo),
        SectionHeader("Document Control", level=2),
        InfoCard("Document", [
            ("Report", f"{TITLE} for {description}"), ("Project", p.name), ("Reference", p.project_id),
            ("Address", p.site_address), ("Client", p.client.name),
            ("Document ID", _or_missing(document_id(pd), "a revision, which the document ID needs")),
            ("Date", printed),
            # One engineer: with the calculations and reporting automated, the
            # project's reviewing engineer both prepares and reviews the report.
            ("Prepared and reviewed by",
             person_label(p.internal_reviewing_engineer) or missing("reviewing engineer, from the portal")),
        ]),
        DataTable([Column("Revision"), Column("Description"), Column("Date")],
                  [[revision_letter(i), r.description, long_date(r.issued_on or day)]
                   for i, r in enumerate(scr.revisions)]
                  or [[missing("revision"), "", ""]], autosize=True),

        SectionHeader("1. Project Description", level=2, page_break_before=True),
        Prose(f"{firm_intro} has been engaged by {p.client.name} to provide structural engineering "
              f"services for the following project at {p.site_address}: {description}."),

        SectionHeader("2. General", level=2),
        SectionHeader("2.1 Scope", level=3),
        Prose("In general terms, the scope of work is as follows:"),
        Bullets([f"{c} design" for c in pd.categories] + list(scr.scope_extra)),
        SectionHeader("2.2 Design Standards", level=3),
        Prose("The design standards used in the design of the building are:"),
        Bullets(pd.standards or [missing("design standards")]),
        SectionHeader("2.3 Alternative Solutions", level=3),
    ]
    if scr.alternative_solutions:
        body += [Prose("The following alternative solutions have been adopted in the design:"),
                 Bullets(list(scr.alternative_solutions))]
    else:
        body.append(Prose("No alternative solutions have been adopted in the design of the structure."))

    body += _design_basis(pd)

    body.append(SectionHeader("4. Specific Engineering Design Items", level=2, page_break_before=True))
    for n, r in enumerate(pd.design_items, start=1):     # one section per element
        body.append(SectionHeader(f"4.{n} {design_item_title(r)}", level=3))
        body.append(Prose(pd.narrative(r.element.id) or missing(f"design narrative for element {r.element.id}")))

    body += [
        SectionHeader("5. Other Considerations", level=2),
        Prose(f"This report has been prepared by {firm_intro} exclusively for {p.client.name} for the purpose of "
              f"applying for building consent with {_or_missing(p.territorial_authority, 'building consent authority')}. "
              "Information, opinions and recommendations contained in it cannot be used for any other purpose or "
              f"by any other entity without {short}'s review and written consent. "
              f"{short} accepts no liability or responsibility whatsoever for or in respect of "
              "any use or reliance upon this report by any third party."),
        Prose(f"This report is issued through the {PORTAL} portal, operated by {PORTAL_OPERATOR}. "
              f"{PORTAL_OPERATOR} provides the portal only. It does not carry out or certify the structural design, "
              f"which is the responsibility of {short}."),
        Prose("Opinions given in this report are based on:"),
        Bullets(basis_of_opinions(pd)),
        SectionHeader("Appendix A – Calculations", level=2, page_break_before=True),
        Prose("The calculation report for each element follows, listed in the table of contents on the next page."),
    ]

    meta = DocMeta(title=TITLE, reference=p.project_id, site_address=p.site_address, engineer=engineer,
                   date=printed, header_text=f"{p.name} – {TITLE}",
                   footer_left=document_id(pd) or p.project_id)
    return ReportDocument(meta=meta, body=body)


def _design_basis(pd: ProjectData) -> list:
    p, scr = pd.project, pd.project.reports.scr
    s = p.structural
    out: list = [
        SectionHeader("3. Design Basis", level=2, page_break_before=True),
        SectionHeader("3.1 Site Information", level=3),
        InfoCard("Site information", [
            ("Building importance level", scr.importance_level),
            ("Wind zone", _or_missing(s.wind_zone, "wind zone")),
            ("Snow zone", _or_missing(s.snow_zone, "snow zone")),
            ("Snow elevation", s.snow_elevation or "—"),
        ]),
        SectionHeader("3.2 Dead Loads", level=3),
        DataTable([Column("Assembly"), Column("Category"), Column("Total (kPa)", "right")],
                  [[d.name, d.category.title(), _num(d.total_kpa) if d.total_kpa is not None else missing("weight")]
                   for d in pd.dead_loads] or [[missing("assemblies"), "", ""]], autosize=True),
        SectionHeader("3.3 Live Loads", level=3),
        DataTable([Column("Area"), Column("Distributed (kPa)", "right"), Column("Point (kN)", "right")],
                  [[l.area, _num(l.distributed_kpa),
                    _num(l.point_kn) if l.point_kn is not None else "–".join(_num(v) for v in l.point_kn_range)]
                   for l in pd.live_loads], autosize=True),
    ]
    n = 4
    if pd.barrier_loads:
        b = pd.barrier_loads
        out += [SectionHeader(f"3.{n} Barrier Loads", level=3),
                DataTable([Column("Load"), Column("Value", "right")],
                          [["Line load", f"{_num(b.line_kn_per_m)} kN/m"],
                           ["Concentrated load", f"{_num(b.concentrated_kn)} kN"],
                           ["Infill load", f"{_num(b.infill_kpa)} kPa"]], autosize=True)]
        n += 1

    f = scr.foundations
    out.append(SectionHeader(f"3.{n} Soil and Foundations", level=3))
    if f:
        rows = [
            ("ULS bearing capacity", f"{s.uls_bearing} kPa" if s.uls_bearing else missing("ULS bearing capacity")),
            ("General ground conditions", f.ground_conditions),
            ("Expansive soils suspected", "Yes" if f.expansive_soils_suspected else "No"),
        ]
        if f.site_soils_class:         # only given when expansive soils are suspected
            rows.append(("Site soils class (AS 2870-2011)", f.site_soils_class))
        out.append(InfoCard("Soil and foundations", rows))
        if f.narrative:
            out.append(Prose(f.narrative))
    else:
        out.append(Prose(missing("foundations inputs (general ground conditions, expansive soils, site soils class)")))
    n += 1

    rows = []
    for material in [m.name for m in pd.materials_used]:
        if material not in _DURABILITY_ROWS:
            continue
        block_name, fields = _DURABILITY_ROWS[material]
        block = getattr(p.durability, block_name)
        for label, attr in fields:
            value = getattr(block, attr) if block else missing(label)
            if [label, value] not in rows:
                rows.append([label, value])
    out += [SectionHeader(f"3.{n} Durability", level=3),
            DataTable([Column("Item"), Column("Classification")], rows or [["—", "—"]], autosize=True)]
    return out


def render_scr_html(pd: ProjectData, today: date | None = None) -> str:
    """The report as one HTML page: the review preview."""
    out = io.StringIO()
    render_html(build_document(pd, today), out, theme=web_theme())
    return preview_numbers_in_body_font(out.getvalue())


def render_scr_body_pdf(pd: ProjectData, today: date | None = None, logo: bytes | None = None) -> bytes:
    """The report body as PDF, before the calculation appendix is merged in."""
    out = io.BytesIO()
    render_pdf(build_document(pd, today, logo), out, theme=pdf_theme())
    return out.getvalue()
