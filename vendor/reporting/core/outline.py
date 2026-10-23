"""PDF outline (bookmark) support — a zero-size flowable that registers a
bookmark at its position in the document.

The PDF engine adds a top-level entry for the document title; SectionHeader adds
one per heading. This gives each element PDF a clickable navigation outline when
it is opened on its own.

Note: the combined report's contents pages are still one row per element file,
built from standard PDF metadata (see manifest.py), not from this outline.
`sed_reporting` nests these outline entries under each element's own bookmark in
the combined PDF (its `section_bookmarks` option), so section headings stay
clickable there too.

Levels are clamped so they never jump by more than one (a ReportLab requirement
for a well-formed outline tree).
"""

from reportlab.platypus import Flowable


class OutlineEntry(Flowable):
    """Registers a PDF bookmark for `title` at `level` (0 = top). Draws nothing."""

    def __init__(self, title: str, level: int = 0):
        super().__init__()
        self.title = title
        self.level = max(0, level)
        self.width = 0
        self.height = 0

    def wrap(self, _aw, _ah):
        return (0, 0)

    def draw(self):
        canv = self.canv
        # Track the last-used level on the canvas so we never skip a level.
        last = getattr(canv, "_outline_last_level", -1)
        level = min(self.level, last + 1)
        canv._outline_last_level = level
        key = f"ol{id(self)}"
        canv.bookmarkPage(key)
        canv.addOutlineEntry(self.title, key, level=level, closed=False)
