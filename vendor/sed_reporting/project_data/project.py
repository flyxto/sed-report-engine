"""A project file: the portal's project JSON, plus three blocks of our own.

    portal fields   as the portal sends them (camelCase). Only the fields the
                    reports use are modelled; any others are ignored, so the
                    portal can add fields without breaking anything here.
    elements        the project's element instances (type code, material, …)
    durability      corrosion/durability choices, printed by the SCR; project
                    level in case a later report needs them
    reports         one block per report (ps1, scr, sir, rfi, ps4): the engineer's
                    inputs that the portal does not hold

Our own blocks are strict: an unknown key is rejected, so a misspelt input can't
silently drop a value from a signed document.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from sed_reporting.project_data._base import Portal, Strict
from sed_reporting.project_data.dates import nz_date

Text = Annotated[str, Field(min_length=1)]


# --- portal fields --------------------------------------------------------

class Client(Portal):
    id: str
    name: Text
    email: str = ""
    phone: str = ""
    company_name: str | None = None
    address: str = ""


class Inspection(Strict):
    """An inspection on the project's checklist: a row of the PS1's Construction
    Monitoring Schedule, and what a SIR inspects. Defined per element type in the
    library, or added on the project (reports.sir.additionalInspections)."""

    item: Text                         # e.g. "Reinforcement pre pour inspection by project Structural Engineer"
    timeframe: str = ""                # the library's all have one; one added on the project may not
    monitored_by: Text = "Structural Engineer"
    on_site: bool = True               # False: an office check (e.g. Shop Drawing Check), marked complete, not inspected in a SIR
    observations: list[Text] = []      # standard observations a SIR starts from, edited on site


class ReviewingEngineer(Portal):
    """The project's engineer. With the calculations and reports automated, the
    same engineer prepares and reviews the Structural Calculations Report, and
    signs the PS1. Everything below `handle` is requested from the portal
    (docs/portal_data_requests.md); not sent yet."""

    name: Text
    handle: str = ""                   # the engineer's email address
    position: str = ""                 # e.g. "Senior Structural Engineer"
    chartered_status: str = ""         # e.g. "Chartered Professional Engineer"
    cpeng_number: str = ""             # e.g. "1016856"
    qualifications: list[str] = []     # e.g. ["BSc Eng"]
    mobile: str = ""                   # the engineer's own; the daytime and after-hours numbers are the firm's
    signature_url: str = ""            # the engineer's signature image (https, PNG or JPEG), placed on issue


class Ps1CertificateData(Portal):
    """The engineering firm that signs off the design (not the portal company),
    and its signatory."""

    issuer: Text                       # the firm's full name, e.g. "Earthquake & Structural Engineering Consultants Limited"
    issuer_short_name: str = ""        # e.g. "EQSE"; requested (docs/portal_data_requests.md), not sent yet
    issuer_phone: str = ""             # the firm's daytime phone (the Cognito form's "Design Company Phone Number")
    issuer_email: str = ""
    issuer_address: str = ""           # the firm's physical address
    # Requested for the PS1 (docs/portal_data_requests.md); not sent yet:
    issuer_postal_address: str = ""
    issuer_phone_after_hours: str = ""
    issuer_website: str = ""
    issuer_pi_insurance_nzd: int | None = Field(default=None, gt=0)   # professional indemnity cover
    issuer_ace_nz_member: bool | None = None
    issuer_logo_url: str = ""          # the firm's logo (https, PNG or JPEG), for the SIR's letterhead
    issued_at: datetime | None = None
    # Not used by the reports: the reviewing engineer signs (internalReviewingEngineer).
    signed_by_name: str = ""
    signed_by_title: str = ""
    licence_number: str = ""   # e.g. "CPEng 12345"


class Structural(Portal):
    uls_bearing: str | None = None     # kPa (confirmed 2026-10-10); sent as text, e.g. "150.00"
    wind_zone: str | None = None
    snow_zone: str | None = None
    snow_elevation: str | None = None


class Assembly(Portal):
    id: str
    category: Text                     # "WALL", "ROOF", "FLOOR"
    code: str = ""
    name: Text
    calculated_total_weight: float | None = None   # kPa (confirmed 2026-10-10)


class Builder(Portal):
    """The builder on the project, as the portal sends it."""

    id: str = ""
    name: str = ""                     # e.g. "Smith Building Co."; the PS4 names it on the Record of Work


class Architect(Portal):
    """The architect: sed.works is the architects' portal. Requested as `architect`
    (docs/portal_data_requests.md); not sent yet."""

    company_name: str = ""             # printed when given
    name: str = ""                     # else the architect's own name


class DrawingReview(Portal):
    """A completed review of the project's drawing set (there is one set per
    project, not drawings per element). Each review is a revision of the set, "<job number>-DRG-Rev A", B, …; requested as
    `drawingReviews` (docs/portal_data_requests.md); not sent yet."""

    completed_at: AwareDatetime        # when the review was completed (UTC); the NZ date is printed


class GeotechnicalReport(Portal):
    """The site's geotechnical report, as captured when it is uploaded to the
    portal. Requested as `geotechnicalReport` (docs/portal_data_requests.md);
    not sent yet."""

    author_company: Text
    reference: str = ""                # the report's own reference, e.g. "G-0451"
    revision: str = ""                 # the report's own revision, e.g. "B"
    issue_date: date | None = None
    file_url: str = ""


# --- our own blocks -------------------------------------------------------

class Element(Strict):
    id: int
    type: Text                         # an element type code from the library
    description: Text
    calculation_report_url: str | None = None


class SteelFixings(Strict):
    exposure_zone: Literal["Zone B and C", "Zone D"]


class ConcreteDurability(Strict):
    exposure_classification: Literal["A1", "A2", "B1", "B2", "C (30% FA)"]


class SteelDurability(Strict):
    macroclimate_category: Literal["C1", "C2", "C3", "C4", "C5-M"]
    construction_category: Literal["CC1", "CC2", "CC3", "CC4"]


class Durability(Strict):
    steel_fixings: SteelFixings | None = None
    concrete: ConcreteDurability | None = None
    steel: SteelDurability | None = None


class Waivers(Strict):
    required: bool
    details: str | None = None

    @model_validator(mode="after")
    def _details_match(self) -> Waivers:
        if self.required and not self.details:
            raise ValueError("waivers.required is true, so waivers.details must describe them")
        if not self.required and self.details:
            raise ValueError("waivers.details is given but waivers.required is false")
        return self


class Ps1Documents(Strict):
    """The attachments to include. The Structural Maintenance Schedule is not a
    choice: it is included when any of its items is ticked."""

    certificate_of_design_work: bool = True
    construction_monitoring_schedule: bool = True
    b2_letter_in_lieu: bool = True


# The Structural Maintenance Schedule's intervals: field name -> label (as in the PS1 form).
MAINTENANCE_INTERVALS = {
    "half_yearly": "Half-yearly",
    "five_yearly": "5 yearly",
    "ten_yearly": "10 yearly",
    "twenty_five_yearly": "25 yearly",
    "after_fit_out_or_alterations": "Following fit-out or alterations",
    "after_seismic_shaking_sls1": "Following seismic shaking > SLS1 event",
}


class MaintenanceItems(Strict):
    """Items per interval, as the element library gives them for a material."""

    half_yearly: list[Text] = []
    five_yearly: list[Text] = []
    ten_yearly: list[Text] = []
    twenty_five_yearly: list[Text] = []
    after_fit_out_or_alterations: list[Text] = []
    after_seismic_shaking_sls1: list[Text] = []


class MaintenanceSchedule(Strict):
    """The engineer's edits per interval. None = the element library's items for
    the materials used; an empty list = none ("Not applicable.")."""

    half_yearly: list[Text] | None = None
    five_yearly: list[Text] | None = None
    ten_yearly: list[Text] | None = None
    twenty_five_yearly: list[Text] | None = None
    after_fit_out_or_alterations: list[Text] | None = None
    after_seismic_shaking_sls1: list[Text] | None = None


# The Certificate of Design Work's rows of restricted building work (fixed by the form).
RbwRow = Literal["Foundations", "Subfloor framing", "Retaining walls", "Beams", "Portal", "Bracing", "Other (primary)"]


class RbwRowInput(Strict):
    """The engineer's entries for one row of the Certificate of Design Work."""

    description: Text | None = None    # None = the element library's text for the row
    carried_out_or_supervised: Literal["Carried out", "Supervised"] | None = None   # None = the firm default


CodeClause = Literal["B1", "B2", "C1", "C2", "C3", "C4", "C5", "C6", "D1", "D2", "F6", "F7", "F8", "G4", "G9"]


class Ps1Revision(Strict):
    """One issue of the PS1 (Rev A, B, …). Only the description is typed: the
    letter follows its position, and the moment of issue and the documents it
    cited are stamped on issue. When the SCR or the drawing set moves past what
    the latest issued revision cites, the PS1 needs a new revision."""

    description: Text                  # e.g. "Building Consent", "Response to council RFI"
    issued_at: AwareDatetime | None = None   # stamped on issue (X-Issued-At); None = the draft
    cites_calculations: str = ""       # stamped on issue (X-Cites-Calculations): the SCR it cited, e.g. "P260703-SCR-Rev A"
    cites_drawings: str = ""           # stamped on issue (X-Cites-Drawings): the drawing set it cited, e.g. "P260703-DRG-Rev A"


class Ps1Inputs(Strict):
    """The engineer's inputs for the PS1 package. Not inputs: whether alternative
    solutions were adopted (the Structural Calculations Report's list), the firm
    and engineer details (the portal's issuer and reviewing engineer), and the
    issue dates (stamped on issue)."""

    code_clauses: list[CodeClause] = Field(default=["B1"], min_length=1)
    extent: Literal["all", "part"] = "part"
    engaged_by: str | None = None      # None = the client
    verification_methods: Text | None = None   # None = the firm default (design_defaults.json)
    design_assumptions: list[Text] = []
    construction_monitoring_level: Literal["CM1", "CM2", "CM3", "CM4", "CM5", "Nil"] = "CM3"
    waivers: Waivers = Waivers(required=False)
    liability_cap_nzd: Literal[200000, 500000] = 200000
    documents: Ps1Documents = Ps1Documents()
    rbw: dict[RbwRow, RbwRowInput] = {}                # Certificate of Design Work, per row
    maintenance_schedule: MaintenanceSchedule = MaintenanceSchedule()
    revisions: list[Ps1Revision] = []  # oldest first; the last is the current one. Once it is issued the PS1 is
                                       # locked until a new revision is added.

    @model_validator(mode="after")
    def _revision_record(self) -> Ps1Inputs:
        if any(r.issued_at is None for r in self.revisions[:-1]):
            raise ValueError("only the latest PS1 revision can be unissued; every earlier one needs issuedAt")
        for r in self.revisions:
            if r.issued_at and not (r.cites_calculations and r.cites_drawings):
                raise ValueError(f"PS1 revision {r.description!r} is issued, so it needs citesCalculations and "
                                 "citesDrawings (stamped on issue)")
        issued = [r.issued_at for r in self.revisions if r.issued_at]
        if issued != sorted(issued):
            raise ValueError("the PS1 revisions' issue times (issuedAt) must not go backwards")
        return self


class Revision(Strict):
    """One entry in the revision record. Only the description is entered: the
    letter follows the entry's position (A, B, …) and the date, and the drawing
    set it cited, are stamped when the revision is issued. When the drawing set
    moves past what the latest issued revision cites, the SCR needs a new
    revision."""

    description: Text                  # e.g. "Building Consent"
    issued_on: date | None = None      # set on issue, never typed; None = not issued yet (a draft)
    cites_drawings: str | None = None  # stamped on issue (X-Cites-Drawings): the drawing set it cited, e.g.
                                       # "P260703-DRG-Rev A"; "" if no review was completed then


class LiveLoad(Strict):
    area: Text                         # e.g. "Floors"
    distributed_kpa: float = Field(gt=0)
    point_kn: float | None = Field(default=None, gt=0)
    point_kn_range: tuple[float, float] | None = None    # printed as a range, e.g. roofs 1.1–1.4 kN

    @model_validator(mode="after")
    def _one_point_load(self) -> LiveLoad:
        if (self.point_kn is None) == (self.point_kn_range is None):
            raise ValueError(f"live load {self.area!r}: give exactly one of pointKn or pointKnRange")
        if self.point_kn_range and not 0 < self.point_kn_range[0] < self.point_kn_range[1]:
            raise ValueError(f"live load {self.area!r}: pointKnRange must be two increasing positive values")
        return self


class BarrierLoads(Strict):
    line_kn_per_m: float = Field(gt=0)
    concentrated_kn: float = Field(gt=0)
    infill_kpa: float = Field(gt=0)


class FoundationsInputs(Strict):
    ground_conditions: Literal["Good Ground (NZS 3604)", "TC1", "TC2", "TC3"]   # general ground conditions
    expansive_soils_suspected: bool
    site_soils_class: Literal["A", "S", "M", "H1", "H2", "E"] | None = None    # AS 2870-2011; only when expansive soils are suspected
    narrative: str = ""

    @model_validator(mode="after")
    def _soils_class_follows_expansive_soils(self) -> FoundationsInputs:
        if self.expansive_soils_suspected and self.site_soils_class is None:
            raise ValueError("expansive soils are suspected, so the site soils class (siteSoilsClass) is required")
        if not self.expansive_soils_suspected and self.site_soils_class is not None:
            raise ValueError("siteSoilsClass is given, but expansive soils are not suspected")
        return self


class ScrInputs(Strict):
    importance_level: Literal["IL1", "IL2", "IL3", "IL4"] = "IL2"
    # Not inputs: the document ID ("<job number>-SCR-Rev <latest revision>") and
    # the report date (the latest revision's issue date, else today in NZ).
    revisions: list[Revision] = []     # oldest first; the last one is the current revision
    # The preparing and reviewing engineers come from the portal, not from here.
    scope_extra: list[Text] = []       # scope items beyond the element categories
    alternative_solutions: list[Text] = []   # empty = none adopted
    narratives: dict[int, Text] = {}   # element id -> its type's scrNarrative as edited for this project
    live_loads: list[LiveLoad] | None = None       # None = the firm defaults
    barrier_loads: BarrierLoads | None = None      # None = the firm defaults (if a barrier element exists)
    foundations: FoundationsInputs | None = None
    # The basis of opinions (architect's drawings, geotechnical report) comes from the portal.

    @model_validator(mode="after")
    def _revision_record(self) -> ScrInputs:
        if any(r.issued_on is None for r in self.revisions[:-1]):
            raise ValueError("only the latest revision can be unissued; every earlier one needs its issue date (issuedOn)")
        issued = [r.issued_on for r in self.revisions if r.issued_on]
        if issued != sorted(issued):
            raise ValueError("the revisions' issue dates (issuedOn) must not go backwards")
        for r in self.revisions:
            if r.issued_on and r.cites_drawings is None:
                raise ValueError(f"SCR revision {r.description!r} is issued, so it needs citesDrawings (stamped on "
                                 "issue from X-Cites-Drawings; \"\" if no drawing review was completed then)")
        return self


# --- SIR (site inspection reports) --------------------------------------------

class SiteContact(Strict):
    """The builder's site contact, from the inspection order. The email receives
    the link to upload corrections when an observation fails."""

    name: Text
    phone: str = ""
    email: str = ""


class FailureNotice(Strict):
    """An email to the site contact with the link to upload a correction. Sent
    when an observation fails, and again after a correction is rejected."""

    sent_at: AwareDatetime
    sent_to: Text                      # the email address it went to


class CorrectionReview(Strict):
    """The engineer's decision on a correction."""

    decision: Literal["Approved", "Rejected"]
    reviewed_at: AwareDatetime
    reviewed_by: Text                  # the engineer, from the portal session
    comment: str = ""                  # required for a rejection: what is still wrong (sent to the builder)

    @model_validator(mode="after")
    def _rejection_says_why(self) -> CorrectionReview:
        if self.decision == "Rejected" and not self.comment.strip():
            raise ValueError("a rejected correction needs a comment saying what is still wrong")
        return self


class Correction(Strict):
    """One attempt by the builder, uploaded through the link in a failure notice."""

    notes: str = ""
    photos: list[Text] = Field(min_length=1)   # https URLs; at least one
    submitted_at: AwareDatetime
    submitted_by: Text                 # who uploaded it: the site contact the link was sent to
    review: CorrectionReview | None = None     # None = waiting for the engineer


class Observation(Strict):
    """One observation. Its `id` is stable (set by the portal or app when it is
    created) so the correction link always reaches this record, whatever happens
    to the observations around it."""

    id: Text
    text: Text                         # starts from the inspection's standard observations; edited on site
    photos: list[Text] = []            # https URLs, taken on site
    result: Literal["Pass", "Fail"] | None = None
    # For a failure:
    required_correction: str = ""      # the engineer's note on what to correct: emailed to the builder, printed
    notices: list[FailureNotice] = []  # every email sent with the correction link
    corrections: list[Correction] = []     # the builder's attempts, oldest first

    @model_validator(mode="after")
    def _attempts_in_order(self) -> Observation:
        for c in self.corrections[:-1]:
            if c.review is None or c.review.decision != "Rejected":
                raise ValueError(f"observation {self.id}: only the latest correction can be unreviewed or approved; "
                                 "every earlier one must have been rejected")
        return self


class InspectedItem(Strict):
    """One checklist item inspected on a visit, with its observations."""

    inspection: Text                   # the checklist item (an Inspection's `item`)
    elements: list[int] = []           # the project's elements this inspection covered (ids); pre-ticked with all
                                       # whose type has the inspection. Empty for an inspection added on the project.
    element: str = ""                  # "Structural Element Inspected", e.g. "Foundation slab and ground beam at GL E-I/1-2"
    drawing_sheets: str = ""           # e.g. "sheets 1/3/4/5/14"; printed after the drawing set's revision
    observations: list[Observation] = []


class SiteVisit(Strict):
    """One Site Inspection Report: SIR01, SIR02, … (the number is set by the
    portal when the report is started). It stays a draft until every observation
    has passed or its failure has an approved correction; then it is issued."""

    number: int = Field(ge=1)
    inspection_date: date | None = None    # the day on site, set by the app
    site_contact: SiteContact | None = None
    items: list[InspectedItem] = []
    actions: list[Text] = []               # "Actions Required": ticked standard actions and the engineer's own
    issued_at: AwareDatetime | None = None   # stamped on issue, never typed; the SIR is then locked
    pdf_url: str = ""                      # where the portal keeps the issued, signed PDF (https); the PS4 attaches it


class OfficeCheck(Strict):
    """A checklist item done in the office (e.g. Shop Drawing Check), marked complete."""

    inspection: Text                   # the checklist item
    completed_on: date                 # pre-filled with the day it is marked complete (NZ)
    notes: str = ""                    # e.g. which shop drawing revision was checked


class SirInputs(Strict):
    additional_inspections: list[Inspection] = []   # added on the project; on the checklist with the library's
    visits: list[SiteVisit] = []
    office_checks: list[OfficeCheck] = []

    @model_validator(mode="after")
    def _unique_numbers_and_ids(self) -> SirInputs:
        numbers = [v.number for v in self.visits]
        dupes = sorted({n for n in numbers if numbers.count(n) > 1})
        if dupes:
            raise ValueError(f"SIR number(s) used more than once: {', '.join(f'SIR{n:02d}' for n in dupes)}")
        ids = [o.id for v in self.visits for it in v.items for o in it.observations]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"observation id(s) used more than once: {', '.join(dupes)}")
        return self


# --- RFI responses (council requests for further information) ----------------

class RfiItem(Strict):
    """One request in a council's RFI, pasted by the architect into its own box,
    and the reviewing engineer's answer. Its `id` is stable (set by the portal
    when the architect adds it)."""

    id: Text
    heading: str = ""                  # the council's heading, e.g. "B1: Deck Structure and Decking"
    question: Text                     # the council's text, as pasted (line breaks kept)
    answer: str = ""                   # the reviewing engineer's answer
    images: list[Text] = []            # https URLs (PNG or JPEG), e.g. screenshots, printed under the answer
    # The project documents the answer cites. "revised": revised in response to this RFI, so the letter
    # can't be submitted until the new revision exists (a completed drawing review, an issued SCR revision).
    drawings: Literal["cited", "revised"] | None = None
    drawing_sheets: str = ""           # the sheets cited or revised, e.g. "S104, S105"
    calculations: Literal["cited", "revised"] | None = None   # the Structural Calculations Report
    ps1: Literal["cited", "revised"] | None = None            # the PS1 (its latest revision)
    external_id: str = ""              # the item's id in an outside RFI system (e.g. a later Objective Build
                                       # import); not printed


class RfiRound(Strict):
    """One council RFI and our response letter: RFI01, RFI02, … (a further RFI
    from the council is a new round). The architect enters the items; the
    reviewing engineer answers and submits, which issues the letter. No dates
    are typed."""

    number: int = Field(ge=1)
    received_at: AwareDatetime         # when the architect sent the questions to the engineer (stamped by the portal)
    items: list[RfiItem] = Field(min_length=1)
    issued_at: AwareDatetime | None = None   # stamped when the engineer submits; the letter is then locked

    @property
    def raised_on(self) -> date:
        """The date the letter gives for the RFI ("raised on …"): the NZ date the
        architect sent it to the engineer. Automatic, not entered."""
        return nz_date(self.received_at)


class RfiInputs(Strict):
    rounds: list[RfiRound] = []

    @model_validator(mode="after")
    def _unique_numbers_and_ids(self) -> RfiInputs:
        numbers = [r.number for r in self.rounds]
        dupes = sorted({n for n in numbers if numbers.count(n) > 1})
        if dupes:
            raise ValueError(f"RFI number(s) used more than once: {', '.join(f'RFI{n:02d}' for n in dupes)}")
        ids = [i.id for r in self.rounds for i in r.items]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"RFI item id(s) used more than once: {', '.join(dupes)}")
        return self


# --- PS4 (construction review) ---------------------------------------------------

class SuppliedDocument(Strict):
    """A document someone else issued, uploaded by the builder with the PS4
    order: a PS3 from the steel fabricator, or the builder's Record of Work.
    The PS4 lists it in its Schedule and attaches it."""

    file_url: Text                     # https, a PDF
    issued_by: str = ""                # the fabricator (a PS3: required); the LBP (Record of Work: else the builder)
    issued_on: date | None = None      # the document's own date, if the builder gives it
    uploaded_at: AwareDatetime | None = None   # stamped by the portal


class Ps4Revision(Strict):
    """One issue of the PS4 (Rev A, B, …), as for the PS1: only the description
    is typed; the moment of issue and what it cited are stamped on issue."""

    description: Text                  # e.g. "Code Compliance Certificate"
    issued_at: AwareDatetime | None = None   # stamped on issue (X-Issued-At); None = the draft
    cites_ps1: str = ""                # stamped on issue (X-Cites-Ps1): the PS1 revision it covers, e.g. "P260703-PS1-Rev B"
    cites_sirs: list[str] = []         # stamped on issue (X-Cites-Sirs): the SIRs it attached, e.g. ["P260703-SIR01"]


class Ps4Inputs(Strict):
    """The PS4: what the builder uploads with the PS4 order, the one engineer
    choice, and the revision record. Everything else is shared with the PS1 or
    comes from the portal."""

    ps3s: list[SuppliedDocument] = []  # from the steel fabricator(s); required when an element uses mild steel
    record_of_work: SuppliedDocument | None = None   # the builder's Record of Work
    record_of_work_required: bool = True   # the engineer can issue the PS4 without one
    revisions: list[Ps4Revision] = []  # oldest first; once the latest is issued the PS4 is locked until a revision is added

    @model_validator(mode="after")
    def _ps3s_and_revisions(self) -> Ps4Inputs:
        for d in self.ps3s:
            if not d.issued_by.strip():
                raise ValueError("each PS3 needs issuedBy: the fabricator who issued it")
        if any(r.issued_at is None for r in self.revisions[:-1]):
            raise ValueError("only the latest PS4 revision can be unissued; every earlier one needs issuedAt")
        for r in self.revisions:
            if r.issued_at and not r.cites_ps1:
                raise ValueError(f"PS4 revision {r.description!r} is issued, so it needs citesPs1 and citesSirs "
                                 "(stamped on issue)")
        issued = [r.issued_at for r in self.revisions if r.issued_at]
        if issued != sorted(issued):
            raise ValueError("the PS4 revisions' issue times (issuedAt) must not go backwards")
        return self


class Reports(Strict):
    ps1: Ps1Inputs = Ps1Inputs()
    scr: ScrInputs = ScrInputs()
    sir: SirInputs = SirInputs()
    rfi: RfiInputs = RfiInputs()
    ps4: Ps4Inputs = Ps4Inputs()


# --- the project ----------------------------------------------------------

class Project(Portal):
    # portal
    id: str
    project_id: Text                   # the job number printed on the reports
    name: Text
    project_description: str = ""
    site_address: Text                 # one string
    # The same address in parts, for the PS1's Certificate of Design Work (requested; not sent yet):
    site_street_address: str = ""
    site_suburb: str = ""
    site_town_city: str = ""
    site_postcode: str = ""
    legal_description: str = ""
    territorial_authority: str = ""    # the council: a name from data/territorial_authorities.json, picked in the portal
    status: str = ""
    building_consent_number: str = ""
    building_consent_amendments: list[Text] = []   # amendment numbers; the architect adds them when ordering inspections
    client: Client
    internal_reviewing_engineer: ReviewingEngineer | None = None
    inspection_engineer: ReviewingEngineer | None = None   # the portal's inspection engineer role: inspects and signs SIRs
    ps1_certificate_data: Ps1CertificateData | None = None
    structural: Structural = Structural()
    assemblies: list[Assembly] = []
    architect: Architect | None = None
    builder: Builder | None = None
    drawing_reviews: list[DrawingReview] = []
    geotechnical_report: GeotechnicalReport | None = None
    structural_calculation_report_url: str | None = None
    # ours
    elements: list[Element] = []
    durability: Durability = Durability()
    reports: Reports = Reports()


def load_project(path: str | Path) -> Project:
    """Read and validate a project file."""
    return Project.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
