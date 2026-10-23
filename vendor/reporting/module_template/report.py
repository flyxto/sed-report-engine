"""Report wiring for THIS design module — copy this file into your module.

To adapt (3 steps):
  1. Set MODULE_KEY to your module name ("rafts", "beams", "pf", "rw"), and set
     ELEMENT_TYPE from the fixed list in reporting/manifest.py.
  2. Fill detailed_view() / summary_view() with your sections, reading YOUR
     results object, and _manifest() with its identity. Point the imports at
     your real results + components.
  3. Put any module-only components in report_components.py.

Everything else — the engine, themes, fonts, HTML/PDF, page furniture, the
manifest stamp — comes from `reporting`. The rest of your module gets its
reports by calling render() below, which returns bytes to store.
"""

import sys
from pathlib import Path
from typing import Any

# Make `reporting` importable when this file is run standalone. In your real
# module you'll install/have `reporting` on the path and can delete this.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from reporting import (  # noqa: E402
    Card,
    DesignCheck,
    DesignCheckTable,
    DocMeta,
    ReportDocument,
    ReportManifest,
    ReportProvider,
    SectionHeader,
    StatusBanner,
    SummaryCardGrid,
    render_report,
    util_label,
    util_passed,
)

# Sibling files in this template. In a packaged module use your package path,
# e.g. `from rafts.report_components import RibEdgeTable`.
from report_components import RibEdgeTable  # noqa: E402
from results import SAMPLE, DemoResults  # noqa: E402

MODULE_KEY = "mymodule"  # <-- rename to your module: "rafts" | "beams" | "pf" | "rw"
ELEMENT_TYPE = "raft"    # <-- from the fixed list in reporting/manifest.py


# --- shared building blocks for this module's views ------------------------


def _meta(r: DemoResults) -> DocMeta:
    return DocMeta(
        title=r.project,
        reference=r.reference,
        header_text=f"{MODULE_KEY.upper()} STRUCTURAL ANALYSIS — {r.project.upper()}",
        footer_left=r.reference,
    )


# Every utilisation shown — cards, banner, tables — goes through util_label, and
# every OK/FAIL through util_passed / util_status, so they can never disagree.


def _utils(r: DemoResults) -> list[float]:
    """Every utilisation in the report; the governing value and the overall pass come from these."""
    return [c.util for c in r.checks] + [e.util for e in r.edges]


def _cards(r: DemoResults) -> SummaryCardGrid:
    return SummaryCardGrid([
        Card("System", r.system, ""),
        Card("Concrete", r.concrete, "Specified f'c"),
        Card("Max Utilisation", util_label(max(_utils(r))), "Governing check"),
    ])


def _banner(r: DemoResults) -> StatusBanner:
    passed = all(util_passed(u) for u in _utils(r))
    headline = "Design Satisfactory" if passed else "Design Requires Upgrade"
    return StatusBanner(passed, headline, f"Maximum Utilisation: {util_label(max(_utils(r)))}")


def _checks_table(r: DemoResults) -> DesignCheckTable:
    return DesignCheckTable([DesignCheck(c.name, c.demand, c.capacity, c.util) for c in r.checks])


# --- the two views (content selection) -------------------------------------


def detailed_view(r: DemoResults) -> ReportDocument:
    """Full report — all checks + every edge."""
    return ReportDocument(meta=_meta(r), body=[
        _banner(r),
        _cards(r),
        SectionHeader("Design Check Summary", level=2),
        _checks_table(r),
        SectionHeader("Per-Edge Results", level=3),
        RibEdgeTable(r.edges),                    # domain component, all edges
    ])


def summary_view(r: DemoResults) -> ReportDocument:
    """Reasonable summary — checks + worst 3 edges."""
    return ReportDocument(meta=_meta(r), body=[
        _banner(r),
        _cards(r),
        SectionHeader("Design Check Summary", level=2),
        _checks_table(r),
        SectionHeader("Critical Edges (worst 3)", level=3),
        RibEdgeTable(r.worst_edges(3)),           # domain component, subset
    ])


# --- the element's identity, stamped into every PDF ------------------------


def _manifest(r: DemoResults) -> ReportManifest:
    """What the combined portal report reads from this element's PDF: the
    contents-row title, the module key, the element type and the reference."""
    return ReportManifest(
        id=f"{MODULE_KEY}-{r.reference}",
        module=MODULE_KEY,
        element_type=ELEMENT_TYPE,
        title=r.project,
        reference=r.reference,
    )


# --- the provider: this module's whole surface to reporting ----------------

provider = ReportProvider(
    key=MODULE_KEY,
    views={"detailed": detailed_view, "summary": summary_view},
    manifest=_manifest,
)


def render(results: Any, profile: str = "pdf") -> bytes:
    """The single call the rest of your module makes to get a report.

    profile: "pdf" (summary PDF) or "web" (detailed HTML) — the shared defaults.
    Returns bytes to store. A PDF comes back stamped with _manifest(), ready for
    the combined portal report; HTML comes back as UTF-8.
    """
    return render_report(provider, results, profile)


if __name__ == "__main__":
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    (out / "demo_detailed.html").write_bytes(render(SAMPLE, "web"))
    (out / "demo_summary.pdf").write_bytes(render(SAMPLE, "pdf"))
    print(f"Wrote: {out}/demo_detailed.html")
    print(f"Wrote: {out}/demo_summary.pdf")
