"""Materials (data/materials.json): what each material means for the reports,
defined once. An element type names its material(s) from here
(element_library.json), so defining a type defines its material.

    b2Label, b2MeansOfCompliance, b2Details   its row in the PS1's B2 letter
    maintenance                                the standard maintenance items it
                                               brings (maintenance_items.json),
                                               pre-ticked when it is used
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from sed_reporting.project_data._base import Strict
from sed_reporting.project_data.project import MaintenanceItems

MATERIALS_FILE = Path(__file__).resolve().parents[1] / "data" / "materials.json"

Text = Annotated[str, Field(min_length=1)]


class Material(Strict):
    name: Text                 # e.g. "Mild steel"; what element types name
    b2_label: Text             # e.g. "Mild steel structure"; the B2 letter's material column
    b2_means_of_compliance: Literal["B2/AS1", "Alternative Solution"] = "B2/AS1"
    b2_details: str | None     # None = not written yet; reports needing it are blocked
    maintenance: MaintenanceItems = MaintenanceItems()   # standard items (maintenance_items.json) pre-ticked when used


class Materials(Strict):
    materials: list[Material]

    @model_validator(mode="after")
    def _unique(self) -> Materials:
        names = [m.name for m in self.materials]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"material(s) listed more than once: {', '.join(dupes)}")
        return self

    def find(self, name: str | None) -> Material | None:
        return next((m for m in self.materials if m.name == name), None)


def load_materials(path: str | Path = MATERIALS_FILE) -> Materials:
    """Read and validate the materials."""
    return Materials.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def check_element_types(library, materials: Materials) -> None:
    """Every material an element type names must be defined in materials.json."""
    for t in library.element_types:
        unknown = [m for m in t.materials if materials.find(m) is None]
        if unknown:
            raise ValueError(f"element type {t.code}: material(s) not in materials.json: {', '.join(unknown)}")
