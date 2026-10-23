"""What an edit form for an RFI response needs to know, worked out on the server:

    rounds          every RFI round on the project: number, label (RFI01), the
                    date it was raised (the NZ date the architect sent it),
                    submitted or not
    nextNumber      the number a new round would get
    issuedAt        this round's moment of submission, or None; once submitted
                    it is locked
    receivedAt      when the architect sent this round's questions
    documents       what an answer can cite, at the current revisions: the
                    drawing set (and whether a review was completed since the
                    questions were received), the SCR (its revision, whether
                    issued, and whether one was issued since), the PS1 (its
                    latest revision, issued or not, and what the issued one
                    cites that has since been revised: then a new PS1 revision
                    is needed before submitting)
    addressee       the council's name and postal address, as printed
    consentNumber, reviewingEngineer, firm   from the portal, shown read-only

Returned by POST /rfi/preview alongside the HTML and the issues.
"""

from __future__ import annotations

from sed_reporting.project_data import ProjectData
from sed_reporting.project_data.dates import nz_date
from sed_reporting.project_data.resolve import revision_letter
from sed_reporting.rfi.document import rfi_tag
from sed_reporting.scr.document import document_id


def form_context(pd: ProjectData, number: int) -> dict:
    p, r = pd.project, pd.rfi_round(number)
    rounds = p.reports.rfi.rounds
    scr = p.reports.scr.revisions
    ds = pd.drawing_set
    return {
        "rounds": [{"number": x.number, "label": rfi_tag(x.number), "raisedOn": x.raised_on.isoformat(),
                    "issued": x.issued_at is not None} for x in sorted(rounds, key=lambda x: x.number)],
        "nextNumber": max((x.number for x in rounds), default=0) + 1,
        "issuedAt": r.issued_at.isoformat() if r and r.issued_at else None,
        "receivedAt": r.received_at.isoformat() if r else None,
        "documents": {
            "drawings": {"reference": ds.reference if ds else None,
                         "revisedSinceReceived": bool(r) and any(d.completed_at > r.received_at
                                                                 for d in p.drawing_reviews)},
            "calculations": {"reference": document_id(pd),
                             "issued": bool(scr) and scr[-1].issued_on is not None,
                             "revisedSinceReceived": bool(r) and bool(scr) and scr[-1].issued_on is not None
                                                     and scr[-1].issued_on >= nz_date(r.received_at),
                             "draftRevision": (f"Rev {revision_letter(len(scr) - 1)}"
                                               if scr and scr[-1].issued_on is None else None)},
            "ps1": {"reference": pd.ps1_document_id, "issued": pd.ps1_issued_at is not None,
                    "revisedSinceReceived": bool(r) and any(x.issued_at and x.issued_at > r.received_at
                                                            for x in p.reports.ps1.revisions),
                    "outOfDate": pd.ps1_out_of_date},
        },
        "addressee": pd.b2_addressee,
        "consentNumber": p.building_consent_number or None,
        "reviewingEngineer": p.internal_reviewing_engineer.name if p.internal_reviewing_engineer else None,
        "firm": pd.firm_name or None,
    }
