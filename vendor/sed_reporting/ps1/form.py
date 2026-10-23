"""What an edit form for the PS1 package needs to know, worked out on the server
so no front end has to re-implement it:

    issuedAt        when the PS1's latest revision was issued (ISO), or None; once
                    issued the PS1 is locked until a revision is added
    documentId      "P260703-PS1-Rev B" (the latest revision), or None
    revisions       the revision record: letter, description, issued or not, when
    nextRevision    the letter a new revision would get
    outOfDate       what the latest issued revision cites that has since been
                    revised ("P260703-SCR-Rev A, now P260703-SCR-Rev B"); a new
                    revision is needed when this isn't empty
    firm, engineer  from the portal, shown read-only
    scope           the "SED …" labels, from the element categories
    alternativeSolution  whether alternative solutions were adopted (from the
                    Structural Calculations Report), shown read-only
    rbw             the Certificate of Design Work's rows: whether each applies,
                    the element library's description (what the box starts from),
                    and the engineer's entries
    maintenance     per interval: its label, the standard items to tick (`options`,
                    from data/maintenance_items.json), and the ones pre-ticked for the
                    materials used (`library`)
    documents       the attachments that can be left out (the Structural
                    Maintenance Schedule is included when any item is ticked)
    hasMaintenanceSchedule  whether it is, now
    cmLevels        CM1–CM5: each level's review and where it is appropriate
                    (data/cm_levels.json), shown under the choice of level
    defaults        the firm defaults the boxes start from (verification method,
                    carried out or supervised)
    choices         the allowed values of every choice field, read from the
                    models so they can never drift from validation

Returned by POST /ps1/preview alongside the HTML and the issues.
"""

from __future__ import annotations

from sed_reporting.project_data import ProjectData, load_cm_levels
from sed_reporting.project_data.project import MAINTENANCE_INTERVALS, Ps1Inputs, RbwRowInput
from sed_reporting.project_data.resolve import revision_letter
from sed_reporting.ps1.document import DOCUMENT_LABELS
from sed_reporting.scr.form import _camel, _choices


def form_context(pd: ProjectData) -> dict:
    p, ps1 = pd.project, pd.project.reports.ps1
    eng = p.internal_reviewing_engineer
    return {
        "issuedAt": pd.ps1_issued_at.isoformat() if pd.ps1_issued_at else None,
        "documentId": pd.ps1_document_id,
        "revisions": [{"revision": revision_letter(i), "description": r.description, "issued": r.issued_at is not None,
                       "issuedAt": r.issued_at.isoformat() if r.issued_at else None}
                      for i, r in enumerate(ps1.revisions)],
        "nextRevision": revision_letter(len(ps1.revisions)),
        "outOfDate": pd.ps1_out_of_date,
        "firm": pd.firm_name or None,
        "engineer": eng.name if eng else None,
        "engineerProfile": {
            "position": eng.position,
            "charteredStatus": eng.chartered_status,
            "cpengNumber": eng.cpeng_number,
            "qualifications": list(eng.qualifications or []),
            "mobile": eng.mobile,
            "signatureUrl": eng.signature_url,
        } if eng else None,
        "council": pd.council.name if pd.council else None,
        "scope": pd.scope_labels,
        "alternativeSolution": pd.alternative_solution,
        "rbw": [{"row": l.row, "applies": l.applies, "libraryDescription": pd.rbw_library_description(l.row),
                 "description": l.description, "carriedOutOrSupervised": l.carried_out_or_supervised}
                for l in pd.rbw_lines],
        "maintenance": [{"key": _camel(key), "label": label, "options": getattr(pd.maintenance_items, key),
                         "library": pd.default_maintenance(key)}
                        for key, label in MAINTENANCE_INTERVALS.items()],
        "documents": [{"key": _camel(key), "label": label} for key, label in DOCUMENT_LABELS.items()],
        "hasMaintenanceSchedule": pd.has_maintenance_schedule,
        "cmLevels": [{"level": x.level, "review": x.review, "comment": x.comment} for x in load_cm_levels().levels],
        "defaults": {"verificationMethods": pd.defaults.ps1.verification_methods,
                     "carriedOutOrSupervised": pd.defaults.ps1.carried_out_or_supervised},
        "choices": {
            "codeClauses": _choices(Ps1Inputs, "code_clauses"),
            "extent": _choices(Ps1Inputs, "extent"),
            "constructionMonitoringLevel": _choices(Ps1Inputs, "construction_monitoring_level"),
            "liabilityCapNzd": _choices(Ps1Inputs, "liability_cap_nzd"),
            "carriedOutOrSupervised": _choices(RbwRowInput, "carried_out_or_supervised"),
        },
    }
