"""The report-as-data model.

A ReportDocument is metadata plus an ordered list of components. It carries
no theme and no medium — the same document renders through either engine
with either theme. This is what keeps View, Medium and Theme independent.
"""

from dataclasses import dataclass, field

from reporting.core.component import Component


@dataclass
class DocMeta:
    """Document-level metadata and running header/footer text."""

    title: str
    reference: str = ""
    site_address: str = ""
    engineer: str = ""
    date: str = ""
    header_text: str = ""     # running page header (top-centre)
    footer_left: str = ""     # running page footer (bottom-left)
    footer_note: str = ""     # second running footer line, under footer_left

    # `footer_note` carries a caveat that has to appear on *every* page rather
    # than once at the end — a site-specific scope limitation, say, which only
    # does its job if a page separated from the set still carries it. Unset by
    # default, so documents that do not use it render exactly as before.


@dataclass
class ReportDocument:
    """A composed report: metadata + ordered components (the 'View')."""

    meta: DocMeta
    body: list[Component] = field(default_factory=list)
