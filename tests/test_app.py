import json
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import create_app
from app.repository import LocalTemplateSource


def payload(template_ids=None):
    return {
        "patient": {"name": "Alex Morgan", "age": 42, "medical_history": "Asthma; no prior surgery"},
        "doctor": {"name": "Dr. Sam Lee"},
        "template_ids": template_ids or ["patient-intake"],
        "fields": {
            "patient-intake": {"chief_complaint": "Persistent cough"},
            "lab-request": {"tests_requested": "CBC", "clinical_question": "Check anemia"},
            "consultation-referral": {"specialty": "Pulmonology", "referral_reason": "Worsening symptoms"},
        },
    }


def test_catalog_lists_local_templates():
    client = TestClient(create_app())
    response = client.get("/api/templates")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {"patient-intake", "lab-request", "consultation-referral"}
    assert all("blocks" not in item for item in response.json())


def test_single_template_generates_filled_pdf():
    client = TestClient(create_app())
    response = client.post("/api/generate", json=payload())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Alex Morgan" in text
    assert "Persistent cough" in text
    assert "Dr. Sam Lee" in text
    assert "{{" not in text


def test_multiple_templates_generate_zip():
    client = TestClient(create_app())
    response = client.post("/api/generate", json=payload(["patient-intake", "lab-request", "consultation-referral"]))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"patient-intake.pdf", "lab-request.pdf", "consultation-referral.pdf"}
        assert all(archive.read(name).startswith(b"%PDF") for name in archive.namelist())


def test_missing_required_template_field_is_rejected():
    client = TestClient(create_app())
    data = payload(["lab-request"])
    data["fields"]["lab-request"]["clinical_question"] = " "
    response = client.post("/api/generate", json=data)
    assert response.status_code == 422
    assert "Clinical question is required" in response.json()["detail"]


def test_unknown_template_is_rejected():
    client = TestClient(create_app())
    response = client.post("/api/generate", json=payload(["does-not-exist"]))
    assert response.status_code == 404


def test_template_source_can_be_swapped(tmp_path):
    template = {
        "id": "custom-form", "title": "Custom Form", "category": "Forms", "description": "Injected source",
        "fields": [], "blocks": [{"type": "paragraph", "text": "Patient: {{ patient.name }}"}],
    }
    (tmp_path / "custom.json").write_text(json.dumps(template), encoding="utf-8")
    client = TestClient(create_app(LocalTemplateSource(tmp_path)))
    catalog = client.get("/api/templates").json()
    assert [item["id"] for item in catalog] == ["custom-form"]
    response = client.post("/api/generate", json=payload(["custom-form"]))
    assert response.status_code == 200
    assert "Alex Morgan" in PdfReader(BytesIO(response.content)).pages[0].extract_text()


def test_template_with_unknown_placeholder_fails_clearly(tmp_path):
    template = {
        "id": "broken-form", "title": "Broken Form", "category": "Forms", "description": "",
        "fields": [], "blocks": [{"type": "paragraph", "text": "{{ fields.missing }}"}],
    }
    (tmp_path / "broken.json").write_text(json.dumps(template), encoding="utf-8")
    client = TestClient(create_app(LocalTemplateSource(tmp_path)))
    response = client.post("/api/generate", json=payload(["broken-form"]))
    assert response.status_code == 422
    assert "Unknown placeholder" in response.json()["detail"]


def test_long_history_flows_across_pages():
    client = TestClient(create_app())
    data = payload()
    data["patient"]["medical_history"] = "History. " * 500
    response = client.post("/api/generate", json=data)
    assert response.status_code == 200
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) >= 2
    assert "History." in reader.pages[-1].extract_text()
