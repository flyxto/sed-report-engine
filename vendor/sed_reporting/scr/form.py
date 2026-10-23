"""What an edit form for the Structural Calculations Report needs to know,
worked out on the server so no front end has to re-implement it:

    documentId      the derived document ID ("P260703-SCR-Rev A"), shown read-only
    revisions       per revision: its letter, its date as printed, and whether it
                    is issued (issued ones are locked; only a draft's description
                    can be edited)
    nextRevision    the letter a new revision would get
    outOfDate       what the latest issued revision cites that has since been
                    revised ("P260703-DRG-Rev A, now P260703-DRG-Rev B"); a new
                    revision is needed when this isn't empty
    basisOfOpinions the "Opinions given in this report are based on" items as
                    printed, all from the portal, shown read-only
    engineer        "Name, Position" of the engineer who prepares and reviews
                    the report (the portal's reviewing engineer), read-only
    designItems     the elements in report order (one section each): id, section
                    title, and the library narrative the edit box starts from
    defaults        the firm's live loads and barrier loads
    hasBarrier      whether the barrier loads section applies
    durabilityNeeded  which durability blocks the elements' materials call for
    choices         the allowed values of every choice field, read from the
                    models themselves so they can never drift from validation

Returned by POST /scr/preview alongside the HTML and the issues.
"""

from __future__ import annotations

import types
import typing

from pydantic import BaseModel

from sed_reporting.scr.document import (
    basis_of_opinions, design_item_title, document_id, long_date, person_label, report_date, revision_letter,
)
from sed_reporting.project_data import ProjectData
from sed_reporting.project_data.project import ConcreteDurability, ScrInputs, FoundationsInputs, SteelDurability, SteelFixings


def _choices(model: type[BaseModel], field: str) -> list:
    """The values a Literal field (possibly Optional, or a list of them) accepts."""
    annotation = model.model_fields[field].annotation
    if isinstance(annotation, types.UnionType) or typing.get_origin(annotation) is typing.Union:
        annotation = next(a for a in typing.get_args(annotation) if a is not type(None))
    if typing.get_origin(annotation) is list:
        annotation = typing.get_args(annotation)[0]
    return list(typing.get_args(annotation))


def _camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(w.title() for w in rest)


def form_context(pd: ProjectData) -> dict:
    d = pd.defaults.live_loads
    revisions, day = pd.project.reports.scr.revisions, report_date(pd)
    return {
        "documentId": document_id(pd),     # derived, shown read-only; None until a revision exists
        "revisions": [{"revision": revision_letter(i), "date": long_date(r.issued_on or day),
                       "issued": r.issued_on is not None} for i, r in enumerate(revisions)],
        "nextRevision": revision_letter(len(revisions)),
        "outOfDate": pd.scr_out_of_date,
        "basisOfOpinions": basis_of_opinions(pd),
        "engineer": person_label(pd.project.internal_reviewing_engineer) or None,   # from the portal, read-only
        "designItems": [
            {"id": r.element.id, "title": f"4.{n} {design_item_title(r)}",
             "defaultNarrative": pd.default_narrative(r.element.id)}
            for n, r in enumerate(pd.design_items, start=1)
        ],
        "defaults": {
            "liveLoads": [l.model_dump(by_alias=True, exclude_none=True) for l in d.residential],
            "barrierLoads": d.barriers.model_dump(by_alias=True),
        },
        "hasBarrier": pd.has_barrier,
        "durabilityNeeded": [_camel(n) for n in pd.durability_needed],
        "choices": {
            "importanceLevel": _choices(ScrInputs, "importance_level"),
            "groundConditions": _choices(FoundationsInputs, "ground_conditions"),
            "siteSoilsClass": _choices(FoundationsInputs, "site_soils_class"),
            "steelFixingsExposureZone": _choices(SteelFixings, "exposure_zone"),
            "concreteExposureClassification": _choices(ConcreteDurability, "exposure_classification"),
            "steelMacroclimateCategory": _choices(SteelDurability, "macroclimate_category"),
            "steelConstructionCategory": _choices(SteelDurability, "construction_category"),
        },
    }
