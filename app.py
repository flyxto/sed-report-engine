"""HTTP service the Node backend calls.

    GET  /health
    POST /v1/reports/{kind}/preview     JSON  { html, issues, form, notes }
    POST /v1/reports/{kind}/pdf         PDF
    POST /v1/reports/{kind}/issue       PDF   (signed; PS1, SIR, RFI, PS4)

`kind` is scr, ps1, sir, rfi or ps4. SIR and RFI also take `?number=1`.

Body:

    { "project": { ...the portal project, including elements... } }

Set REPORT_ENGINE_SECRET and send it as `X-Report-Engine-Secret`. When the
variable is unset, local calls are accepted.

Run from the folder that contains `reporting`, `sed_reporting` and this
package (the parent must be on PYTHONPATH):

    uvicorn sed_report_engine.app:app --app-dir .. --port 8010
"""

from __future__ import annotations

import os

import base64

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from reporting import ReportManifest, read_manifest, stamp_manifest
from sed_report_engine import __version__
from sed_report_engine.errors import EngineError
from sed_report_engine.generate import Pdf, Preview, generate

app = FastAPI(title="sed report engine", version=__version__)


class GenerateBody(BaseModel):
    project: dict = Field(..., description="Portal project, including elements.")


class StampBody(BaseModel):
    pdfBase64: str
    id: str
    module: str
    elementType: str
    title: str
    reference: str = ""


class FillReferenceBody(BaseModel):
    pdfBase64: str
    reference: str


def require_secret(x_report_engine_secret: str | None = Header(default=None)) -> None:
    expected = os.environ.get("REPORT_ENGINE_SECRET", "").strip()
    if expected and x_report_engine_secret != expected:
        raise HTTPException(status_code=401, detail="report engine secret is missing or wrong")


@app.post("/v1/stamp")
def stamp_pdf(body: StampBody, _: None = Depends(require_secret)) -> Response:
    """Write the calculation stamp onto an element PDF from an external engine."""
    try:
        raw = base64.b64decode(body.pdfBase64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="pdfBase64 is not valid base64") from exc
    stamped = stamp_manifest(
        raw,
        ReportManifest(
            id=body.id,
            module=body.module,
            element_type=body.elementType,
            title=body.title,
            reference=body.reference,
        ),
    )
    return Response(stamped, media_type="application/pdf")


@app.post("/v1/fill-reference")
def fill_reference(body: FillReferenceBody, _: None = Depends(require_secret)) -> Response:
    """Put the section mark into a stamped calculation PDF that left reference blank."""
    try:
        raw = base64.b64decode(body.pdfBase64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="pdfBase64 is not valid base64") from exc
    current = read_manifest(raw)
    if not isinstance(current, dict) or not current.get("title"):
        raise HTTPException(status_code=400, detail="the calculation PDF has no stamp to add a reference to")
    if str(current.get("reference") or "").strip():
        return Response(raw, media_type="application/pdf")
    stamped = stamp_manifest(
        raw,
        ReportManifest(
            id=str(current.get("id") or ""),
            module=str(current.get("module") or ""),
            element_type=str(current.get("element_type") or ""),
            title=str(current["title"]),
            reference=body.reference,
        ),
    )
    return Response(stamped, media_type="application/pdf")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sed_report_engine", "version": __version__}


@app.post("/v1/reports/{kind}/{action}")
def run_report(
    kind: str,
    action: str,
    body: GenerateBody,
    number: int | None = None,
    _: None = Depends(require_secret),
):
    try:
        result = generate(kind, action, body.project, number)
    except EngineError as exc:
        return JSONResponse(
            status_code=exc.status,
            content={"message": exc.message, "issues": exc.issues},
        )

    if isinstance(result, Preview):
        return {
            "html": result.html,
            "issues": result.issues,
            "form": result.form,
            "notes": result.notes,
        }
    assert isinstance(result, Pdf)
    return Response(result.body, media_type=result.media_type, headers=result.headers)
