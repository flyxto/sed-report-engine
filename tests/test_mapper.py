"""The portal's project shape survives the trip into sed_reporting."""

import json
from pathlib import Path

from sed_report_engine.generate import generate
from sed_report_engine.mapper import to_project
from sed_reporting.project_data.project import Project

SAMPLE = Path(__file__).resolve().parents[2] / "sed_reporting" / "data" / "project_sample.json"


def portal_project() -> dict:
    """A project in the shape the Node backend returns today."""
    return {
        "id": "8",
        "projectId": "P260802",
        "project_id": "P260802",
        "name": "Hill House",
        "projectName": "Hill House",
        "projectDescription": "Single-storey extension",
        "address": "12 Example Road, Kelburn, Wellington 6012",
        "siteAddress": "12 Example Road, Kelburn, Wellington 6012",
        "legalDescription": "Lot 2 DP 99999",
        "territorialAuthority": "auckland-council",
        "status": "Element Design",
        "buildingConsentNumber": "BC-1",
        "client": {
            "id": "3",
            "name": "Alex Client",
            "email": "alex@example.com",
            "phoneNumber": "+64 21 000 0000",
            "companyName": None,
        },
        "builder": {"id": "9", "name": "Example Builders Ltd"},
        "internalReviewingEngineer": {
            "name": "Sam Engineer",
            "handle": "sam@sed.works",
            "avatarUrl": "https://example.com/a.png",
        },
        "structural": {
            "ulsBearing": 150,
            "windZone": "High",
            "snowZone": "N0",
            "snowElevation": None,
        },
        "assemblies": [
            {
                "id": "4",
                "category": "WALL",
                "code": "W1",
                "name": "90mm stud wall",
                "frameSpacing": 600,
                "materials": [{"name": "Gib"}],
                "calculatedTotalWeight": "0.42",
            },
            {"id": "5", "category": "OTHER", "name": "skip me"},
        ],
        "elements": [
            {
                "id": "15",
                "type": "Gabel Portal Frame",
                "elementCode": "PF-01",
                "description": "Living room frame",
                "designResults": {
                    "structural_report_url": "https://files.example.com/pf.pdf",
                },
            },
            {
                "id": "16",
                "type": "Beams",
                "description": "",
                "elementCode": "B-01",
            },
            {
                "id": "17",
                "type": "Mystery Wall",
                "description": "not a library type",
            },
        ],
        "drawings": [{"fileName": "ignored.pdf"}],
    }


def test_portal_shape_validates_and_maps_element_types():
    mapped, notes = to_project(portal_project())
    project = Project.model_validate(mapped)

    assert project.territorial_authority == "Auckland Council"
    assert project.project_id == "P260802"
    assert project.name == "Hill House"
    assert project.ps1_certificate_data is not None
    assert project.ps1_certificate_data.issuer == "Earthquake & Structural Engineering Consultants Limited"
    assert project.ps1_certificate_data.issuer_short_name == "EQSE"
    assert project.reports.ps1.revisions[0].description == "Building Consent"
    assert project.site_street_address == "12 Example Road"
    assert project.site_suburb == "Kelburn"
    assert project.site_town_city == "Wellington"
    assert project.site_postcode == "6012"
    assert project.client.phone == "+64 21 000 0000"
    assert project.structural.uls_bearing == "150"
    assert [a.name for a in project.assemblies] == ["90mm stud wall"]
    assert [(e.id, e.type, e.description) for e in project.elements] == [
        (15, "PF2", "Living room frame"),
        (16, "TB1", "B-01"),
    ]
    assert project.elements[0].calculation_report_url == "https://files.example.com/pf.pdf"
    assert project.elements[1].calculation_report_url is None
    assert any("Mystery Wall" in note for note in notes)
    assert any("assembly 2" in note for note in notes)
    assert "drawings" not in mapped
    cert = project.ps1_certificate_data
    assert cert.issuer_phone == "+64 9 000 1111"
    assert cert.issuer_phone_after_hours == "+64 9 000 1111"
    assert cert.issuer_address == "Level 5, 1 Queen Street, Auckland"
    assert cert.issuer_postal_address == "Level 5, 1 Queen Street, Auckland"
    assert cert.issuer_website == "www.eqse.nz"
    assert cert.issuer_pi_insurance_nzd == 200000
    assert cert.issuer_ace_nz_member is False


def test_engineer_and_drawing_review_clear_the_last_ps1_notes():
    raw = portal_project()
    raw["internalReviewingEngineer"] = {
        **raw["internalReviewingEngineer"],
        "position": "Senior Structural Engineer",
        "charteredStatus": "Chartered Professional Engineer",
        "cpengNumber": "1234567",
        "qualifications": ["BE (Hons)"],
        "mobile": "+64 21 000 0000",
        "signatureUrl": "https://example.com/sig.png",
    }
    raw["drawingReviews"] = [{"completedAt": "2026-10-24T12:00:00Z"}]

    preview = generate("ps1", "preview", raw)
    messages = [issue["message"] for issue in preview.issues]

    assert not any("internalReviewingEngineer" in message for message in messages)
    assert not any("ps1CertificateData" in message for message in messages)
    assert not any("drawing set" in message and "completed review" in message for message in messages)


def test_sample_project_passes_through_and_previews():
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    preview = generate("scr", "preview", raw)

    assert "Smith Residence Extension" in preview.html
    assert isinstance(preview.issues, list)
    assert isinstance(preview.form, dict)


def test_draft_pdf_is_created_while_details_are_missing():
    pdf = generate("ps1", "pdf", portal_project())
    assert pdf.body.startswith(b"%PDF")


def test_issuing_stays_blocked_while_details_are_missing():
    from sed_report_engine.errors import EngineError
    import pytest

    with pytest.raises(EngineError) as caught:
        generate("ps1", "issue", portal_project())
    assert caught.value.status == 422
    assert caught.value.issues
