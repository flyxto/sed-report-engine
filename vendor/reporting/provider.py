"""How design modules (beams, pf, rafts, rw, …) plug into reporting.

Each module hands over a `ReportProvider` — its name plus its view-building
functions. `generate()` renders: pick a profile (which maps to a view + medium +
theme), build the document, render it to a sink. `render_report()` is the single
entrypoint for modules: it renders through `generate()` and returns bytes, with
every PDF stamped. Central defaults are shared by every module; a module
overrides only the profiles it needs.

Library mode: a module calls `render_report(provider, results, "pdf")` in
process and stores the bytes. Every PDF that leaves a module goes through it, so
every PDF carries the manifest stamp that portal assembly (`sed_reporting`)
requires. If a central reporting API is added later, the endpoint runs these
same lines — no provider/view code changes.
"""

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from typing import Any

from reporting.core.document import ReportDocument
from reporting.core.theme import PRINT_THEME, WEB_THEME, Theme
from reporting.engine.html_engine import render_html
from reporting.engine.pdf_engine import render_pdf
from reporting.manifest import ReportManifest, stamp_manifest


@dataclass(frozen=True)
class OutputProfile:
    """Maps a named output to a view + medium + theme."""

    view: str
    medium: str          # "html" | "pdf"
    theme: Theme


# Defaults every module gets for free. Policy: web = detailed HTML, pdf = summary PDF.
DEFAULT_PROFILES: dict[str, OutputProfile] = {
    "web": OutputProfile(view="detailed", medium="html", theme=WEB_THEME),
    "pdf": OutputProfile(view="summary", medium="pdf", theme=PRINT_THEME),
}


@dataclass(frozen=True)
class ReportProvider:
    """A design module's report recipe: its key + view-building functions.

    `views` maps a view name ("detailed", "summary", …) to a function that turns
    the module's results into a ReportDocument. `profiles` overrides only the
    named outputs this module wants to change; the rest fall back to DEFAULT_PROFILES.
    `manifest` turns the results into the element's ReportManifest, which
    `render_report` stamps into every PDF; without it, PDF profiles are refused.
    """

    key: str
    views: dict[str, Callable[[Any], ReportDocument]]
    profiles: dict[str, OutputProfile] = field(default_factory=dict)
    manifest: Callable[[Any], ReportManifest] | None = None

    def resolved_profiles(self) -> dict[str, OutputProfile]:
        """Central defaults merged with this module's overrides."""
        return {**DEFAULT_PROFILES, **self.profiles}


def generate(provider: ReportProvider, results: Any, profile: str, sink) -> None:
    """Render `results` for `provider` using a named profile, into `sink`.

    `sink` is a path or an open stream (binary for PDF, text for HTML).
    """
    profiles = provider.resolved_profiles()
    if profile not in profiles:
        raise ValueError(f"Unknown profile '{profile}' for module '{provider.key}'. Available: {sorted(profiles)}")
    prof = profiles[profile]

    if prof.view not in provider.views:
        raise ValueError(f"Module '{provider.key}' has no view '{prof.view}'. Available: {sorted(provider.views)}")
    doc = provider.views[prof.view](results)

    if prof.medium == "html":
        render_html(doc, sink, theme=prof.theme)
    elif prof.medium == "pdf":
        render_pdf(doc, sink, theme=prof.theme)
    else:
        raise ValueError(f"Unknown medium '{prof.medium}' in profile '{profile}' (expected 'html' or 'pdf')")


def render_report(provider: ReportProvider, results: Any, profile: str = "pdf", *, report_id: str | None = None) -> bytes:
    """Render `results` for `provider` and return the bytes, ready to store.

    The shared path for everything a module outputs. A PDF comes back stamped
    with `provider.manifest(results)` (see manifest.py), so it can go into a
    combined portal report; this never returns an unstamped PDF. HTML comes back
    as UTF-8 bytes, unstamped. `report_id`, if given, replaces the manifest's `id`.
    """
    prof = provider.resolved_profiles().get(profile)
    if prof is None or prof.medium != "pdf":
        # HTML — or an unknown profile or medium, which generate() rejects as usual.
        out = StringIO()
        generate(provider, results, profile, out)
        return out.getvalue().encode("utf-8")

    manifest = _checked_manifest(provider, results, report_id)   # before rendering: fail fast
    out = BytesIO()
    generate(provider, results, profile, out)
    return stamp_manifest(out.getvalue(), manifest)


def _checked_manifest(provider: ReportProvider, results: Any, report_id: str | None) -> ReportManifest:
    """Build the manifest and refuse one that sed_reporting would reject at assembly."""
    if provider.manifest is None:
        raise ValueError(
            f"Module '{provider.key}' has no manifest builder, and PDFs must be stamped for portal "
            "assembly. Pass ReportProvider(..., manifest=fn), where fn(results) returns a ReportManifest."
        )
    m = provider.manifest(results)
    if not isinstance(m, ReportManifest):
        raise TypeError(f"Module '{provider.key}': the manifest builder must return a ReportManifest, got {type(m).__name__}")
    if report_id is not None:
        m = dataclasses.replace(m, id=report_id)
    empty = [name for name in ("title", "module", "element_type") if not str(getattr(m, name) or "").strip()]
    if empty:
        raise ValueError(
            f"Module '{provider.key}': manifest {', '.join(empty)} is empty; sed_reporting would reject this PDF."
        )
    return m


# --- optional registry: look a provider up by key (useful for a future API) ---

_REGISTRY: dict[str, ReportProvider] = {}


def register(provider: ReportProvider) -> ReportProvider:
    """Register a provider so it can be fetched by key. Returns it for chaining."""
    _REGISTRY[provider.key] = provider
    return provider


def get(key: str) -> ReportProvider:
    """Fetch a registered provider by key."""
    if key not in _REGISTRY:
        raise KeyError(f"No report provider registered for '{key}'. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[key]
