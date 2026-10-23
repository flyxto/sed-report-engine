"""The SIR's standard "Actions Required" (data/sir_actions.json), ticked on the
edit page; the engineer adds their own. "{council}" is replaced with the
project's council.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field

from sed_reporting.project_data._base import Strict

SIR_ACTIONS_FILE = Path(__file__).resolve().parents[1] / "data" / "sir_actions.json"

Text = Annotated[str, Field(min_length=1)]


class SirActions(Strict):
    actions: list[Text]


def load_sir_actions(path: str | Path = SIR_ACTIONS_FILE) -> SirActions:
    """Read and validate the standard actions."""
    return SirActions.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
