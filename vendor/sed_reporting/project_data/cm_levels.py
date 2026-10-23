"""The construction monitoring levels CM1–CM5 (data/cm_levels.json): what each
level's review involves and where it is appropriate, word for word from
Table 1 of "Construction Monitoring Services". Shown under the PS1's choice of
level; never printed on a report.
"""

from __future__ import annotations

import json
import typing
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from sed_reporting.project_data._base import Strict

CM_LEVELS_FILE = Path(__file__).resolve().parents[1] / "data" / "cm_levels.json"

Text = Annotated[str, Field(min_length=1)]
Level = Literal["CM1", "CM2", "CM3", "CM4", "CM5"]


class CmLevel(Strict):
    level: Level
    review: Text                       # the table's "Review" column: what the engineer does
    comment: Text                      # the table's "Comment" column: where the level is appropriate


class CmLevels(Strict):
    source: Text                       # where the wording comes from
    levels: list[CmLevel]

    @model_validator(mode="after")
    def _each_level_once_in_order(self) -> CmLevels:
        if [x.level for x in self.levels] != list(typing.get_args(Level)):
            raise ValueError("cm_levels.json must list CM1, CM2, CM3, CM4 and CM5, once each, in that order")
        return self


def load_cm_levels(path: str | Path = CM_LEVELS_FILE) -> CmLevels:
    """Read and validate the construction monitoring levels."""
    return CmLevels.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
