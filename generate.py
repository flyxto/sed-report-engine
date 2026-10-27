"""Generate a portal report from a project payload.

Preview returns HTML plus the issues list (errors block the PDF; warnings
do not). `pdf` and `issue` return the PDF bytes and the stamp headers
`sed_reporting` already sets (`X-Document-Id`, `X-Issued-At`, `X-Cites-*`).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import ValidationError

from sed_report_engine.draft import draft_pdf
from sed_report_engine.errors import EngineError
from sed_report_engine.mapper import to_project
from sed_reporting.project_data.project import Project
from sed_reporting.scr.build import fetch_url
from sed_reporting.api import (
    ps1_issue,
    ps1_pdf,
    ps1_preview,
    ps4_issue,
    ps4_pdf,
    ps4_preview,
    rfi_issue,
    rfi_pdf,
    rfi_preview,
    scr_pdf,
    scr_preview,
    sir_issue,
    sir_pdf,
    sir_preview,
)

NUMBERED = {"sir", "rfi"}
KIND_ACTIONS = {
    "scr": {"preview": scr_preview, "pdf": scr_pdf},
    "ps1": {"preview": ps1_preview, "pdf": ps1_pdf, "issue": ps1_issue},
    "sir": {"preview": sir_preview, "pdf": sir_pdf, "issue": sir_issue},
    "rfi": {"preview": rfi_preview, "pdf": rfi_pdf, "issue": rfi_issue},
    "ps4": {"preview": ps4_preview, "pdf": ps4_pdf, "issue": ps4_issue},
}


@dataclass
class Preview:
    html: str
    issues: list[dict]
    form: dict
    notes: list[str]


@dataclass
class Pdf:
    body: bytes
    media_type: str
    headers: dict[str, str]
    notes: list[str]


def load_project(payload: dict) -> tuple[Project, list[str]]:
    """Map and validate. Raises EngineError (422) when the details cannot be used."""
    mapped, notes = to_project(payload)
    try:
        project = Project.model_validate(mapped)
    except ValidationError as exc:
        issues = [
            {
                "severity": "error",
                "report": "all",
                "message": f"{_loc(err['loc'])}: {err['msg']}",
            }
            for err in exc.errors()
        ]
        raise EngineError(422, "Project details do not match the report contract.", issues) from exc
    return project, notes


def generate(kind: str, action: str, payload: dict, number: int | None = None) -> Preview | Pdf:
    actions = KIND_ACTIONS.get(kind)
    if actions is None:
        raise EngineError(404, f"Unknown report '{kind}'. Use one of: {', '.join(KIND_ACTIONS)}.")
    handler = actions.get(action)
    if handler is None:
        raise EngineError(404, f"'{kind}' has no '{action}' action. Available: {', '.join(actions)}.")
    if kind in NUMBERED and not number:
        raise EngineError(422, f"{kind.upper()} needs a number, for example number=1 for {kind.upper()}01.")

    project, notes = load_project(payload)
    try:
        result = _call(kind, action, handler, project, number)
    except HTTPException as exc:
        if action == "pdf" and exc.status_code == 422 and isinstance(exc.detail, dict):
            body = draft_pdf(kind, project)
            if body:
                notes = [
                    *notes,
                    "Draft PDF. Items still marked [not entered] have to be filled in before this report can be issued.",
                ]
                return Pdf(body=body, media_type="application/pdf", headers={"X-Report-Draft": "true"}, notes=notes)
        raise _from_http(exc) from exc

    if action == "preview":
        issues = [
            issue
            for issue in (result.get("issues") or [])
            if issue.get("report") in (kind, "all", None)
        ]
        return Preview(
            html=result.get("html") or "",
            issues=issues,
            form=result.get("form") or {},
            notes=[note for note in notes if "sent to the report as" not in note],
        )

    headers = {key: value for key, value in result.headers.items() if key.lower().startswith("x-") or key.lower() == "content-disposition"}
    return Pdf(body=result.body, media_type="application/pdf", headers=headers, notes=notes)


def _call(kind: str, action: str, handler, project: Project, number: int | None):
    """Match each sed_reporting endpoint. A draft PS1 PDF takes no fetch."""
    if action == "preview":
        return handler(project, number) if kind in NUMBERED else handler(project)
    if kind in NUMBERED:
        return handler(project, number, fetch_url)
    if kind == "ps1" and action == "pdf":
        return handler(project)
    return handler(project, fetch_url)


def _from_http(exc: HTTPException) -> EngineError:
    detail = exc.detail
    if isinstance(detail, dict):
        return EngineError(
            exc.status_code,
            str(detail.get("message") or "The report could not be generated."),
            detail.get("issues") or [],
        )
    return EngineError(exc.status_code, str(detail))


def _loc(loc: tuple) -> str:
    parts = [str(part) for part in loc if part != "body"]
    return ".".join(parts) or "project"
