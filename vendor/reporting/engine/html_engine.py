"""HTML engine: renders a document to a self-contained HTML page.

The engine owns a theme-driven stylesheet; components emit semantic HTML
fragments that reference its classes. Stateless — one call, one page, to a
path or an open text stream.
"""

from html import escape
from pathlib import Path

from reporting.core.document import DocMeta, ReportDocument
from reporting.core.theme import WEB_THEME, Theme

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{style}
</style>
</head>
<body>
<div class="report-container">
{header}
{body}
</div>
</body>
</html>
"""


def render_html(doc: ReportDocument, sink, theme: Theme = WEB_THEME) -> None:
    """Render `doc` to `sink` (a path or open text stream) as HTML."""
    body = "\n".join(component.render_html(theme) for component in doc.body)
    note = doc.meta.footer_note if theme.html_footer_note else ""
    header = _doc_header(doc.meta)
    if note:
        header += f'<div class="footer-note">{escape(note)}</div>'
    page = _PAGE.format(
        title=escape(doc.meta.title),
        style=_stylesheet(theme, footer_note=note),
        header=header,
        body=body,
    )
    _write(sink, page)


def _doc_header(meta: DocMeta) -> str:
    bits = []
    if meta.reference:
        bits.append(f"<span><strong>Ref:</strong> {escape(meta.reference)}</span>")
    if meta.site_address:
        bits.append(f"<span><strong>Site:</strong> {escape(meta.site_address)}</span>")
    if meta.engineer:
        bits.append(f"<span><strong>Engineer:</strong> {escape(meta.engineer)}</span>")
    if meta.date:
        bits.append(f"<span><strong>Date:</strong> {escape(meta.date)}</span>")
    meta_row = f'<div class="header-meta">{"".join(bits)}</div>' if bits else ""
    return (
        '<div class="report-header">'
        f"<h1>{escape(meta.title)}</h1>"
        f"{meta_row}</div>"
    )


def _css_string(text: str) -> str:
    """Quote `text` as a CSS string that cannot close the <style> element."""
    return '"' + "".join(f"\\{ord(c):x} " if c in '\\"<>\n\r\f' else c for c in text) + '"'


def _stylesheet(theme: Theme, footer_note: str = "") -> str:
    """The page stylesheet. A non-empty `footer_note` adds the print rules that
    repeat it at the foot of every printed page; they set an `@page` margin, so
    they are emitted only when a note is shown, never for other documents."""
    css = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: {theme.html_font_family}; font-size: 10pt; line-height: 1.5; color: {theme.text}; background: #fff; }}
.report-container {{ max-width: 210mm; margin: 0 auto; padding: 10mm; }}
.report-header {{ background: {theme.primary}; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
.report-header h1 {{ font-size: 20pt; margin-bottom: 5px; }}
.header-meta {{ display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-top: 12px; font-size: 9pt; }}
h2 {{ color: {theme.primary}; font-size: 14pt; border-bottom: 2px solid {theme.primary}; padding-bottom: 5px; margin: 25px 0 15px; }}
h3 {{ color: {theme.primary}; font-size: 11pt; margin: 20px 0 10px; }}
.status-banner {{ text-align: center; padding: 20px; border-radius: 8px; margin: 20px 0; }}
.status-banner.pass {{ background: {theme.ok_bg}; border: 2px solid {theme.ok}; }}
.status-banner.fail {{ background: {theme.fail_bg}; border: 2px solid {theme.fail}; }}
.status-banner h2 {{ font-size: 16pt; border-bottom: none; margin-bottom: 5px; }}
.status-badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 9pt; font-weight: bold; }}
.status-badge-large {{ padding: 5px 15px; border-radius: 20px; font-size: 11pt; }}
.status-pass {{ background: {theme.ok}; color: #fff; }}
.status-fail {{ background: {theme.fail}; color: #fff; }}
.status-pass-outline {{ background: {theme.ok_bg}; color: {theme.ok}; border: 1px solid {theme.ok}; }}
.status-fail-outline {{ background: {theme.fail_bg}; color: {theme.fail}; border: 1px solid {theme.fail}; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 15px 0; }}
.summary-card {{ background: {theme.row_alt}; border: 1px solid {theme.border}; border-radius: 6px; padding: 12px; text-align: center; }}
.summary-card .label {{ font-size: 8pt; color: {theme.muted}; text-transform: uppercase; }}
.summary-card .value {{ font-size: 14pt; font-weight: bold; color: {theme.primary}; margin: 5px 0; }}
.summary-card .detail {{ font-size: 8pt; color: {theme.muted}; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9pt; }}
th {{ background: {theme.primary}; color: #fff; padding: 8px 6px; text-align: left; }}
td {{ padding: 6px; border-bottom: 1px solid #ddd; }}
tr:nth-child(even) td {{ background: {theme.row_alt}; }}
td.right {{ text-align: right; font-family: 'Consolas', 'Monaco', monospace; }}
td.center {{ text-align: center; }}
tr.fail td {{ background: {theme.fail_bg}; }}
figure.diagram {{ margin: 12px 0; text-align: center; }}
figure.diagram svg, figure.diagram img {{ max-width: 100%; height: auto; }}
figure.diagram figcaption {{ font-size: 8pt; color: {theme.muted}; margin-top: 4px; }}
.diagram-grid {{ display: grid; grid-template-columns: repeat(var(--cols, 3), 1fr); gap: 10px; margin: 12px 0; align-items: start; }}
.diagram-grid figure.diagram {{ margin: 0; }}
.calc-block {{ margin: 10px 0; border-left: 3px solid {theme.border}; padding-left: 10px; }}
.calc-title {{ font-weight: bold; color: {theme.primary}; margin-bottom: 4px; }}
.calc-row {{ display: grid; grid-template-columns: 26% 1fr auto; gap: 8px; align-items: baseline; padding: 2px 0; border-bottom: 1px solid #eee; }}
.calc-label {{ color: {theme.muted}; }}
.calc-work {{ font-family: 'Consolas', 'Monaco', monospace; font-size: 9pt; }}
.calc-ref {{ color: {theme.muted}; font-size: 8pt; white-space: nowrap; }}
.page-break {{ page-break-before: always; }}
.footer-note {{ color: {theme.muted}; font-size: 8pt; font-style: italic; margin: -8px 0 20px; padding: 4px 10px; border-left: 3px solid {theme.border}; }}
.signoff {{ margin: 20px 0; padding: 14px 16px; border: 1px solid {theme.border}; border-radius: 6px; background: {theme.row_alt}; page-break-inside: avoid; break-inside: avoid; }}
.signoff-title {{ font-size: 11pt; font-weight: bold; color: {theme.primary}; margin-bottom: 8px; }}
.signoff-conditions {{ margin: 0 0 12px 18px; }}
.signoff-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }}
.signoff-label {{ font-weight: bold; }}
.signoff-line {{ height: 36px; border-bottom: 1px solid {theme.text}; margin-bottom: 6px; }}
.info-grid {{ display: grid; grid-template-columns: repeat(var(--cols, 2), 1fr); gap: 12px; margin: 12px 0; align-items: start; }}
.info-card {{ border: 1px solid {theme.border}; border-radius: 6px; padding: 8px 10px; margin: 10px 0; break-inside: avoid; }}
.info-grid .info-card {{ margin: 0; }}
.info-card-title {{ font-weight: bold; color: {theme.primary}; border-bottom: 2px solid {theme.primary}; padding-bottom: 4px; }}
.info-card table {{ margin: 0; }}
.info-card td {{ padding: 3px 4px; }}
.info-card td:first-child {{ width: 40%; }}
.design-check-table td:nth-child(4) {{ width: 24%; }}
.util-cell {{ display: flex; align-items: center; gap: 6px; }}
.util-bar {{ flex: 1; height: 8px; background: {theme.border}; border-radius: 4px; overflow: hidden; }}
.util-fill {{ height: 100%; border-radius: 4px; }}
.util-fill.ok {{ background: {theme.ok}; }}
.util-fill.warn {{ background: {theme.warn}; }}
.util-fill.fail {{ background: {theme.fail}; }}
.util-pct {{ font-family: 'Consolas', 'Monaco', monospace; font-size: 9pt; min-width: 4.5em; text-align: right; }}
@media print {{
  body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .report-container {{ padding: 0; }}
  .no-print {{ display: none; }}
}}
"""
    if footer_note:
        # A page margin box, not `position: fixed`: Chrome measures fixed offsets
        # from the page content area, so a fixed note covers the last line of each
        # page, and one pushed down into the margin lands on the next page instead.
        # The in-page .footer-note is deliberately NOT hidden in print: only Chrome
        # (131+) supports page margin boxes, so in Firefox and Safari it is the only
        # copy of the caveat on paper. Chrome shows it twice on page 1; that is fine.
        css += f"""@page {{
  margin-bottom: 22mm;
  @bottom-left {{ content: {_css_string(footer_note)}; font-family: {theme.html_font_family}; font-size: 6.5pt; color: {theme.muted}; vertical-align: top; padding-top: 2mm; border-top: 1px solid {theme.border}; }}
}}
"""
    return css


def _write(sink, text: str) -> None:
    if isinstance(sink, (str, Path)):
        Path(sink).write_text(text, encoding="utf-8")
    else:
        sink.write(text)
