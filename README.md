# sed report engine

Connects the sed.works portal to the two client packages:

- `reporting` draws one element calculation as HTML and as a stamped PDF
- `sed_reporting` turns a whole project into the SCR, PS1, SIR, RFI and PS4

This service does the step those packages do not: it takes the project JSON
the Node backend already stores, maps element names and addresses into the
shape `sed_reporting` validates, and returns the preview or the PDF.

The frontend never calls this process directly. It calls the Node API, which
loads the project (after the normal access check) and posts it here.

```
frontend  →  POST /api/v1/projects/:id/reports/scr/preview
backend   →  POST /v1/reports/scr/preview   { "project": { ... } }
engine    →  sed_reporting
```

## Run it locally

From the `sed` folder (the parent of `reporting`, `sed_reporting` and this package):

```bash
sed_reporting/.venv/bin/pip install -r sed_report_engine/requirements.txt
PYTHONPATH=. sed_reporting/.venv/bin/uvicorn sed_report_engine.app:app --port 8010
```

`GET http://127.0.0.1:8010/health`

Set `REPORT_ENGINE_URL=http://127.0.0.1:8010` on the Node backend. Set
`REPORT_ENGINE_SECRET` on both sides when this port is not only on localhost;
the backend sends it as `X-Report-Engine-Secret`.

## Reports

| kind | actions | number |
|------|---------|--------|
| `scr` | preview, pdf | |
| `ps1` | preview, pdf, issue | |
| `sir` | preview, pdf, issue | `?number=1` |
| `rfi` | preview, pdf, issue | `?number=1` |
| `ps4` | preview, pdf, issue | |

`preview` returns `{ html, issues, form, notes }`. An issue with
`"severity": "error"` is why the PDF is refused. `notes` lists details the
mapper translated or left out (for example a portal element type sent as
`PF2`).

`pdf` and `issue` return `application/pdf`. Issue headers (`X-Issued-At`,
`X-Document-Id`, `X-Cites-*`) are the stamps the portal stores on that revision.
