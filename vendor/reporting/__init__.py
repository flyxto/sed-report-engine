"""reporting — a shared dual-medium (HTML + PDF) structural report engine.

Structural modules build a `ReportDocument` from shared + domain components,
then render it through `render_html` / `render_pdf` with a chosen theme.
View (which components), Medium (which engine) and Theme are independent.
"""

from reporting.components.calc import CalcBlock, CalcRow
from reporting.components.card_grid import Card, SummaryCardGrid
from reporting.components.data_table import Column, DataTable
from reporting.components.design_check import DesignCheck, DesignCheckTable
from reporting.components.image import Diagram, DiagramGrid
from reporting.components.info_card import InfoCard, InfoCardGrid
from reporting.components.section_header import SectionHeader
from reporting.components.signoff import Signoff
from reporting.components.status_banner import StatusBanner
from reporting.core.component import Component
from reporting.core.document import DocMeta, ReportDocument
from reporting.core.theme import BASE_THEME, PRINT_THEME, PRINT_THEME_LANDSCAPE, WEB_THEME, Theme
from reporting.core.utilisation import util_label, util_passed, util_status
from reporting.engine.html_engine import render_html
from reporting.engine.pdf_engine import render_pdf
from reporting.manifest import ReportManifest, read_manifest, stamp_manifest
from reporting.provider import (
    DEFAULT_PROFILES,
    OutputProfile,
    ReportProvider,
    generate,
    get,
    register,
    render_report,
)

__all__ = [
    "Component",
    "DocMeta",
    "ReportDocument",
    "Theme",
    "BASE_THEME",
    "WEB_THEME",
    "PRINT_THEME",
    "PRINT_THEME_LANDSCAPE",
    "SectionHeader",
    "StatusBanner",
    "Card",
    "SummaryCardGrid",
    "Column",
    "DataTable",
    "CalcBlock",
    "CalcRow",
    "Diagram",
    "DiagramGrid",
    "InfoCard",
    "InfoCardGrid",
    "DesignCheck",
    "DesignCheckTable",
    "Signoff",
    "util_label",
    "util_status",
    "util_passed",
    "render_html",
    "render_pdf",
    "ReportManifest",
    "stamp_manifest",
    "read_manifest",
    "ReportProvider",
    "OutputProfile",
    "DEFAULT_PROFILES",
    "generate",
    "render_report",
    "register",
    "get",
]
