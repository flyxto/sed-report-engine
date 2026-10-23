# reporting

A shared, memory-efficient engine that renders structural engineering reports to
**both** an on-screen **HTML** view and an export **PDF**, from one component
model, across many design modules (rafts, beams, pf, rw, …).

Built on **ReportLab** (not WeasyPrint) for a flat, dependency-free memory
profile that scales cheaply on a small server. See [ARCHITECTURE.md](ARCHITECTURE.md)
for the design and [DEPLOYMENT.md](DEPLOYMENT.md) for hosting/ops.

## Status

- ✅ Engine (HTML + PDF), themes, Unicode fonts, shared components
- ✅ Provider / profiles / `render_report()` integration flow (library mode), PDFs stamped for the portal
- ✅ Module template for design modules to copy
- ✅ Tests (green)
- ⏳ Real per-module views (each design module writes its detailed/summary views)
- ✅ Diagram/image, calc-block, info-card, design-check and sign-off shared components

## Quickstart

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # reportlab, pytest

python module_template/report.py         # the module-side template, run standalone
pytest -q                                # run the test suite
```

> **Import note:** the repo root *is* the `reporting` package (no nested
> `reporting/reporting/`). It's importable whenever its **parent** dir is on
> `sys.path`. Tests use `conftest.py`; the template uses a small
> bootstrap. Editable installs (`pip install -e .`) are unreliable for this
> layout — for production, build a wheel or add the parent dir to `PYTHONPATH`.
> Details in [ARCHITECTURE.md](ARCHITECTURE.md#package-layout-note).

## Repo layout

```
reporting/                    # repo root = the `reporting` package
├── core/        component protocol, document model, theme, fonts, pdf styles, utilisation rule
├── engine/      render_html, render_pdf (ReportLab spine), page furniture
├── components/  SHARED components (SectionHeader, DataTable, StatusBanner, SummaryCardGrid, CalcBlock,
│                Diagram/DiagramGrid, InfoCard/InfoCardGrid, DesignCheckTable, Signoff)
├── provider.py  ReportProvider, OutputProfile, generate(), render_report(), registry
├── assets/fonts/  bundled DejaVu Sans (Unicode) + licence
├── module_template/  copy-me starter for a design module (report.py + report_components.py)
└── tests/       pytest suite
```

## Core idea (30-second version)

A report is **not a template** — it's a **composition of components**, chosen by
three independent axes:

- **Data model** — per design module (its analysis results)
- **View** — *which* components appear (`detailed` vs `summary`) → an assembler function
- **Medium** — *how* it renders (HTML vs PDF) → an engine function
- **Theme** — brand/typography → one object, passed at render time

A design module exposes a **Provider** (its views, domain components and
manifest builder) and calls `render_report(provider, results, profile)`, which
returns bytes — PDFs stamped for the combined portal report. Everything else is
shared.

```python
import reporting
from rafts.report import provider
pdf = reporting.render_report(provider, results, "pdf")    # summary PDF, stamped
html = reporting.render_report(provider, results, "web")   # detailed HTML
```

## Documentation

| Doc | What's in it |
|-----|--------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Design: the three axes, layering, integration flow, HTML→ReportLab mapping, fonts, refinements |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Hosting decision, box architecture, Cloudflare Tunnel + Queues + R2, cost analysis, performance findings |
| [module_template/README.md](module_template/README.md) | How a design module adopts reporting (3 steps) |
