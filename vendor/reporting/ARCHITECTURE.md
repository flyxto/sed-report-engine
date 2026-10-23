# Reporting Engine — Architecture

A shared, memory-efficient engine that renders structural reports to **both**
an on-screen **HTML** view and an export **PDF**, from one component model,
across many structural analysis modules (rafts, beams, pf1, …).

> Related docs: [README.md](README.md) (overview + quickstart) ·
> [DEPLOYMENT.md](DEPLOYMENT.md) (hosting, cost, performance) ·
> [module_template/README.md](module_template/README.md) (module adoption).

## Why not just HTML→PDF?

Two options were weighed and rejected as the primary path:

- **WeasyPrint (HTML+CSS → PDF).** Highest fidelity, but builds a full
  DOM+CSSOM+box tree for the whole document in memory — peak RSS scales with
  document length. Fine locally; heavier per-render at platform scale.
- **xhtml2pdf (HTML+CSS → PDF via ReportLab).** Flat memory, but no CSS grid /
  flex / gradients / paged-media counters — our templates lean on all of those,
  so it would mean a template fork *and* a mini CSS-cascade engine to maintain.

Chosen path: **Approach B — a semantic component model over ReportLab.** No HTML
parsing, no CSS-cascade engine (the hardest, buggiest part of any HTML→PDF tool).
ReportLab streams page-by-page, so per-render memory stays flat — the property we
need for a scalable platform.

## Three orthogonal axes

The whole design falls out of keeping these independent:

| Axis | What it varies | Where it lives |
|------|----------------|----------------|
| **Data model** | per structural module (raft vs beam …) | the structural module |
| **View** | *which* components appear (detailed vs summary) | an assembler function `(results) -> ReportDocument` |
| **Medium** | *how* it renders (HTML vs PDF) | an engine function `render_html` / `render_pdf` |
| **Theme** | brand/typography | one `Theme` object, passed at render time |

"Detailed HTML" and "summary PDF" is just the **default routing** through the
View × Medium grid — not a hardcoded coupling. Any view renders to any medium.

```
results ──► detailed_view(results) ─┐
        └─► summary_view(results)  ─┼─► render_html(doc, theme=WEB)   ─► screen
                                    └─► render_pdf(doc,  theme=PRINT)  ─► PDF
```

## Layers and the dependency rule

```
reporting/  (this package — everything shared)
├── core/         Component protocol, ReportDocument/DocMeta, Theme, pdf_style, utilisation
├── engine/       render_html, render_pdf (BaseDocTemplate spine), page furniture
└── components/   SectionHeader, StatusBanner, SummaryCardGrid, DataTable, …

raft module / beam module / pf1 module  (each depends on reporting)
├── report.py            detailed_view / summary_view assemblers
└── report_components.py DOMAIN components (e.g. RaftPerEdgeTable)
```

**Rule: `reporting` never imports from a structural module.** Dependencies point
inward only. Structural modules import shared components + the `Component`
protocol, contribute their own domain components and view assemblers, and get
both mediums for free. A new structural module is added without touching
`reporting`.

- **Shared components** live here (`reporting/components/`).
- **Domain components** live in the structural module that owns them, implementing
  the same `Component` protocol.
- **Theme is centralised** here: `BASE_THEME` is the single source of brand truth;
  `WEB_THEME` / `PRINT_THEME` are variants off it. A rebrand edits `BASE_THEME`.

## Integration flow — how modules call reporting

There is **one shared engine**, selected per module by a **Provider**. A design
module (beams, pf, rafts, rw, …) exposes its report recipe; `render_report()` is
the single entrypoint.

```python
# rafts/report.py  (in the raft module — imports FROM reporting)
from reporting import ReportProvider, OutputProfile, PRINT_THEME

provider = ReportProvider(
    key="rafts",
    views={"detailed": detailed_view, "summary": summary_view},
    # inherit shared "web"/"pdf" profiles; override/add only what differs:
    profiles={"pdf_full": OutputProfile("detailed", "pdf", PRINT_THEME)},
    manifest=build_manifest,   # results -> ReportManifest, stamped into every PDF
)
```

```python
# calling it (in-process / library mode)
import reporting
from rafts.report import provider
pdf = reporting.render_report(provider, results, "pdf")    # summary PDF, stamped
html = reporting.render_report(provider, results, "web")   # detailed HTML, UTF-8 bytes
```

- **Every PDF that leaves a module goes through `render_report`.** It renders
  through `generate()` and stamps the PDF with the provider's manifest
  (`manifest.py`), which is what lets the PDF go into a combined portal report —
  `sed_reporting` rejects unstamped PDFs. It never returns an unstamped PDF: a
  PDF profile on a provider with no `manifest`, or a manifest with an empty
  title, module or element type, raises. `manifest.module` is the provider's key;
  `element_type` comes from the fixed list on `ReportManifest`. `generate()`
  stays as the unstamped primitive that writes to a sink.
- **One utilisation rule for the whole report** (`core/utilisation.py`). Modules
  hold utilisations as float ratios. Every utilisation shown anywhere in a report
  (tables, cards, banners, calc blocks) uses `util_label`; every OK/FAIL from a
  utilisation comes from `util_status` or `util_passed`; an overall pass is
  `all(util_passed(u) for u in utils)`. Never `f"{u:.0%}"`, `round()` or a
  hand-typed status. Labels round up, so a value shown above 100 % is always
  FAIL, and a check reads the same in a card, a banner and `DesignCheckTable`.
- **Profiles** map a name → (view, medium, theme). `DEFAULT_PROFILES` ships
  `web = detailed HTML` and `pdf = summary PDF`; a module overrides only the
  names it wants (`resolved_profiles()` merges defaults + overrides).
- **Registry** (`register` / `get`) is optional — look a provider up by key.

**Library vs central service.** Today this runs as a **library**: each module
`import reporting` and renders its own reports. The provider/view/component code
is identical if a **central reporting API** is added later — the endpoint just
runs the same `render_report()` lines. The trade to know: a central service must hold
every module's report code (the recipes live at the service); the library keeps
each module's recipe with the module. Chosen: library now, endpoint optional later.

## The core contract

Two small interfaces are the entire API surface.

```python
# core/component.py
class Component(Protocol):
    def render_html(self, theme: Theme) -> str: ...
    def render_pdf(self, theme: Theme) -> list[Flowable]: ...

# core/document.py
@dataclass
class ReportDocument:
    meta: DocMeta
    body: list[Component]     # the composition — this is the "View"
```

A component knows only how to draw *itself* in each medium. The assembler decides
placement; the engine decides format; the theme is passed in at render time.

## HTML→ReportLab mapping (the engine internals)

| Construct | ReportLab realisation |
|-----------|----------------------|
| block / heading | `Paragraph` + a `ParagraphStyle` |
| **grid / flex row** | **`Table` with N equal columns**, each cell a stack of flowables (see `SummaryCardGrid`) — the key porting trick |
| data table | `Table` + `TableStyle`, `repeatRows=1` (headers repeat across page splits; auto-splits) |
| `page-break-before` | `PageBreak()` |
| keep-together | `KeepTogether([...])` |
| running header / footer | `PageTemplate(onPageEnd=draw_furniture)`; no page numbers — `sed_reporting` numbers the combined document |
| inline `<strong>`, `<sub>`, `<sup>` | ReportLab para markup `<b>`, `<sub>`, `<super>` |

## Opt-in document furniture

Two `Theme` flags add furniture that the other medium already shows. Both are off
by default, so existing documents render exactly as before; a module opts in per
output, e.g. `OutputProfile("summary", "pdf", replace(PRINT_THEME, pdf_title_block=True))`.

| Flag | Effect |
|------|--------|
| `pdf_title_block` | The PDF opens with the title block the HTML header shows: a navy band with the title and one line of Ref / Site / Engineer / Date (empty fields left out). |
| `html_footer_note` | The HTML shows `DocMeta.footer_note` under the header, on screen and in print. Chrome (131+) also prints it in the bottom page margin of every page (a CSS `@page` margin box); Firefox and Safari ignore margin boxes, so the copy under the header is the one they print. The `@page` rules are emitted only when a note is shown. |

## Scalability properties

- **Stateless engines** — one call renders one document; no module-global state.
  Safe to fan out across a bounded worker pool with back-pressure.
- **Streaming** — `render_pdf` / `render_html` accept a path *or* an open stream;
  write straight to a file / `BytesIO` / object-store stream.
- **Flat per-render memory** — ReportLab lays out page-by-page.
- **Deterministic** — same input → same bytes; cacheable and testable.

## Package layout note

The repo root **is** the `reporting` package (no nested `reporting/reporting/`).
The root has `__init__.py`, so it is importable as `reporting` whenever its
**parent** directory is on `sys.path`.

- **Dev / tests** — `conftest.py` at the repo root puts the parent on the path;
  the module template does the same via a small bootstrap. Deterministic, cwd-independent.
- **Cross-project / production** — build a wheel (`pip install .`) or add the
  parent dir to `PYTHONPATH`. Note: `pip install -e .` (editable) is **unreliable**
  when the repo root is the package — setuptools' generated finder/`.pth` points at
  a transient `build/` mirror and silently drops out, so import becomes
  intermittent. Avoid editable installs for this layout.

## Fonts (Unicode)

The PDF uses **DejaVu Sans** (regular/bold/oblique), bundled under
`assets/fonts/` (redistributable — see `LICENSE_DEJAVU`). It covers the Greek
letters, superscript-minus, sub/superscripts and math symbols that base-14
Helvetica lacks (`φMn⁻`, `μ`, `ξ`, `²`, `≥`, …). `core/fonts.register_fonts()`
is idempotent and called from both the PDF engine and the `pdf_style` builders,
so any component renders correctly whether or not it goes through the engine.
Font files are shipped as package data (`pyproject.toml`).

## Known refinements (not yet done)

- **Column sizing** in `DataTable` is equal-width; content-proportional sizing is
  a future improvement (matters for wide tables like per-edge results).
- Gradients are flattened to solid brand colour in PDF (cosmetic).
