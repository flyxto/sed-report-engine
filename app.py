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

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from sed_report_engine import __version__
from sed_report_engine.errors import EngineError
from sed_report_engine.generate import Pdf, Preview, generate

app = FastAPI(title="sed report engine", version=__version__)


class GenerateBody(BaseModel):
    project: dict = Field(..., description="Portal project, including elements.")


def require_secret(x_report_engine_secret: str | None = Header(default=None)) -> None:
    expected = os.environ.get("REPORT_ENGINE_SECRET", "").strip()
    if expected and x_report_engine_secret != expected:
        raise HTTPException(status_code=401, detail="report engine secret is missing or wrong")


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
