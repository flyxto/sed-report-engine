"""Project data for every report: the portal's project, its elements, the shared
durability choices and per-report inputs, resolved against the element library.

    load_project(path) -> Project
    load_library(path=data/element_library.json) -> ElementLibrary
    ProjectData(project, library)   views (scope, standards, inspections, B2 rows, …)
                                    and issues() for the review page
"""

from sed_reporting.project_data.cm_levels import CM_LEVELS_FILE, CmLevels, load_cm_levels
from sed_reporting.project_data.councils import COUNCILS_FILE, TerritorialAuthorities, TerritorialAuthority, load_councils
from sed_reporting.project_data.dates import nz_today
from sed_reporting.project_data.sir_actions import SIR_ACTIONS_FILE, SirActions, load_sir_actions
from sed_reporting.project_data.maintenance import MAINTENANCE_FILE, load_maintenance_items
from sed_reporting.project_data.defaults import DEFAULTS_FILE, DesignDefaults, load_defaults
from sed_reporting.project_data.library import LIBRARY_FILE, ElementLibrary, ElementType, load_library
from sed_reporting.project_data.materials import MATERIALS_FILE, Material, Materials, load_materials
from sed_reporting.project_data.project import Durability, Element, Project, load_project
from sed_reporting.project_data.resolve import B2Row, Issue, ProjectData, ResolvedElement
from sed_reporting.project_data.schema import SCHEMA_FILE, schema_json, write_schema

__all__ = [
    "Project",
    "Element",
    "Durability",
    "ElementLibrary",
    "ElementType",
    "Material",
    "ProjectData",
    "ResolvedElement",
    "B2Row",
    "Issue",
    "load_project",
    "load_library",
    "load_defaults",
    "load_councils",
    "load_sir_actions",
    "load_cm_levels",
    "CmLevels",
    "CM_LEVELS_FILE",
    "SirActions",
    "load_materials",
    "Materials",
    "MATERIALS_FILE",
    "load_maintenance_items",
    "MAINTENANCE_FILE",
    "TerritorialAuthorities",
    "TerritorialAuthority",
    "COUNCILS_FILE",
    "nz_today",
    "DesignDefaults",
    "LIBRARY_FILE",
    "DEFAULTS_FILE",
    "SCHEMA_FILE",
    "schema_json",
    "write_schema",
]
