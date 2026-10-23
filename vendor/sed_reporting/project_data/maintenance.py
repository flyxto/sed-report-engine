"""The Structural Maintenance Schedule's standard items (data/maintenance_items.json):
per interval, word for word from the ACE NZ / Engineering NZ PS1 form, where they
are tick boxes. The PS1 edit page shows them the same way.

Kept apart from the element library: it is a list of its own, with its own
source. A material in the library names the items it brings (its `maintenance`),
which are pre-ticked when the material is used; those names must be in this list.
"""

from __future__ import annotations

import json
from pathlib import Path

from sed_reporting.project_data.project import MaintenanceItems

MAINTENANCE_FILE = Path(__file__).resolve().parents[1] / "data" / "maintenance_items.json"


def load_maintenance_items(path: str | Path = MAINTENANCE_FILE) -> MaintenanceItems:
    """Read and validate the standard maintenance items."""
    return MaintenanceItems.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def check_materials(materials, items: MaintenanceItems) -> None:
    """Every material's maintenance items must be standard items of the same interval."""
    for m in materials.materials:
        for interval in MaintenanceItems.model_fields:
            extra = [i for i in getattr(m.maintenance, interval) if i not in getattr(items, interval)]
            if extra:
                raise ValueError(f"material {m.name!r}: maintenance item(s) not in maintenance_items.json "
                                 f"({interval}): " + "; ".join(repr(i[:60]) for i in extra))
