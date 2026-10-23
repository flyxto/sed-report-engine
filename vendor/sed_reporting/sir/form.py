"""What an edit form for a SIR needs to know, worked out on the server:

    visits          every SIR on the project: number, label (SIR01), inspection
                    date, issued or not
    nextNumber      the number a new SIR would get
    issuedAt        this SIR's moment of issue, or None; once issued it is locked
    checklist       the project's inspections (the PS1's Construction Monitoring
                    Schedule plus those added on the project): item, timeframe,
                    monitored by, onSite (False = an office check, marked complete
                    rather than inspected), the standard observations a new item
                    starts from, the issued SIRs that covered it, the elements it
                    applies to (each with whether an issued SIR has covered it),
                    whether it is done, and for an office check the day it was
                    marked complete
    observationStates  this SIR's observations by id: their state on the failure
                    path (state, and a label to show)
    standardActions the standard actions to tick ("{council}" filled in for display)
    drawingSet      the reviewed drawing set's reference, printed before the sheets
    inspectionEngineer, firm   from the portal, shown read-only

Returned by POST /sir/preview alongside the HTML and the issues.
"""

from __future__ import annotations

from sed_reporting.project_data import ProjectData, load_sir_actions
from sed_reporting.project_data.resolve import OBSERVATION_STATES, observation_state
from sed_reporting.sir.document import action_text, sir_tag


def form_context(pd: ProjectData, number: int) -> dict:
    p, v = pd.project, pd.visit(number)
    visits = p.reports.sir.visits
    return {
        "visits": [{"number": x.number, "label": sir_tag(x.number),
                    "inspectionDate": x.inspection_date.isoformat() if x.inspection_date else None,
                    "issued": x.issued_at is not None} for x in sorted(visits, key=lambda x: x.number)],
        "nextNumber": max((x.number for x in visits), default=0) + 1,
        "issuedAt": v.issued_at.isoformat() if v and v.issued_at else None,
        "checklist": [{"item": c.inspection.item, "timeframe": c.inspection.timeframe,
                       "monitoredBy": c.inspection.monitored_by, "onSite": c.inspection.on_site,
                       "observations": c.inspection.observations, "doneIn": [sir_tag(n) for n in c.sir_numbers],
                       "completedOn": c.completed_on.isoformat() if c.completed_on else None, "done": c.done,
                       "elements": [{"id": e, "label": pd.element_label(e), "covered": e in c.covered}
                                    for e in c.elements]}
                      for c in pd.checklist_status],
        "observationStates": {o.id: {"state": observation_state(o), "label": OBSERVATION_STATES[observation_state(o)]}
                              for it in (v.items if v else []) for o in it.observations},
        "standardActions": [{"text": a, "display": action_text(pd, a)} for a in load_sir_actions().actions],
        "drawingSet": pd.drawing_set.reference if pd.drawing_set else None,
        "inspectionEngineer": p.inspection_engineer.name if p.inspection_engineer else None,
        "firm": pd.firm_name or None,
    }
