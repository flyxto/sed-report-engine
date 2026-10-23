"""JSON Schemas for the front-end team: the project file, the element library and
the list of territorial authorities.

Both are generated from the models and committed; a test fails if they drift.
After changing a model, regenerate from the repo's parent directory:

    PYTHONPATH=.. .venv/bin/python -c "from sed_reporting.project_data import write_schema; write_schema()"
"""

from __future__ import annotations

import json
from pathlib import Path

from sed_reporting.project_data.cm_levels import CmLevels
from sed_reporting.project_data.councils import TerritorialAuthorities
from sed_reporting.project_data.library import ElementLibrary
from sed_reporting.project_data.materials import Materials
from sed_reporting.project_data.sir_actions import SirActions
from sed_reporting.project_data.project import MaintenanceItems, Project

SCHEMA_DIR = Path(__file__).parent
SCHEMA_FILE = SCHEMA_DIR / "project.schema.json"
SCHEMAS = {"project.schema.json": Project, "element_library.schema.json": ElementLibrary,
           "territorial_authorities.schema.json": TerritorialAuthorities,
           "maintenance_items.schema.json": MaintenanceItems,
           "materials.schema.json": Materials,
           "sir_actions.schema.json": SirActions,
           "cm_levels.schema.json": CmLevels}


def schema_json(name: str = "project.schema.json") -> str:
    """A schema as formatted JSON text (by alias, i.e. the camelCase names in the files)."""
    return json.dumps(SCHEMAS[name].model_json_schema(by_alias=True), indent=2, ensure_ascii=False) + "\n"


def write_schema() -> None:
    for name in SCHEMAS:
        (SCHEMA_DIR / name).write_text(schema_json(name), encoding="utf-8")
