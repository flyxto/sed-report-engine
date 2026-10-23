"""Turn a portal project into the project file `sed_reporting` validates.

The Node backend already returns a project DTO (camelCase, extra fields,
element types such as "Gabel Portal Frame"). `sed_reporting.Project` accepts
that shape, ignores unknown portal fields, and rejects a misspelt key inside
`elements`, `durability` or `reports`. This mapper:

- copies the fields the reports print
- translates the portal's element type names into library codes (PF1, PF2,
  SB1, TB1, Rafts)
- drops a block that would fail validation, and says so in `notes`, so one
  missing firm field does not stop the preview of everything else
"""

from __future__ import annotations

import re
from typing import Any

from sed_report_engine.errors import EngineError

# Portal element names → codes in sed_reporting/data/element_library.json.
_EXACT_TYPES = {
    "pf1": "PF1",
    "rectangular portal frame": "PF1",
    "flat portal frame": "PF1",
    "portal frame": "PF1",
    "pf2": "PF2",
    "gable portal frame": "PF2",
    "gabel portal frame": "PF2",  # the portal spells "gable" this way
    "gable shaped portal frame": "PF2",
    "sb1": "SB1",
    "steel beam": "SB1",
    "steel beam type 1": "SB1",
    "tb1": "TB1",
    "beam": "TB1",
    "beams": "TB1",
    "timber beam": "TB1",
    "timber beam type 1": "TB1",
    "raft": "Rafts",
    "rafts": "Rafts",
    "raft foundation": "Rafts",
    "raft foundations": "Rafts",
    "raft floor": "Rafts",
}

_ASSEMBLY_CATEGORIES = {"WALL", "ROOF", "FLOOR"}
_POSTCODE = re.compile(r"\b(\d{4})\s*$")

# Every report is issued by this engineering firm unless the portal sends another.
DEFAULT_FIRM = {
    "issuer": "Earthquake & Structural Engineering Consultants Limited",
    "issuerShortName": "EQSE",
    "issuerPhone": "+64 9 000 1111",
    "issuerPhoneAfterHours": "+64 9 000 1111",
    "issuerAddress": "Level 5, 1 Queen Street, Auckland",
    "issuerPostalAddress": "Level 5, 1 Queen Street, Auckland",
    "issuerWebsite": "www.eqse.nz",
    "issuerPiInsuranceNzd": 200000,
    "issuerAceNzMember": False,
}


def to_project(raw: dict) -> tuple[dict, list[str]]:
    """Return `(project, notes)` ready for `Project.model_validate`."""
    if not isinstance(raw, dict):
        raise EngineError(422, "project must be an object")

    notes: list[str] = []
    project_id = _text(raw.get("projectId") or raw.get("project_id"))
    name = _text(raw.get("name") or raw.get("projectName") or raw.get("project_name"))
    site = _text(raw.get("siteAddress") or raw.get("address") or raw.get("site_address"))
    client = _client(raw.get("client"))

    missing = [
        label
        for label, value in (
            ("project id", _text(raw.get("id"))),
            ("job number (projectId)", project_id),
            ("project name", name),
            ("site address", site),
            ("client", client),
        )
        if not value
    ]
    if missing:
        raise EngineError(
            422,
            "This project is missing details the report needs: " + ", ".join(missing) + ".",
        )

    street, suburb, city, postcode = _address_parts(site)
    out: dict[str, Any] = {
        "id": _text(raw.get("id")),
        "projectId": project_id,
        "name": name,
        "projectName": name,
        "projectDescription": _text(raw.get("projectDescription") or raw.get("project_description")),
        "siteAddress": site,
        "address": site,
        "siteStreetAddress": _text(raw.get("siteStreetAddress")) or street,
        "siteSuburb": _text(raw.get("siteSuburb")) or suburb,
        "siteTownCity": _text(raw.get("siteTownCity")) or city,
        "sitePostcode": _text(raw.get("sitePostcode")) or postcode,
        "legalDescription": _text(raw.get("legalDescription") or raw.get("legal_description")),
        "territorialAuthority": _council(raw.get("territorialAuthority") or raw.get("territorial_authority")),
        "status": _text(raw.get("status")),
        "buildingConsentNumber": _text(raw.get("buildingConsentNumber") or raw.get("building_consent_number")),
        "client": client,
    }

    amendments = raw.get("buildingConsentAmendments")
    if isinstance(amendments, list):
        out["buildingConsentAmendments"] = [str(a).strip() for a in amendments if str(a).strip()]

    engineer = _engineer(raw.get("internalReviewingEngineer"), notes, "reviewing engineer")
    if engineer:
        out["internalReviewingEngineer"] = engineer
    inspector = _engineer(raw.get("inspectionEngineer"), notes, "inspection engineer")
    if inspector:
        out["inspectionEngineer"] = inspector

    out["ps1CertificateData"] = _firm(raw.get("ps1CertificateData"), notes)

    structural = _structural(raw.get("structural"))
    if structural:
        out["structural"] = structural

    assemblies = _assemblies(raw.get("assemblies"), notes)
    if assemblies:
        out["assemblies"] = assemblies

    architect = _architect(raw.get("architect"))
    if architect:
        out["architect"] = architect

    builder = _builder(raw.get("builder"))
    if builder:
        out["builder"] = builder

    reviews = _drawing_reviews(raw.get("drawingReviews"), notes)
    if reviews:
        out["drawingReviews"] = reviews

    geo = _geo(raw.get("geotechnicalReport"), notes)
    if geo:
        out["geotechnicalReport"] = geo

    elements = _elements(raw.get("elements"), notes)
    if elements:
        out["elements"] = elements

    if isinstance(raw.get("durability"), dict):
        out["durability"] = raw["durability"]
    out["reports"] = _reports(raw.get("reports"))

    calc_url = raw.get("structuralCalculationReportUrl")
    if isinstance(calc_url, str) and calc_url.startswith("https://"):
        out["structuralCalculationReportUrl"] = calc_url

    return out, notes


def _reports(raw: Any) -> dict:
    """Every report starts with Rev A — Building Consent when none is stored."""
    reports = dict(raw) if isinstance(raw, dict) else {}
    for key in ("ps1", "scr"):
        block = dict(reports.get(key) or {}) if isinstance(reports.get(key), dict) else {}
        revisions = block.get("revisions")
        if not isinstance(revisions, list) or not revisions:
            block["revisions"] = [{"description": "Building Consent"}]
        reports[key] = block
    return reports


def _council(value: Any) -> str:
    """Map a portal slug such as auckland-council to the listed council name."""
    from sed_reporting.project_data.councils import load_councils

    name = _text(value)
    if not name:
        return ""
    councils = load_councils()
    if councils.find(name):
        return name
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    for council in councils.territorial_authorities:
        if re.sub(r"[^a-z0-9]+", "-", council.name.lower()).strip("-") == slug:
            return council.name
    hints = councils.suggestions(name)
    return hints[0] if len(hints) == 1 else name


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _client(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))
    ident = _text(raw.get("id"))
    if not name or not ident:
        return None
    return {
        "id": ident,
        "name": name,
        "email": _text(raw.get("email")),
        "phone": _text(raw.get("phone") or raw.get("phoneNumber")),
        "companyName": _text(raw.get("companyName") or raw.get("company_name")) or None,
        "address": _text(raw.get("address")),
    }


def _engineer(raw: Any, notes: list[str], label: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))
    if not name:
        notes.append(f"{label} was left out because it has no name")
        return None
    qualifications = raw.get("qualifications") or []
    if isinstance(qualifications, str):
        qualifications = [qualifications]
    return {
        "name": name,
        "handle": _text(raw.get("handle") or raw.get("email")),
        "position": _text(raw.get("position")),
        "charteredStatus": _text(raw.get("charteredStatus")),
        "cpengNumber": _text(raw.get("cpengNumber")),
        "qualifications": [str(q).strip() for q in qualifications if str(q).strip()],
        "mobile": _text(raw.get("mobile")),
        "signatureUrl": _https(raw.get("signatureUrl")),
    }


def _firm(raw: Any, notes: list[str]) -> dict:
    data = raw if isinstance(raw, dict) else {}
    issuer = _text(data.get("issuer")) or DEFAULT_FIRM["issuer"]
    short_name = _text(data.get("issuerShortName")) or DEFAULT_FIRM["issuerShortName"]
    cover = data.get("issuerPiInsuranceNzd")
    try:
        cover_nzd = int(cover) if cover not in (None, "") else None
    except (TypeError, ValueError):
        cover_nzd = None
        notes.append("issuerPiInsuranceNzd is not a whole number, so it was left out")
    if cover_nzd is not None and cover_nzd <= 0:
        cover_nzd = None
    ace = data.get("issuerAceNzMember")
    if not isinstance(ace, bool):
        ace = DEFAULT_FIRM["issuerAceNzMember"]
    return {
        "issuer": issuer,
        "issuerShortName": short_name,
        "issuerPhone": _text(data.get("issuerPhone")) or DEFAULT_FIRM["issuerPhone"],
        "issuerEmail": _text(data.get("issuerEmail")),
        "issuerAddress": _text(data.get("issuerAddress")) or DEFAULT_FIRM["issuerAddress"],
        "issuerPostalAddress": _text(data.get("issuerPostalAddress")) or DEFAULT_FIRM["issuerPostalAddress"],
        "issuerPhoneAfterHours": _text(data.get("issuerPhoneAfterHours")) or DEFAULT_FIRM["issuerPhoneAfterHours"],
        "issuerWebsite": _text(data.get("issuerWebsite")) or DEFAULT_FIRM["issuerWebsite"],
        "issuerPiInsuranceNzd": cover_nzd or DEFAULT_FIRM["issuerPiInsuranceNzd"],
        "issuerAceNzMember": ace,
        "issuerLogoUrl": _https(data.get("issuerLogoUrl")),
    }


def _structural(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    out = {}
    for src, dest in (
        ("ulsBearing", "ulsBearing"),
        ("windZone", "windZone"),
        ("snowZone", "snowZone"),
        ("snowElevation", "snowElevation"),
    ):
        value = raw.get(src)
        if value is None or value == "":
            continue
        out[dest] = str(value).strip()
    return out or None


def _assemblies(raw: Any, notes: list[str]) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name") or item.get("description"))
        category = _text(item.get("category") or item.get("assembly_category_type")).upper()
        if not name or category not in _ASSEMBLY_CATEGORIES:
            notes.append(f"assembly {index} was left out (it needs a name and a WALL, ROOF or FLOOR category)")
            continue
        weight = item.get("calculatedTotalWeight", item.get("calculated_total_weight_kpa"))
        try:
            weight_kpa = float(weight) if weight not in (None, "") else None
        except (TypeError, ValueError):
            weight_kpa = None
        out.append({
            "id": _text(item.get("id")) or str(index),
            "category": category,
            "code": _text(item.get("code")),
            "name": name,
            "calculatedTotalWeight": weight_kpa,
        })
    return out


def _architect(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    company = _text(raw.get("companyName"))
    name = _text(raw.get("name"))
    if not company and not name:
        return None
    return {"companyName": company, "name": name}


def _builder(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))
    ident = _text(raw.get("id"))
    if not name and not ident:
        return None
    return {"id": ident, "name": name}


def _drawing_reviews(raw: Any, notes: list[str]) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        completed = _text(item.get("completedAt"))
        if not completed:
            notes.append(f"drawing review {index} was left out because completedAt is empty")
            continue
        if re.fullmatch(r".*[+-]\d\d:\d\d|.*Z", completed) is None and "T" in completed:
            completed += "Z"
        out.append({"completedAt": completed})
    return out


def _geo(raw: Any, notes: list[str]) -> dict | None:
    if not isinstance(raw, dict):
        return None
    author = _text(raw.get("authorCompany"))
    if not author:
        notes.append("geotechnical report was left out because authorCompany is empty")
        return None
    return {
        "authorCompany": author,
        "reference": _text(raw.get("reference")),
        "revision": _text(raw.get("revision")),
        "issueDate": _text(raw.get("issueDate")) or None,
        "fileUrl": _https(raw.get("fileUrl")),
    }


def _elements(raw: Any, notes: list[str]) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        code, _type_note = _element_type(item.get("type") or item.get("element_type"))
        ident = item.get("id")
        try:
            element_id = int(ident)
        except (TypeError, ValueError):
            notes.append(f"element {index} was left out because its id is not a number")
            continue
        if not code:
            notes.append(f"element {element_id} ({_text(item.get('type')) or 'no type'}) was left out: {_element_type_help()}")
            continue
        description = _text(item.get("description") or item.get("elementCode") or item.get("name") or code)
        url = _calculation_url(item)
        out.append({
            "id": element_id,
            "type": code,
            "description": description,
            "calculationReportUrl": url,
        })
    return out


def _element_type(value: Any) -> tuple[str, str]:
    """Return `(library code, note)`. The note is set when the name was translated."""
    label = _text(value)
    if not label:
        return "", ""
    key = label.lower()
    if key in _EXACT_TYPES:
        code = _EXACT_TYPES[key]
        note = "" if code == label else f"type {label!r} sent to the report as {code}"
        return code, note
    if "portal" in key and "gab" in key:
        return "PF2", f"type {label!r} sent to the report as PF2"
    if "portal" in key:
        return "PF1", f"type {label!r} sent to the report as PF1"
    if "beam" in key and "steel" in key:
        return "SB1", f"type {label!r} sent to the report as SB1"
    if "beam" in key:
        return "TB1", f"type {label!r} sent to the report as TB1"
    if "raft" in key:
        return "Rafts", f"type {label!r} sent to the report as Rafts"
    if label in {"PF1", "PF2", "SB1", "TB1", "Rafts"}:
        return label, ""
    return "", ""


def _element_type_help() -> str:
    return "its type is not a library code (PF1, PF2, SB1, TB1, Rafts) or a portal name such as Flat Portal Frame, Gabel Portal Frame, Beams or Raft"


def _calculation_url(item: dict) -> str | None:
    candidates = [item.get("calculationReportUrl")]
    results = item.get("designResults") or item.get("design_results") or {}
    if isinstance(results, dict):
        candidates.extend([
            results.get("structural_report_url"),
            results.get("structuralReportUrl"),
            results.get("combined_report_url"),
        ])
    for candidate in candidates:
        url = _https(candidate)
        if url:
            return url
    return None


def _https(value: Any) -> str:
    text = _text(value)
    return text if text.startswith("https://") else ""


def _address_parts(address: str) -> tuple[str, str, str, str]:
    """Best-effort split of the one-line site address. Explicit parts win later."""
    postcode = ""
    match = _POSTCODE.search(address)
    rest = address
    if match:
        postcode = match.group(1)
        rest = address[: match.start()].strip(" ,")
    parts = [part.strip() for part in rest.split(",") if part.strip()]
    if not parts:
        return address, "", "", postcode
    street = parts[0]
    city = parts[-1] if len(parts) > 1 else ""
    suburb = ", ".join(parts[1:-1]) if len(parts) > 2 else ""
    return street, suburb, city, postcode
