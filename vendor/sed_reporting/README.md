# sed_reporting

The reporting service for the sed.works portal. From a project's data it
produces the **Structural Calculations Report (SCR)**, the **PS1 package**,
**Site Inspection Reports (SIR)**, **responses to council RFIs** and the **PS4
package**: previews for review, draft PDFs, and signed, locked PDFs on issue. A
Python library with a thin FastAPI service on top. What the portal must send,
store and do is in [docs/portal_data_requests.md](docs/portal_data_requests.md);
the agreed decisions per report are in
[docs/report_requirements.md](docs/report_requirements.md).

Underneath, it assembles **element report PDFs** into **one combined report**
(the SCR's Appendix A): contents page(s), every element in order, bookmarks,
and uniform "Page X of Y".

```
beams / pf / rafts / …                      sed_reporting
  reporting.render_report(…)           ──►   read + validate each element
  (renders and stamps the element PDF)       contents page(s) (rendered with `reporting`)
                                             merge, bookmarks, "Page X of Y"
```

Design modules render their own element PDFs; their report recipes and analysis
dependencies stay with them. This package never imports analysis code.

## The element contract

Each element PDF must carry the **stamp** that `reporting.render_report` writes.
The assembler reads:

| From the PDF | Used for | If missing |
|---|---|---|
| the stamp | proof the PDF came through the module's render path | rejected |
| its title | the contents-row label and the element's bookmark | rejected |
| its reference | the Ref column | shown as "—" |
| page tree | start-page offsets | — |
| outline | section bookmarks (opt-in, see Known limits) | ignored |

The stamp is written twice. The identity is read from the attached
`manifest.json`, the exact copy. `/Title` and `/Keywords` (`ref=…; module=…;
type=…`) are the fallback, for a PDF whose attachment was stripped by later
processing. The keywords can't hold a `;` inside a value, so "B12; rev C" would
come back as "B12"; that's why the attachment comes first. An unstamped
`reporting` PDF still has a `/Title`, because ReportLab copies `DocMeta.title`,
so without the attachment all three keyword keys must be present.

The stamp also carries the element type, but the assembler doesn't use it:
the title and reference identify each row.

Elements are expected to use `reporting`'s standard margins. The page number is
drawn opposite the element's left footer, on the same baseline.

## Library

```python
from sed_reporting import ReportMeta, assemble

pdf = assemble(
    [beam_pdf, raft_pdf],                                   # report order
    ReportMeta("House 3 — Structural Calculations", reference="SED-2026-H3",
               engineer="A. Engineer", date="2026-10-09"),
    names=["Beam B12", "Raft R3"],                          # for error messages
)
```

`assemble` raises `ElementError` (a `ValueError`) naming the first element that
breaks the contract; nothing is produced from a partly valid set. It also
refuses to finish if any contents-page number would disagree with where the
element actually lands.

On the module side, an element PDF comes from `render_report`, with the provider
carrying a manifest builder:

```python
provider = reporting.ReportProvider(
    key="beams",
    views={...},
    manifest=lambda m: reporting.ReportManifest(
        id=f"beams-{m.reference}", module="beams", element_type="beam",
        title=f"Beam {m.reference} — Design Check",   # names the element: it is the contents-row label
        reference=m.reference),
)
element_pdf = reporting.render_report(provider, results, "pdf")   # rendered and stamped
```

## HTTP service

```
GET  /health                     -> {"status": "ok", "pdfFont": …}
POST /assemble                   -> application/pdf (below)
POST /scr/preview | /scr/pdf     -> the SCR
POST /ps1/preview | /ps1/pdf | /ps1/issue
POST /sir/preview | /sir/pdf | /sir/issue   ?number=N
POST /rfi/preview | /rfi/pdf | /rfi/issue   ?number=N
POST /ps4/preview | /ps4/pdf | /ps4/issue
```

Each `preview` returns `{"html", "issues", "form"}`; `pdf` a draft; `issue` the
signed, locked PDF with its stamps in response headers (`X-Issued-At`,
`X-Document-Id`, `X-Cites-…`). Details in api.py's docstring and
docs/portal_data_requests.md, section 1. `/assemble` takes:

```jsonc
{
  "title": "House 3 — Structural Calculations",   // required
  "reference": "SED-2026-H3",                     // optional: also site_address, engineer, date
  "filename": "house3",                           // download name; .pdf added
  "elements": [{"name": "Beam B12", "pdf_base64": "JVBERi0…"}]   // report order, ≥ 1
}
```

A bad element (not base64, not a PDF, not stamped) is a `422` whose detail names
it. Non-ASCII download names (e.g. macrons) are sent with an ASCII fallback plus
RFC 6266 `filename*`.

## Element library

[data/element_library.json](data/element_library.json) is the firm-wide list of design
element types, shared by every project. It grows over time. Defining a type
defines its material.

- **`elementTypes`:** each type has a `code` (e.g. `PF1`), `name`, `category`
  (`Portal Frames`, `Beams`, `Foundations`, …), `materials` (every material the
  type has, e.g. TB1 `["Structural timber", "Steel timber fixings"]`, a masonry
  retaining wall `["Reinforced masonry", "Reinforced concrete"]`), `standards`
  and `inspections`
  (each an `item`, a `timeframe` and who it is `monitoredBy`; together these
  are the Construction Monitoring Schedule's rows), and `scrNarrative`: the
  default text for that type's section in the Structural Calculations Report,
  which the engineer edits per project (`null` until written).
  A project's elements refer to a type by its `code`.
- **To add a type,** add an entry. Codes must be unique, and its materials must
  be defined in `materials.json`.
- **Never rename or remove a code that projects already use;** their elements
  would stop resolving.

[data/materials.json](data/materials.json) defines each material once: `Mild steel`,
`Reinforced concrete`, `Structural timber`, `Steel timber fixings`, `Reinforced masonry`.
- **Its B2 letter row:** `b2Label`, `b2MeansOfCompliance` (B2/AS1 or Alternative
  Solution) and `b2Details`. A `null` text means it is not written yet, and the
  PS1 is blocked for that material until it is.
- **`maintenance`:** the Structural Maintenance Schedule items it brings,
  pre-ticked when it is used. They must be standard items from
  [data/maintenance_items.json](data/maintenance_items.json): the form's items per
  interval, word for word from the ACE NZ / Engineering NZ form, shown as tick
  boxes on the PS1 edit page. The schedule is part of the PS1 when any item is
  ticked: by default when mild steel or steel timber fixings are used.
- **Never rename a material that element types use;** checked when a project loads.

[data/design_defaults.json](data/design_defaults.json) holds firm-wide design
defaults, currently the residential live loads and barrier loads used by the
Structural Calculations Report. Units are in the field names (`distributedKpa`,
`pointKn`, `lineKnPerM`, `infillKpa`).

[data/territorial_authorities.json](data/territorial_authorities.json) lists New
Zealand's 67 councils (name, territory, authority, physical and postal address,
website). The portal links the same list; a project's `territorialAuthority` must
be one of its names. The B2 letter is addressed to the council's postal address.

[data/sir_actions.json](data/sir_actions.json) holds the Site Inspection Report's
standard "Actions Required" (`{council}` is filled in). The standard observations
a SIR item starts from are on each element type's `inspections` in the element
library.

A project's data is a separate file; see
[data/project_sample.json](data/project_sample.json). It holds:
- the portal's project fields, as the portal sends them;
- `elements`: the project's element instances (type code, description,
  material, and the URL of the calculation engine's report);
- `durability`: the corrosion and durability choices, printed by the SCR (the
  PS1's B2 letter uses fixed text per material, not these values);
- `reports`: one block per report for the inputs the portal doesn't hold yet,
  mostly the engineer's judgements and the revision records: `scr`
  (Structural Calculations Report), `ps1` (PS1 package), `sir` (Site
  Inspection Reports), `rfi` (RFI responses), `ps4` (PS4 package).

## Structural Calculations Report (SCR)

`scr/` builds the report from a project, following the firm's SCR template (cover,
document control, project description, general, design basis, design items per
element category, other considerations), then Appendix A: a table of contents
and each element's calculation report, merged with page numbers across the whole
document.

```python
from sed_reporting.scr import render_scr_html, build_scr_pdf

html = render_scr_html(pd)   # the review preview; gaps show as "[not entered: …]"
pdf = build_scr_pdf(pd)      # refuses (ScrBlocked) while SCR errors remain;
                             # fetches each element's calculationReportUrl (https only)
```

## PS1 package

```python
from sed_reporting.ps1 import build_ps1_pdf, issue_ps1, render_ps1_html
html = render_ps1_html(pd)                 # the review preview
draft = build_ps1_pdf(pd)                  # unsigned, "DRAFT, not issued"; refuses (Ps1Blocked) while errors remain
pdf, issued_at = issue_ps1(pd, fetch)      # signed with the reviewing engineer's signature, dated, locked
```

The same pages and wording as the ACE NZ / Engineering NZ PS1 form (January 2024,
Rev 01): PS1, Schedule, guidance, Construction Monitoring Schedule, Certificate
of Design Work, Structural Maintenance Schedule and B2 letter. HTTP:
`POST /ps1/preview`, `/ps1/pdf`, `/ps1/issue`. The PS1 has a revision record
(`reports.ps1.revisions`, `P260703-PS1-Rev A`); an issued revision is never
regenerated, and a new SCR or drawing revision means a new PS1 revision. See
docs/portal_data_requests.md (sections 3.1, 3.2, 5.2 and 5.6).

## Site Inspection Reports

```python
from sed_reporting.sir import build_sir_pdf, issue_sir, render_sir_html
html = render_sir_html(pd, 1)              # SIR01's review preview (photos load from their links)
draft = build_sir_pdf(pd, 1, fetch)        # with photos, scaled down; unsigned
pdf, issued_at = issue_sir(pd, 1, fetch)   # signed by the inspection engineer, dated, locked
```

One SIR per site visit (`reports.sir.visits`), following the sample in
`samples/sir_reference/`. Each covers checklist items (the PS1's Construction
Monitoring Schedule plus `reports.sir.additionalInspections`). Each item has
observations with photos and Pass/Fail. A failure needs the builder's
correction, approved by the engineer, before the SIR can be issued. HTTP:
`POST /sir/preview`, `/sir/pdf`, `/sir/issue`, each with `?number=N`. The portal
records where it keeps each issued SIR (`pdfUrl`): the PS4 attaches it. See
docs/portal_data_requests.md (sections 4.5, 5.3, 5.4 and 7).

## RFI responses

```python
from sed_reporting.rfi import build_rfi_pdf, issue_rfi, render_rfi_html
html = render_rfi_html(pd, 1)              # the response to RFI01, for review
draft = build_rfi_pdf(pd, 1, fetch)        # available even while errors remain (for checking)
pdf, issued_at = issue_rfi(pd, 1, fetch)   # submitted: signed by the reviewing engineer, dated, locked
```

The firm's RFI letter in our theme (`samples/rfi_reference/`). The architect
pastes each structural request into its own box (`reports.rfi.rounds`); the
reviewing engineer answers under each, with images, and marks the drawings,
SCR and PS1 as cited or revised for this RFI. The letter goes out last: it can
be submitted only once everything it cites is issued and current, and a draft
cites each document as it will be then. HTTP: `POST /rfi/preview`, `/rfi/pdf`,
`/rfi/issue`, each with `?number=N`. See docs/portal_data_requests.md
(sections 4.6, 5.5 and 7).

## PS4 package

```python
from sed_reporting.ps4 import build_ps4_pdf, issue_ps4, render_ps4_html
html = render_ps4_html(pd)                 # the PS4's own pages, for review
draft = build_ps4_pdf(pd, fetch)           # with its attachments; refuses (Ps4Blocked) while errors remain
pdf, issued_at = issue_ps4(pd, fetch)      # signed by the reviewing engineer, dated, locked
```

The ACE NZ / Engineering NZ PS4 – Construction Review form (January 2024, Rev
01), in the same format as the PS1 and sharing its data
(`samples/ps4_reference/`). The package attaches every issued SIR, the PS3s
from the steel fabricator (when an element uses mild steel) and the builder's
Record of Work, which the builder uploads with the PS4 order
(`reports.ps4`). It can be issued only once every checklist item is done and
the PS1 it covers is current. Revision record as the PS1's. HTTP:
`POST /ps4/preview`, `/ps4/pdf`, `/ps4/issue`. See docs/portal_data_requests.md
(sections 3.9, 4.7, 5.7 and 7).

### Sample edit pages (development only)

```bash
.venv/bin/uvicorn sed_reporting.dev.server:app --app-dir .. --reload    # from this repo's root
# then open http://127.0.0.1:8000/dev/ (one edit page per report: /dev/scr/edit,
# /dev/ps1/edit, /dev/sir/edit, /dev/rfi/edit, /dev/ps4/edit)
```

The form on the left edits the sample project's report inputs; the preview and
the list of issues on the right update as you type. **Save** writes a working
copy, `data/project_sample.edited.json` (gitignored); **Reset** discards it;
**Download PDF** builds the report, using placeholders (element reports, photos,
signatures, logos, stored documents) because the sample's URLs aren't real.
Every page edits the same working copy. The production app (`sed_reporting.api:app`)
has none of these routes.

The page uses the same endpoints the portal will: `POST /scr/preview` returns the
HTML, the issues and a `form` block (categories with their default narratives and
elements, the firm defaults, which sections apply, and every field's allowed
choices), so no front end has to re-implement those rules.

## Project data (shared by every report)

`project_data/` reads a project file and the reference lists in `data/`, and
gives every report the same resolved views and checks.

```python
from sed_reporting.project_data import ProjectData, load_library, load_project

pd = ProjectData(load_project("data/project_sample.json"), load_library())
pd.scope_labels      # ["SED Foundations", "SED Beams", "SED Portal Frames"]
pd.standards         # merged from the project's element types, each once
pd.inspections       # Construction Monitoring Schedule rows, each once
pd.b2_rows           # one B2 letter row per material used
pd.issues()          # errors (block a report) and warnings, for the review page
```

- **The portal's fields are accepted as sent.** Fields the reports don't use are
  ignored, so the portal can add fields freely.
- **Our blocks are strict:** `elements`, `durability` and `reports` reject
  unknown keys, so a misspelt input can't silently drop a value from a signed
  document.
- **Problems are collected, not raised one at a time,** so the review page can
  show them all. Examples: an element type or material not in the library; a
  material with no B2 text yet (blocks the PS1); a material in use without its
  durability block; an SCR revision cited by the PS1 that isn't issued yet.
- **Contracts for the front-end team:**
  [project_data/project.schema.json](project_data/project.schema.json) and a
  schema for each reference list in `data/` (element library, materials,
  maintenance items, territorial authorities, SIR actions, CM levels), all in
  `project_data/` and generated from the models. A test fails if they drift.

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/test_element.py tests/test_assemble.py tests/test_api.py tests/test_project_data.py \
    tests/test_scr_document.py tests/test_scr_build.py tests/test_dev_server.py tests/test_fonts.py \
    tests/test_ps1.py tests/test_sir.py tests/test_rfi.py tests/test_ps4.py
.venv/bin/uvicorn sed_reporting.api:app --app-dir ..      # run from this repo's root
```

**Layout.** The repo root *is* the `sed_reporting` package, the same layout as
`reporting`. Its parent directory goes on the path (`--app-dir ..`, and
`conftest.py` for tests). That one parent also provides the sibling `reporting`
checkout, which is how every design module finds it: `~/dev` locally, `/opt` in
the Docker base image. `reporting` is therefore not pip-installed, and
`requirements.txt` lists its runtime dependency (`svglib`) directly.

## Known limits / next steps

- **Element PDFs rendered before `reporting` 0.2.0** have every section bookmark
  on their first page. The assembler detects this and leaves out that element's
  nested bookmarks; re-render the element to get them.
- **No authentication.** Keep the service internal, behind Cloudflare Access or
  Tunnel, and cap request size upstream.
- **Elements travel inline as base64.** Fetching by storage key (R2) is the next
  step once the portal stores element PDFs there.
- **The contents page** lists project details in a plain table; switch to
  `reporting`'s title block / `InfoCard` once those land. Contents rows are not
  yet clickable (the bookmarks are).
