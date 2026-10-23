"""What an edit form for the PS4 needs to know, worked out on the server:

    issuedAt        when the PS4's latest revision was issued, or None; once
                    issued it is locked until a revision is added
    documentId      "P260703-PS4-Rev A" (the latest revision), or None
    revisions       the revision record: letter, description, issued or not, when
    nextRevision    the letter a new revision would get
    outOfDate       what the issued revision covers that has since changed (a new
                    PS1 revision, SIRs issued since); a new revision is needed
    checklist       each checklist item: done or not, and for a library
                    inspection the elements still to cover
    sirs            every SIR: number, issued, whether the portal stored its PDF
    attachments     what the package attaches, in order, as the Schedule lists it
    ps3Required     whether a PS3 is needed (an element uses mild steel)
    recordOfWorkRequired   the engineer's choice (default yes)
    ps1             the PS1 it covers: its latest issued revision, out of date or not
    consentNumber, consentAmendments, firm, engineer   from the portal, read-only

Returned by POST /ps4/preview alongside the HTML and the issues.
"""

from __future__ import annotations

from sed_reporting.project_data import ProjectData
from sed_reporting.project_data.resolve import revision_letter
from sed_reporting.ps4.document import attachments


def form_context(pd: ProjectData) -> dict:
    p, ps4 = pd.project, pd.project.reports.ps4
    eng = p.internal_reviewing_engineer
    return {
        "issuedAt": pd.ps4_issued_at.isoformat() if pd.ps4_issued_at else None,
        "documentId": pd.ps4_document_id,
        "revisions": [{"revision": revision_letter(i), "description": r.description, "issued": r.issued_at is not None,
                       "issuedAt": r.issued_at.isoformat() if r.issued_at else None}
                      for i, r in enumerate(ps4.revisions)],
        "nextRevision": revision_letter(len(ps4.revisions)),
        "outOfDate": pd.ps4_out_of_date,
        "checklist": [{"item": c.inspection.item, "onSite": c.inspection.on_site, "done": c.done,
                       "notCovered": [pd.element_label(e) for e in c.elements if e not in c.covered]}
                      for c in pd.checklist_status],
        "sirs": [{"number": v.number, "label": pd.sir_id(v.number), "issued": v.issued_at is not None,
                  "pdfStored": bool(v.pdf_url)} for v in sorted(p.reports.sir.visits, key=lambda v: v.number)],
        "attachments": [label for label, _url in attachments(pd)],
        "ps3Required": pd.ps3_required,
        "recordOfWorkRequired": ps4.record_of_work_required,
        "ps1": {"reference": pd.ps1_issued_id, "outOfDate": pd.ps1_out_of_date},
        "consentNumber": p.building_consent_number or None,
        "consentAmendments": p.building_consent_amendments,
        "firm": pd.firm_name or None,
        "engineer": eng.name if eng else None,
    }
