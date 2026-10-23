# Module report template

Copy these files into a design module (rafts, beams, pf, rw, …) to give it
HTML + PDF reporting. The shared engine, themes, fonts and components come from
the `reporting` package — you only write what's specific to your module.

## Files

| File | What it is | You edit? |
|------|------------|-----------|
| `report.py` | provider + `detailed_view` / `summary_view` + `_manifest()` + `render()` | **yes** — your sections and identity |
| `report_components.py` | module-only components (e.g. `RibEdgeTable`) | **yes** — as needed |
| `results.py` | placeholder for your analysis output | **replace** with your real type |

## Adapt in 3 steps

1. Set `MODULE_KEY` in `report.py` to your module name, and `ELEMENT_TYPE` to
   one of the fixed list in `reporting/manifest.py`.
2. Fill `detailed_view()` / `summary_view()` with your sections, reading your
   own results object, and `_manifest()` with its identity. Point the imports
   at your real results + components.
3. Add any module-only components to `report_components.py` (they usually just
   arrange shared components — see `RibEdgeTable`).

## How your module prints

The rest of your module calls one function, which returns bytes to store:

```python
from your_module import report

pdf = report.render(results, "pdf")     # summary PDF, stamped for the portal
html = report.render(results, "web")    # detailed HTML (UTF-8)
```

It prints *correctly* because your module owns the recipe: `render()` uses your
`provider` (your views + components) and your `results`. Reporting handles the
engine, theme and page furniture. Nothing to discover at call time — you pick a
profile ("web"/"pdf") and pass your results.

**Every PDF that leaves your module goes through `render()`** — that is,
`reporting.render_report`. It stamps the PDF with `_manifest()`, which is what
lets the PDF go into a combined portal report: `sed_reporting` rejects
unstamped PDFs. `render_report` refuses to return an unstamped PDF — a provider
with no `manifest`, or a manifest with an empty title, module or element type,
raises instead. `manifest.module` is your `MODULE_KEY`; `element_type` comes
from the fixed list in `reporting/manifest.py`. Don't write PDFs with
`generate()` directly: it does not stamp.

## One utilisation rule

Hold each utilisation as the float ratio your analysis computed (1.0 == 100 %)
— see `results.py` — and let `reporting` turn it into text:

- Every utilisation shown anywhere in the report (tables, cards, banners, calc
  blocks) uses `util_label(u)` — or `util_label(u, style="ratio")` for "0.77".
- Every OK/FAIL from a utilisation comes from `util_status(u)` or `util_passed(u)`.
- An overall pass is `all(util_passed(u) for u in utils)`.
- Never use `f"{u:.0%}"`, `round()` or a hand-typed status.

Labels round **up** (0.763 → "77%", 1.004 → "101%"), so a value shown above
100 % is always FAIL and one shown at or below it is always OK, and the same
check reads the same everywhere. Show the checks with `DesignCheckTable`, which
follows the same rule. The full rule is in `reporting/core/utilisation.py`.

## Try it

```bash
python module_template/report.py     # writes module_template/output/
```
