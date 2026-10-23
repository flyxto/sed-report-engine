"""The HTTP contract the Node backend calls.

Handlers are called directly. Starlette's TestClient needs httpx, which this
environment does not install (same approach as sed_reporting/tests/test_api.py).
"""

from sed_report_engine.app import GenerateBody, app, run_report
from sed_report_engine.tests.test_mapper import portal_project


def test_routes():
    routes = {(path, method.upper()) for path, ops in app.openapi()["paths"].items() for method in ops}
    assert ("/health", "GET") in routes
    assert ("/v1/reports/{kind}/{action}", "POST") in routes


def test_preview_returns_html_and_the_gaps():
    response = run_report("scr", "preview", GenerateBody(project=portal_project()))
    assert response["html"]
    assert "Hill House" in response["html"]
    assert response["issues"]
    assert "Hill House" in response["html"]
    assert "EQSE" in response["html"] or "Earthquake" in response["html"]


def test_pdf_is_a_draft_while_errors_remain():
    response = run_report("scr", "pdf", GenerateBody(project=portal_project()))
    assert response.status_code == 200
    assert response.body.startswith(b"%PDF")
    assert response.headers["x-report-draft"] == "true"
