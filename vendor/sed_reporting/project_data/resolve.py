"""A project resolved against the element library: the views the reports print,
and the problems that must be fixed (or acknowledged) before issuing them.

Problems are collected rather than raised one at a time, so the review page can
show them all at once. An "error" blocks the report it names; a "warning" is
shown to the engineer but does not block.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sed_reporting.project_data.councils import TerritorialAuthorities, TerritorialAuthority, load_councils
from sed_reporting.project_data.dates import long_date_time, nz_date
from sed_reporting.project_data.defaults import DesignDefaults, load_defaults
from sed_reporting.project_data.library import ElementLibrary, ElementType, Inspection
from sed_reporting.project_data.maintenance import check_materials, load_maintenance_items
from sed_reporting.project_data.materials import Material, Materials, check_element_types, load_materials
from sed_reporting.project_data.project import (
    MAINTENANCE_INTERVALS, BarrierLoads, Element, LiveLoad, MaintenanceItems, Project, RbwRow,
)

# Scope order: the order the Cognito form lists element categories in.
CATEGORY_ORDER = ["Bracing", "Retaining Walls", "Foundations", "Beams", "Posts", "Portal Frames"]

# Which durability block each material needs. Only the Structural Calculations
# Report prints the values; the B2 letter uses the library's fixed text per material.
DURABILITY_FOR_MATERIAL = {
    "Mild steel": "steel",
    "Reinforced concrete": "concrete",
    "Reinforced masonry": "concrete",
    "Steel timber fixings": "steel_fixings",
}


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    report: Literal["all", "ps1", "scr", "sir", "rfi", "ps4"]
    message: str


@dataclass(frozen=True)
class ResolvedElement:
    element: Element
    type: ElementType | None       # None if the code is not in the library
    materials: tuple[Material, ...] = ()   # every material its type has (materials.json)


@dataclass(frozen=True)
class B2Row:
    material: str                  # the B2 label, e.g. "Structural timber"
    means_of_compliance: str       # "B2/AS1" or "Alternative Solution"
    details: str | None


@dataclass(frozen=True)
class ChecklistLine:
    """One checklist item and whether it is done. A library inspection is done
    once issued SIRs have covered every element whose type has it; one added on
    the project, once an issued SIR has covered it; an office check, once it is
    marked complete."""

    inspection: Inspection
    sir_numbers: list[int]             # site inspections: the issued SIRs that covered it
    completed_on: date | None          # office checks: the day it was marked complete
    elements: list[int] = ()           # the elements it applies to (their types have it)
    covered: list[int] = ()            # of those, the ones issued SIRs have covered

    @property
    def done(self) -> bool:
        if not self.inspection.on_site:
            return self.completed_on is not None
        if self.elements:
            return set(self.elements) <= set(self.covered)
        return bool(self.sir_numbers)


@dataclass(frozen=True)
class RbwLine:
    """One row of the Certificate of Design Work's table of restricted building work."""

    row: str                       # "Foundations", "Beams", …
    applies: bool                  # the project has an element of a type in this row
    description: str | None        # the engineer's text, else the library's; None if neither
    carried_out_or_supervised: str | None


RBW_ROWS: list[str] = list(typing.get_args(RbwRow))


@dataclass(frozen=True)
class DeadLoad:
    category: str                  # the portal's assembly category: "WALL", "ROOF", "FLOOR"
    name: str
    total_kpa: float | None


@dataclass(frozen=True)
class DrawingSet:
    reference: str                 # "<job number>-DRG-Rev <letter>", e.g. "P260703-DRG-Rev A"
    reviewed_on: date              # the NZ date its review was completed


# Where a failed observation stands. The portal shows it; only "passed" and "corrected" let a SIR issue.
OBSERVATION_STATES = {
    "unmarked": "not marked Pass or Fail",
    "passed": "passed",
    "describe": "failed: say what the builder must correct",
    "notify": "failed: the builder hasn't been sent the correction link",
    "awaiting-correction": "failed: waiting for the builder's correction",
    "awaiting-review": "failed: the builder's correction is waiting for the engineer's review",
    "corrected": "failed, corrected and approved",
}


def observation_state(o) -> str:
    """Where an observation stands on the failure path (a key of OBSERVATION_STATES)."""
    if o.result is None:
        return "unmarked"
    if o.result == "Pass":
        return "passed"
    if not o.required_correction.strip():
        return "describe"
    rejected = sum(1 for c in o.corrections if c.review and c.review.decision == "Rejected")
    if len(o.notices) < 1 + rejected:          # one notice for the failure, and one after each rejection
        return "notify"
    last = o.corrections[-1] if o.corrections else None
    if last is None or (last.review and last.review.decision == "Rejected"):
        return "awaiting-correction"
    if last.review is None:
        return "awaiting-review"
    return "corrected"


def revision_letter(index: int) -> str:
    """The letter of the revision at `index` in a record: A, B, … Z, AA, AB, …
    Shared by the report's own revisions and the drawing set's."""
    letters, n = "", index + 1
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(ord("A") + r) + letters
    return letters


BARRIER_CATEGORY = "Barriers"      # an element type in this category brings in the barrier loads


class ProjectData:
    """A project, the library it refers to, the firm defaults and the list of
    councils, with the views the reports use."""

    def __init__(self, project: Project, library: ElementLibrary, defaults: DesignDefaults | None = None,
                 councils: TerritorialAuthorities | None = None, maintenance_items: MaintenanceItems | None = None,
                 materials: Materials | None = None):
        self.project = project
        self.library = library
        self.defaults = defaults or load_defaults()
        self.councils = councils or load_councils()
        self.maintenance_items = maintenance_items or load_maintenance_items()
        self.materials = materials or load_materials()
        check_element_types(library, self.materials)
        check_materials(self.materials, self.maintenance_items)
        self.elements = []
        for e in project.elements:
            t = library.element_type(e.type)
            mats = tuple(self.materials.find(n) for n in t.materials) if t else ()
            self.elements.append(ResolvedElement(e, t, mats))       # check_element_types: all found

    # --- views ------------------------------------------------------------

    @property
    def categories(self) -> list[str]:
        """The element categories present, in the form's order (then any others, alphabetically)."""
        cats = {r.type.category for r in self.elements if r.type}
        return [c for c in CATEGORY_ORDER if c in cats] + sorted(cats - set(CATEGORY_ORDER))

    @property
    def scope_labels(self) -> list[str]:
        """"SED <category>" for each category present, in the form's order."""
        return [f"SED {c}" for c in self.categories]

    def elements_in(self, category: str) -> list[ResolvedElement]:
        return [r for r in self.elements if r.type and r.type.category == category]

    @property
    def design_items(self) -> list[ResolvedElement]:
        """The elements in report order (by category, in the form's order): one
        section each in the report, and the order of the calculation appendix."""
        return [r for cat in self.categories for r in self.elements_in(cat)]

    def default_narrative(self, element_id: int) -> str | None:
        """The element type's text from the library (scrNarrative)."""
        r = next((r for r in self.elements if r.element.id == element_id), None)
        return r.type.scr_narrative if r and r.type else None

    def narrative(self, element_id: int) -> str | None:
        """The engineer's text for an element, else the library's, else None."""
        return self.project.reports.scr.narratives.get(element_id) or self.default_narrative(element_id)

    @property
    def durability_needed(self) -> list[str]:
        """The durability blocks the elements' materials call for (snake_case names)."""
        return _unique(DURABILITY_FOR_MATERIAL[m.name] for m in self.materials_used if m.name in DURABILITY_FOR_MATERIAL)

    @property
    def dead_loads(self) -> list[DeadLoad]:
        """The portal's assemblies; `calculatedTotalWeight` is in kPa."""
        return [DeadLoad(a.category, a.name, a.calculated_total_weight) for a in self.project.assemblies]

    @property
    def live_loads(self) -> list[LiveLoad]:
        return self.project.reports.scr.live_loads or self.defaults.live_loads.residential

    @property
    def has_barrier(self) -> bool:
        return any(r.type and r.type.category == BARRIER_CATEGORY for r in self.elements)

    @property
    def barrier_loads(self) -> BarrierLoads | None:
        if not self.has_barrier:
            return None
        return self.project.reports.scr.barrier_loads or self.defaults.live_loads.barriers

    @property
    def standards(self) -> list[str]:
        """Every standard of the project's element types, once, in first-seen order."""
        return _unique(s for r in self.elements if r.type for s in r.type.standards)

    @property
    def inspections(self) -> list[Inspection]:
        """The project's checklist: the element types' inspections in element order,
        each identical row once, then those added on the project. The PS1's
        Construction Monitoring Schedule and the SIRs both use it."""
        library = _unique(i for r in self.elements if r.type for i in r.type.inspections)
        return library + [i for i in self.project.reports.sir.additional_inspections
                          if i.item not in {x.item for x in library}]

    # --- SIR -----------------------------------------------------------------

    def visit(self, number: int):
        """The SIR with this number, or None."""
        return next((v for v in self.project.reports.sir.visits if v.number == number), None)

    @property
    def checklist_status(self) -> list[ChecklistLine]:
        """Each checklist item and how it was done: a site inspection by the issued
        SIRs that covered it (an issued SIR has every observation passed or
        corrected), an office check by being marked complete."""
        sir = self.project.reports.sir
        issued = [v for v in sir.visits if v.issued_at]
        office = {c.inspection: c for c in sir.office_checks}
        out = []
        for i in self.inspections:
            numbers = [v.number for v in issued if any(it.inspection == i.item for it in v.items)] if i.on_site else []
            check = office.get(i.item) if not i.on_site else None
            applies = self.inspection_elements(i.item) if i.on_site else []
            covered = sorted({e for v in issued for it in v.items if it.inspection == i.item for e in it.elements}
                             & set(applies))
            out.append(ChecklistLine(i, numbers, check.completed_on if check else None, applies, covered))
        return out

    def inspection_elements(self, item: str) -> list[int]:
        """The project's elements whose type has this inspection, in element order
        (none for an inspection added on the project)."""
        return [r.element.id for r in self.elements if r.type and any(i.item == item for i in r.type.inspections)]

    def element_label(self, element_id: int) -> str:
        """"Element 4 (PF1): Portal Frame for Living Room"."""
        r = next((r for r in self.elements if r.element.id == element_id), None)
        if r is None:
            return f"Element {element_id}"
        return f"Element {element_id} ({r.element.type}): {r.element.description}"

    def office_check_issues(self) -> list[Issue]:
        """Office checks must be office items on the checklist, each marked once."""
        items, out = {i.item: i for i in self.inspections}, []
        seen = [c.inspection for c in self.project.reports.sir.office_checks]
        for name in seen:
            i = items.get(name)
            if i is None:
                out.append(Issue("error", "sir", f"office check {name!r} is not on the project's checklist"))
            elif i.on_site:
                out.append(Issue("error", "sir", f"{name!r} is a site inspection: it is done by an issued SIR, "
                                                 "not marked complete in the office"))
        for dup in sorted({n for n in seen if seen.count(n) > 1}):
            out.append(Issue("error", "sir", f"office check {dup!r} is marked complete more than once"))
        return out

    def sir_issues(self, number: int) -> list[Issue]:
        """What stands in the way of issuing SIR <number> (report "sir")."""
        v, tag, out = self.visit(number), f"SIR{number:02d}", []
        if v is None:
            return [Issue("error", "sir", f"{tag} does not exist")]
        checklist = {i.item: i for i in self.inspections}
        if self.project.inspection_engineer is None:
            out.append(Issue("error", "sir", "the project has no inspection engineer (inspectionEngineer)"))
        if v.inspection_date is None:
            out.append(Issue("error", "sir", f"{tag}: no inspection date (set by the app on site)"))
        if v.site_contact is None:
            out.append(Issue("warning", "sir", f"{tag}: no site contact (from the builder's inspection order)"))
        elif not v.site_contact.email:
            out.append(Issue("warning", "sir", f"{tag}: the site contact has no email, so failure notices can't be sent"))
        if not v.items:
            out.append(Issue("error", "sir", f"{tag}: nothing inspected yet"))
        for n, it in enumerate(v.items, start=1):
            where = f"{tag}, item {n} ({it.inspection})"
            if it.inspection not in checklist:
                out.append(Issue("error", "sir", f"{where}: not on the project's checklist"))
            elif not checklist[it.inspection].on_site:
                out.append(Issue("error", "sir", f"{where}: an office check, done before fabrication and not on "
                                                 "site; mark it complete instead"))
            else:
                applies = self.inspection_elements(it.inspection)
                wrong = [e for e in it.elements if e not in applies]
                if wrong:
                    out.append(Issue("error", "sir", f"{where}: element(s) {', '.join(map(str, wrong))} don't have this "
                                                     "inspection"))
                if applies and not it.elements:
                    out.append(Issue("error", "sir", f"{where}: tick the elements this inspection covered "
                                                     f"({', '.join(map(str, applies))})"))
            if not it.observations:
                out.append(Issue("error", "sir", f"{where}: no observations"))
            for k, o in enumerate(it.observations, start=1):
                state = observation_state(o)
                if state not in ("passed", "corrected"):
                    out.append(Issue("error", "sir", f"{where}, observation {k}: {OBSERVATION_STATES[state]}"))
                if o.result == "Pass" and (o.corrections or o.notices):
                    out.append(Issue("error", "sir", f"{where}, observation {k}: marked Pass, but a failure was "
                                                     "recorded; a failed observation stays failed until its "
                                                     "correction is approved"))
        return out

    # --- PS4 -----------------------------------------------------------------

    @property
    def ps4_document_id(self) -> str | None:
        """"<job number>-PS4-Rev <latest revision>"; None while it has no revision."""
        n = len(self.project.reports.ps4.revisions)
        return f"{self.project.project_id}-PS4-Rev {revision_letter(n - 1)}" if n else None

    @property
    def ps4_issued_at(self):
        """When the PS4's latest revision was issued, or None while it is a draft
        (or there is none). Once set, the PS4 is locked until a revision is added."""
        revisions = self.project.reports.ps4.revisions
        return revisions[-1].issued_at if revisions else None

    @property
    def ps4_last_issued_label(self) -> str:
        issued = [i for i, r in enumerate(self.project.reports.ps4.revisions) if r.issued_at]
        return f"Rev {revision_letter(issued[-1])}" if issued else ""

    @property
    def ps1_issued_id(self) -> str | None:
        """The PS1's latest issued revision, "P260703-PS1-Rev B"; None if none is issued."""
        issued = [i for i, r in enumerate(self.project.reports.ps1.revisions) if r.issued_at]
        return f"{self.project.project_id}-PS1-Rev {revision_letter(issued[-1])}" if issued else None

    @property
    def issued_sirs(self) -> list:
        """The issued SIRs, in number order: what the PS4 attaches."""
        return sorted((v for v in self.project.reports.sir.visits if v.issued_at), key=lambda v: v.number)

    def sir_id(self, number: int) -> str:
        return f"{self.project.project_id}-SIR{number:02d}"

    @property
    def ps3_required(self) -> bool:
        """A PS3 from the steel fabricator is needed when any element uses mild
        steel (fabricated). Steel timber fixings are off the shelf: not included."""
        return any(m.name == "Mild steel" for m in self.materials_used)

    @property
    def ps4_out_of_date(self) -> list[str]:
        """What the latest issued PS4 revision covers that has since changed: the
        PS1 revised, or SIRs issued since. Empty when up to date or none is issued."""
        issued = [r for r in self.project.reports.ps4.revisions if r.issued_at]
        if not issued:
            return []
        last, out = issued[-1], []
        if (ps1 := self.ps1_issued_id) and ps1 != last.cites_ps1:
            out.append(f"{last.cites_ps1}, now {ps1}")
        sirs = [self.sir_id(v.number) for v in self.issued_sirs]
        if new := [s for s in sirs if s not in last.cites_sirs]:
            out.append(f"SIRs issued since: {', '.join(new)}")
        return out

    def ps4_issues(self) -> list[Issue]:
        """What stands in the way of issuing the PS4 (report "ps4"): every
        checklist item done and every SIR issued, the PS1 it covers issued and up
        to date, and the documents the builder uploads with the PS4 order."""
        p, ps4, out = self.project, self.project.reports.ps4, []
        if not ps4.revisions:
            out.append(Issue("error", "ps4", "the PS4 has no revision: add one (only its description is typed; the "
                                             "letter and the issue date are automatic)"))
        elif self.ps4_issued_at and (changes := self.ps4_out_of_date):
            out.append(Issue("warning", "ps4", f"the issued PS4 ({self.ps4_last_issued_label}) is out of date "
                                               f"({'; '.join(changes)}): add a PS4 revision"))
        if p.reports.ps1.construction_monitoring_level == "Nil":
            out.append(Issue("error", "ps4", "the PS1 recommends no construction monitoring (Nil), so there is no "
                                             "construction review to certify"))
        if not p.building_consent_number:
            out.append(Issue("error", "ps4", "the project has no consent number (buildingConsentNumber)"))
        # The PS1 it covers: issued, and citing the documents as they now stand.
        ps1 = p.reports.ps1.revisions
        if not self.ps1_issued_id:
            out.append(Issue("error", "ps4", "the PS4 covers the PS1, which is not issued yet"))
        elif ps1[-1].issued_at is None:
            out.append(Issue("error", "ps4", f"the PS1's {self.ps1_revision_label} is a draft: issue it first"))
        elif changes := self.ps1_out_of_date:
            out.append(Issue("error", "ps4", f"the PS1 it covers ({self.ps1_last_issued_label}) cites documents that "
                                             f"have since been revised ({'; '.join(changes)}): issue a new PS1 "
                                             "revision first"))
        # The construction review: every checklist item done, every SIR issued and kept by the portal.
        drafts = [v for v in p.reports.sir.visits if not v.issued_at]
        for c in self.checklist_status:
            if c.done:
                continue
            if not c.inspection.on_site:
                out.append(Issue("error", "ps4", f"checklist: {c.inspection.item!r} is not marked complete"))
                continue
            todo = [e for e in c.elements if e not in c.covered]
            message = (f"checklist: {c.inspection.item!r} is not done for " + "; ".join(self.element_label(e) for e in todo)
                       if c.elements else f"checklist: {c.inspection.item!r} is not covered by an issued SIR")
            # Covered in a SIR that isn't issued yet: say which, so it's clear what finishes it.
            pending = [f"SIR{v.number:02d}" for v in sorted(drafts, key=lambda v: v.number)
                       if any(it.inspection == c.inspection.item and (not c.elements or set(todo) & set(it.elements))
                              for it in v.items)]
            if pending:
                message += f" (covered in {', '.join(pending)}, which {'is' if len(pending) == 1 else 'are'} not issued yet)"
            out.append(Issue("error", "ps4", message))
        for v in sorted(p.reports.sir.visits, key=lambda v: v.number):
            if not v.issued_at:
                out.append(Issue("error", "ps4", f"SIR{v.number:02d} is not issued"))
            elif not v.pdf_url:
                out.append(Issue("error", "ps4", f"SIR{v.number:02d} has no stored PDF (pdfUrl), so it can't be attached"))
        if not p.reports.sir.visits:
            out.append(Issue("error", "ps4", "no SIR has been issued"))
        # The builder's uploads with the PS4 order.
        if self.ps3_required and not ps4.ps3s:
            out.append(Issue("error", "ps4", "an element uses mild steel, so a PS3 from the steel fabricator is needed "
                                             "(uploaded by the builder with the PS4 order)"))
        if ps4.record_of_work_required and ps4.record_of_work is None:
            out.append(Issue("error", "ps4", "the builder's Record of Work is needed (uploaded with the PS4 order), "
                                             "unless the PS4 is issued without one"))
        return out

    # --- RFI responses -------------------------------------------------------

    def rfi_round(self, number: int):
        """The RFI round with this number, or None."""
        return next((r for r in self.project.reports.rfi.rounds if r.number == number), None)

    def rfi_issues(self, number: int) -> list[Issue]:
        """What stands in the way of submitting the response to RFI <number>
        (report "rfi"). A document the answer cites must be issued; one it
        revised must have a new revision since the questions were received."""
        r, tag, out = self.rfi_round(number), f"RFI{number:02d}", []
        if r is None:
            return [Issue("error", "rfi", f"{tag} does not exist")]
        p = self.project
        if not p.building_consent_number:
            out.append(Issue("error", "rfi", "the project has no consent number (buildingConsentNumber, set in the "
                                             "portal); the letter needs it"))
        received = long_date_time(r.received_at)
        reviews_since = [d for d in p.drawing_reviews if d.completed_at > r.received_at]
        scr = p.reports.scr.revisions
        scr_latest = (f"Rev {revision_letter(len(scr) - 1)}") if scr else ""
        for k, it in enumerate(r.items, start=1):
            where = f"{tag}, item {k} ({it.heading or it.question[:40]})"
            if not it.answer.strip():
                out.append(Issue("error", "rfi", f"{where}: no answer yet"))
            if it.drawings and self.drawing_set is None:
                out.append(Issue("error", "rfi", f"{where}: cites the drawings, but no drawing review has been "
                                                 "completed (drawingReviews)"))
            if it.drawings == "revised":
                if not it.drawing_sheets.strip():
                    out.append(Issue("error", "rfi", f"{where}: say which drawing sheets were revised"))
                if self.drawing_set is not None and not reviews_since:
                    out.append(Issue("error", "rfi", f"{where}: the drawings are marked as revised, but no drawing "
                                                     f"review has been completed since the RFI was received "
                                                     f"({received}); complete the review of the revised set first"))
            if it.calculations and not scr:
                out.append(Issue("error", "rfi", f"{where}: cites the calculations, but the Structural Calculations "
                                                 "Report has no revision"))
            elif it.calculations and not scr[-1].issued_on:
                out.append(Issue("error", "rfi", f"{where}: cites the Structural Calculations Report's {scr_latest}, "
                                                 "which is not issued yet; issue it first"))
            elif it.calculations == "revised" and scr[-1].issued_on < nz_date(r.received_at):
                out.append(Issue("error", "rfi", f"{where}: the calculations are marked as revised, but no revision "
                                                 "of the Structural Calculations Report has been issued since the "
                                                 f"RFI was received ({received}); add and issue one"))
            if it.ps1 and not p.reports.ps1.revisions:
                out.append(Issue("error", "rfi", f"{where}: cites the PS1, which has no revision yet"))
            elif it.ps1 and self.ps1_issued_at is None:
                out.append(Issue("error", "rfi", f"{where}: cites the PS1's {self.ps1_revision_label}, which is not "
                                                 "issued yet; issue it first"))
            elif it.ps1 == "revised" and not any(x.issued_at and x.issued_at > r.received_at
                                                 for x in p.reports.ps1.revisions):
                out.append(Issue("error", "rfi", f"{where}: the PS1 is marked as revised, but no PS1 revision has been "
                                                 f"issued since the RFI was received ({received}); add and issue one"))
        # Whether or not an answer cites them: the issued SCR and PS1 must cite the documents as they now stand.
        if changes := self.scr_out_of_date:
            out.append(Issue("error", "rfi", f"the issued SCR ({self.scr_last_issued_label}) cites drawings that have "
                                             f"since been revised ({'; '.join(changes)}); issue a new SCR revision "
                                             "first"))
        if changes := self.ps1_out_of_date:
            last = self.ps1_last_issued_label
            out.append(Issue("error", "rfi", f"the issued PS1 ({last}) cites documents that have since been revised "
                                             f"({'; '.join(changes)}); issue a new PS1 revision first"))
        return out

    @property
    def b2_rows(self) -> list[B2Row]:
        """One B2 letter row per material used, in element order."""
        return [B2Row(m.b2_label, m.b2_means_of_compliance, m.b2_details) for m in self.materials_used]

    @property
    def materials_used(self) -> list[Material]:
        """Every material of the elements' types, in element order, each once."""
        return _unique(m for r in self.elements for m in r.materials)

    # --- PS1 ---------------------------------------------------------------

    @property
    def ps1_document_id(self) -> str | None:
        """"<job number>-PS1-Rev <latest revision>", e.g. "P260703-PS1-Rev B"; None
        while the PS1 has no revision."""
        n = len(self.project.reports.ps1.revisions)
        return f"{self.project.project_id}-PS1-Rev {revision_letter(n - 1)}" if n else None

    @property
    def ps1_revision_label(self) -> str:
        """"Rev B", the latest revision; "" while there is none."""
        n = len(self.project.reports.ps1.revisions)
        return f"Rev {revision_letter(n - 1)}" if n else ""

    @property
    def ps1_issued_at(self):
        """When the PS1's latest revision was issued, or None while it is a draft
        (or there is none). Once set, the PS1 is locked until a revision is added."""
        revisions = self.project.reports.ps1.revisions
        return revisions[-1].issued_at if revisions else None

    @property
    def ps1_last_issued_label(self) -> str:
        """"Rev A": the latest issued revision; "" if none is issued."""
        issued = [i for i, r in enumerate(self.project.reports.ps1.revisions) if r.issued_at]
        return f"Rev {revision_letter(issued[-1])}" if issued else ""

    @property
    def scr_issued_id(self) -> str | None:
        """The SCR's latest issued revision, "P260703-SCR-Rev B"; None if none is issued."""
        issued = [i for i, r in enumerate(self.project.reports.scr.revisions) if r.issued_on]
        return f"{self.project.project_id}-SCR-Rev {revision_letter(issued[-1])}" if issued else None

    @property
    def scr_out_of_date(self) -> list[str]:
        """What the SCR's latest issued revision cites that has since been
        revised: "P260703-DRG-Rev A, now P260703-DRG-Rev B". Empty when it is up
        to date, or when no revision is issued yet."""
        issued = [r for r in self.project.reports.scr.revisions if r.issued_on]
        if not issued:
            return []
        cited, now = issued[-1].cites_drawings or "", self.drawing_set.reference if self.drawing_set else ""
        return [f"{cited or 'no reviewed drawings'}, now {now}"] if now != cited else []

    @property
    def scr_last_issued_label(self) -> str:
        """"Rev B": the SCR's latest issued revision; "" if none is issued."""
        issued = [i for i, r in enumerate(self.project.reports.scr.revisions) if r.issued_on]
        return f"Rev {revision_letter(issued[-1])}" if issued else ""

    @property
    def ps1_out_of_date(self) -> list[str]:
        """What the latest issued PS1 revision cites that has since been revised:
        "P260703-SCR-Rev A, now P260703-SCR-Rev B". Empty when it is up to date,
        or when no PS1 revision is issued yet."""
        issued = [r for r in self.project.reports.ps1.revisions if r.issued_at]
        if not issued:
            return []
        last, out = issued[-1], []
        scr, ds = self.scr_issued_id, self.drawing_set
        if scr and scr != last.cites_calculations:
            out.append(f"{last.cites_calculations}, now {scr}")
        if ds and ds.reference != last.cites_drawings:
            out.append(f"{last.cites_drawings}, now {ds.reference}")
        return out

    @property
    def firm_name(self) -> str:
        """The engineering firm as the PS1 names it: "Full Name (SHORT)"; "" if the portal sends none."""
        cert = self.project.ps1_certificate_data
        if not cert:
            return ""
        return f"{cert.issuer} ({cert.issuer_short_name})" if cert.issuer_short_name else cert.issuer

    @property
    def verification_methods(self) -> str:
        """The project's verification method / acceptable solution, else the firm default."""
        return self.project.reports.ps1.verification_methods or self.defaults.ps1.verification_methods

    @property
    def alternative_solution(self) -> bool:
        """Whether alternative solutions were adopted: the Structural Calculations
        Report's list is the one record of them, so the PS1 can't disagree."""
        return bool(self.project.reports.scr.alternative_solutions)

    @property
    def rbw_lines(self) -> list[RbwLine]:
        """The Certificate of Design Work's rows, in the form's order. A row applies
        when an element's type falls under it (the library's rbwRow)."""
        given = self.project.reports.ps1.rbw
        out = []
        for row in RBW_ROWS:
            applies = any(r.type and r.type.rbw_row == row for r in self.elements)
            entry = given.get(row)
            out.append(RbwLine(row, applies,
                               entry.description if entry and entry.description else self.rbw_library_description(row),
                               (entry.carried_out_or_supervised if entry and entry.carried_out_or_supervised
                                else self.defaults.ps1.carried_out_or_supervised)))
        return out

    def rbw_library_description(self, row: str) -> str | None:
        """The element library's description for a row: its types' texts, each once."""
        types = _unique(r.type for r in self.elements if r.type and r.type.rbw_row == row)
        return "; ".join(_unique(t.rbw_description for t in types if t.rbw_description)) or None

    def default_maintenance(self, interval: str) -> list[str]:
        """The element library's items for an interval, from the materials used."""
        return _unique(item for m in self.materials_used for item in getattr(m.maintenance, interval))

    @property
    def maintenance(self) -> dict[str, list[str]]:
        """The Structural Maintenance Schedule: label -> items (empty = "Not applicable.")."""
        edits = self.project.reports.ps1.maintenance_schedule
        return {label: (getattr(edits, key) if getattr(edits, key) is not None else self.default_maintenance(key))
                for key, label in MAINTENANCE_INTERVALS.items()}

    @property
    def has_maintenance_schedule(self) -> bool:
        """The schedule is included when any item is ticked: by default, the items
        mild steel and steel timber fixings bring."""
        return any(self.maintenance.values())

    @property
    def drawing_set(self) -> DrawingSet | None:
        """The architect's drawings as last reviewed: each completed review is a
        revision of the set. None until a review is completed."""
        reviews = sorted(self.project.drawing_reviews, key=lambda r: r.completed_at)
        if not reviews:
            return None
        return DrawingSet(f"{self.project.project_id}-DRG-Rev {revision_letter(len(reviews) - 1)}",
                          nz_date(reviews[-1].completed_at))

    @property
    def council(self) -> TerritorialAuthority | None:
        """The project's council (building consent authority) from the list; None
        if `territorialAuthority` is empty or not a listed name."""
        return self.councils.find(self.project.territorial_authority)

    @property
    def b2_addressee(self) -> list[str] | None:
        """The B2 letter's addressee block: the council's name and postal address."""
        c = self.council
        return [c.name, *c.postal_address] if c else None

    @property
    def site_information(self) -> dict[str, str | None]:
        s = self.project.structural
        return {"Wind zone": s.wind_zone, "Snow zone": s.snow_zone, "Snow elevation": s.snow_elevation,
                "ULS bearing": f"{s.uls_bearing} kPa" if s.uls_bearing else None}

    # --- problems ---------------------------------------------------------

    def issues(self) -> list[Issue]:
        p, out = self.project, []
        ids = [e.id for e in p.elements]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            out.append(Issue("error", "all", f"element id {dup} is used more than once"))
        if not p.elements:
            out.append(Issue("error", "all", "the project has no elements"))

        for r in self.elements:
            e = r.element
            if r.type is None:
                out.append(Issue("error", "all", f"element {e.id}: type {e.type!r} is not in the element library"))
            elif not r.type.scr_narrative:
                out.append(Issue("warning", "scr", f"element type {e.type} has no default report text (scrNarrative)"))
            for m in r.materials:
                if m.b2_details is None:
                    out.append(Issue("error", "ps1", f"element {e.id}: material {m.name!r} has no B2 letter text yet"))
                need = DURABILITY_FOR_MATERIAL.get(m.name)
                if need and getattr(p.durability, need) is None:
                    out.append(Issue("error", "scr",
                                     f"element {e.id} uses {m.name}, so durability.{_camel(need)} is required"))

        known = set(ids)
        out += self._ps1_issues()

        scr = p.reports.scr
        if scr.foundations is None:
            out.append(Issue("error", "scr", "the foundations inputs (general ground conditions, expansive soils, "
                                             "site soils class) have not been entered"))
        if p.internal_reviewing_engineer is None:
            out.append(Issue("error", "all", "the project has no reviewing engineer (internalReviewingEngineer), "
                                             "who prepares and reviews the report and signs the PS1"))
        elif not p.internal_reviewing_engineer.position:
            out.append(Issue("warning", "scr", "the reviewing engineer has no position "
                                               "(internalReviewingEngineer.position); it is left off the report"))
        if not scr.revisions:
            out.append(Issue("error", "scr", "the revision record is empty: add a revision (only its description "
                                             "is entered; the letter and date are automatic)"))
        if scr.revisions and scr.revisions[-1].issued_on and (changes := self.scr_out_of_date):
            out.append(Issue("warning", "scr", f"the issued SCR ({self.scr_last_issued_label}) cites drawings that have "
                                               f"since been revised ({'; '.join(changes)}): add an SCR revision"))
        if p.architect is None or not (p.architect.company_name or p.architect.name):
            out.append(Issue("warning", "scr", "the portal does not send the architect yet (basis of opinions)"))
        if not p.drawing_reviews:
            out.append(Issue("warning", "scr", "no drawing review has been completed, so the architect's drawings "
                                               "have no reference or date (basis of opinions)"))
        for e in p.elements:
            if not e.calculation_report_url:
                out.append(Issue("error", "scr", f"element {e.id} has no calculation report (calculationReportUrl)"))
        for element_id in scr.narratives:
            if element_id not in known:
                out.append(Issue("warning", "scr", f"a narrative is given for element {element_id}, "
                                                   "which is not in the project"))
        ta = p.territorial_authority
        if not ta:
            out.append(Issue("error", "all", "the project has no council (territorialAuthority)"))
        elif self.council is None:
            hints = " or ".join(repr(h) for h in self.councils.suggestions(ta))
            out.append(Issue("error", "all", f"the council {ta!r} is not in the list of territorial authorities "
                                             "(data/territorial_authorities.json)"
                                             + (f"; did you mean {hints}?" if hints else "")))
        cert = p.ps1_certificate_data
        if cert is None:
            out.append(Issue("error", "all", "the portal sends no engineering firm (ps1CertificateData.issuer)"))
        elif not cert.issuer_short_name:
            out.append(Issue("warning", "all", "the portal does not send the firm's short name "
                                               "(ps1CertificateData.issuerShortName) yet; the full name is repeated"))
        return out

    def _ps1_issues(self) -> list[Issue]:
        p, ps1, out = self.project, self.project.reports.ps1, []
        for line in self.rbw_lines:
            if line.applies and not line.description:
                out.append(Issue("error", "ps1", f"Certificate of Design Work, {line.row}: no description "
                                                 "(none in the element library either)"))
            if line.applies and not line.carried_out_or_supervised:
                out.append(Issue("error", "ps1", f"Certificate of Design Work, {line.row}: choose "
                                                 "Carried out or Supervised"))
            if not line.applies and line.row in ps1.rbw:
                out.append(Issue("warning", "ps1", f"Certificate of Design Work, {line.row}: entries are given, but "
                                                   "no element falls under this row, so it prints \"Not applicable\""))
        for r in self.elements:
            if r.type and r.type.rbw_row is None:
                out.append(Issue("warning", "ps1", f"element type {r.type.code} has no Certificate of Design Work "
                                                   "row in the element library (rbwRow)"))
        eng = p.internal_reviewing_engineer
        if eng:
            missing = [label for label, value in (
                ("chartered status", eng.chartered_status), ("CPEng number", eng.cpeng_number),
                ("qualifications", eng.qualifications), ("mobile", eng.mobile),
                ("signature", eng.signature_url)) if not value]
            if missing:
                out.append(Issue("warning", "ps1", "the portal does not send the reviewing engineer's "
                                                   f"{', '.join(missing)} yet (internalReviewingEngineer)"))
        cert = p.ps1_certificate_data
        if cert:
            missing = [label for label, value in (
                ("postal address", cert.issuer_postal_address), ("physical address", cert.issuer_address),
                ("daytime phone", cert.issuer_phone), ("after-hours phone", cert.issuer_phone_after_hours),
                ("website", cert.issuer_website), ("PI insurance", cert.issuer_pi_insurance_nzd),
                ("ACE NZ membership", cert.issuer_ace_nz_member is not None)) if not value]
            if missing:
                out.append(Issue("warning", "ps1", f"the portal does not send the firm's {', '.join(missing)} yet "
                                                   "(ps1CertificateData)"))
        revisions = p.reports.scr.revisions
        if revisions and not revisions[-1].issued_on:
            out.append(Issue("warning", "ps1", "the PS1 cites the Structural Calculations Report's Rev "
                                               f"{revision_letter(len(revisions) - 1)}, which is not issued yet; issue it "
                                               "before the PS1"))
        if not p.drawing_reviews:
            out.append(Issue("warning", "ps1", "the PS1 cites the drawing set, which has no completed review yet; "
                                               "complete it before issuing the PS1"))
        if not ps1.revisions:
            out.append(Issue("error", "ps1", "the PS1 has no revision: add one (only its description is typed; the "
                                             "letter and the issue date are automatic)"))
        elif self.ps1_issued_at and (changes := self.ps1_out_of_date):
            out.append(Issue("warning", "ps1", f"the issued PS1 ({self.ps1_last_issued_label}) cites documents that "
                                               f"have since been revised ({'; '.join(changes)}): add a PS1 revision"))
        if not self.has_maintenance_schedule:
            out.append(Issue("warning", "ps1", "the Structural Maintenance Schedule is left out: no items are ticked "
                                               "(no mild steel or steel timber fixings, and none added)"))
        if not (p.site_street_address and p.site_town_city):
            out.append(Issue("warning", "ps1", "the portal does not send the site address in parts yet (street, "
                                               "suburb, town/city, postcode) for the Certificate of Design Work"))
        return out


def _unique(items):
    seen, out = [], []
    for i in items:
        if i not in seen:
            seen.append(i)
            out.append(i)
    return out


def _camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(w.title() for w in rest)
