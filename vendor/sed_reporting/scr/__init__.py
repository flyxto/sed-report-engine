"""The Structural Calculations Report (SCR): see document.py."""

from sed_reporting.scr.build import ScrBlocked, build_scr_pdf, fetch_url
from sed_reporting.scr.document import TITLE, build_document, render_scr_body_pdf, render_scr_html

__all__ = ["TITLE", "build_document", "render_scr_html", "render_scr_body_pdf", "build_scr_pdf", "fetch_url",
           "ScrBlocked"]
