"""Firm-wide defaults (data/design_defaults.json): the live loads and barrier
loads the Structural Calculations Report starts from, and the PS1's verification
method and Certificate of Design Work answer (carried out or supervised). A
project's `reports.scr` / `reports.ps1` overrides them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from sed_reporting.project_data._base import Strict
from sed_reporting.project_data.project import BarrierLoads, LiveLoad

Text = Annotated[str, Field(min_length=1)]

DEFAULTS_FILE = Path(__file__).resolve().parents[1] / "data" / "design_defaults.json"


class LiveLoadDefaults(Strict):
    residential: list[LiveLoad]
    barriers: BarrierLoads


class Ps1Defaults(Strict):
    verification_methods: Text         # e.g. "B1/VM1 and VM2"; a project's own wording replaces it
    # The Certificate of Design Work's "did you carry out the design work or supervise another
    # engineer?", for every applicable row; a project can change any row.
    carried_out_or_supervised: Literal["Carried out", "Supervised"]


class DesignDefaults(Strict):
    live_loads: LiveLoadDefaults
    ps1: Ps1Defaults


def load_defaults(path: str | Path = DEFAULTS_FILE) -> DesignDefaults:
    """Read and validate the design defaults."""
    return DesignDefaults.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
