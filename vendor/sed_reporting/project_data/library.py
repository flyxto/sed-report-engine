"""The element library: the firm-wide, growing list of element types
(data/element_library.json), shared by every project.

A project's elements refer to a type by `code`. Each type names its material(s),
defined once in data/materials.json: defining a type defines its material.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from sed_reporting.project_data._base import Strict
from sed_reporting.project_data.project import Inspection, RbwRow

LIBRARY_FILE = Path(__file__).resolve().parents[1] / "data" / "element_library.json"

Text = Annotated[str, Field(min_length=1)]


class ElementType(Strict):
    code: Text                 # e.g. "PF1"; what a project's element refers to
    name: Text                 # e.g. "Rectangular Portal Frame"
    category: Text             # e.g. "Portal Frames"; groups elements in the reports
    materials: list[Text] = Field(min_length=1)   # every material the type has, from materials.json
                                                  # e.g. TB1: Structural timber, Steel timber fixings
    standards: list[Text] = []
    inspections: list[Inspection] = []
    scr_narrative: str | None = None   # default text for the report section; None = not written yet
    # The PS1's Certificate of Design Work: the row this type falls under, and its default description.
    rbw_row: RbwRow | None = None
    rbw_description: str | None = None   # e.g. "SED Foundations as per foundation plan"


class ElementLibrary(Strict):
    element_types: list[ElementType]

    @model_validator(mode="after")
    def _unique(self) -> ElementLibrary:
        codes = [t.code for t in self.element_types]
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        if dupes:
            raise ValueError(f"element type code(s) listed more than once: {', '.join(dupes)}")
        # The PS1's Construction Monitoring Schedule prints every library inspection's timeframe.
        # (An inspection added on a project may leave it out.)
        missing = [f"{t.code}: {i.item}" for t in self.element_types for i in t.inspections if not i.timeframe.strip()]
        if missing:
            raise ValueError("library inspection(s) without a timeframe: " + "; ".join(missing))
        return self

    def element_type(self, code: str) -> ElementType | None:
        return next((t for t in self.element_types if t.code == code), None)


def load_library(path: str | Path = LIBRARY_FILE) -> ElementLibrary:
    """Read and validate the element library."""
    return ElementLibrary.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
