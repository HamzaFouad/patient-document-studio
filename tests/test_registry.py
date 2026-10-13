import sqlite3
import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.form_assets import LocalFormAssetSource
from app.main import create_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "patients.sqlite3"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(database_path=db_path))


def add_patient(client, name="Alex Morgan"):
    response = client.post("/api/patients", json={"name": name, "age": 42, "medical_history": "Asthma"})
    assert response.status_code == 201
    return response.json()


def test_patient_registry_persists_and_codes_are_stable(client, db_path):
    first = add_patient(client)
    second = add_patient(client, "Sam Lee")
    assert first["code"] == "P-000001"
    assert second["code"] == "P-000002"
    assert [patient["name"] for patient in client.get("/api/patients").json()] == ["Sam Lee", "Alex Morgan"]
    restarted = TestClient(create_app(database_path=db_path))
    assert restarted.get(f"/api/patients/{first['id']}").json()["medical_history"] == "Asthma"
    assert restarted.delete(f"/api/patients/{first['id']}").status_code == 204
    third = add_patient(restarted, "Jordan Kim")
    assert third["code"] == "P-000003"


def test_order_catalog_and_grouped_forms(client):
    patient = add_patient(client)
    catalog = client.get("/api/catalog").json()
    assert len(catalog) >= 2
    assert all(lab["tests"] for lab in catalog)
    response = client.post(f"/api/patients/{patient['id']}/orders", json={
        "test_ids": ["cbc", "crp", "brca-panel"],
        "doctor_name": "Dr. Sam Lee",
        "clinical_question": "Investigate symptoms",
        "copies": 2,
    })
    assert response.status_code == 201
    order = response.json()
    assert len(order["tests"]) == 3
    assert len(client.get(f"/api/patients/{patient['id']}/orders").json()) == 1

    bundle = client.get(f"/api/orders/{order['id']}/documents")
    assert bundle.status_code == 200
    assert bundle.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(bundle.content)) as archive:
        assert len(archive.namelist()) == 4  # two request forms, two copies each
        texts = ["\n".join(page.extract_text() for page in PdfReader(BytesIO(archive.read(name))).pages) for name in archive.namelist()]
    assert any("Complete blood count" in text and "C-reactive protein" in text for text in texts)
    assert any("BRCA panel" in text for text in texts)
    assert all("Alex Morgan" in text and "P-000001" in text for text in texts)


def test_one_form_one_copy_downloads_pdf(client):
    patient = add_patient(client)
    order = client.post(f"/api/patients/{patient['id']}/orders", json={
        "test_ids": ["cbc", "crp"], "doctor_name": "Dr. Sam Lee", "clinical_question": "Screening", "copies": 1,
    }).json()
    response = client.get(f"/api/orders/{order['id']}/documents")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_order_only_needs_selected_tests(client):
    patient = add_patient(client)
    response = client.post(f"/api/patients/{patient['id']}/orders", json={"test_ids": ["cbc"]})
    assert response.status_code == 201
    document = client.get(f"/api/orders/{response.json()['id']}/documents")
    assert document.status_code == 200
    assert document.content.startswith(b"%PDF")


def test_invalid_order_is_rejected_without_saving(client):
    patient = add_patient(client)
    response = client.post(f"/api/patients/{patient['id']}/orders", json={
        "test_ids": ["missing-test"], "doctor_name": "Dr. Sam Lee", "clinical_question": "Screening", "copies": 1,
    })
    assert response.status_code == 422
    assert client.get(f"/api/patients/{patient['id']}/orders").json() == []


def test_summary_lists_patients_and_orders(client):
    first = add_patient(client)
    add_patient(client, "Sam Lee")
    client.post(f"/api/patients/{first['id']}/orders", json={
        "test_ids": ["cbc"], "doctor_name": "Dr. Sam Lee", "clinical_question": "Screening", "copies": 1,
    })
    response = client.get("/api/summary.pdf")
    assert response.status_code == 200
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    assert "P-000001" in text and "P-000002" in text
    assert "Alex Morgan" in text and "Sam Lee" in text
    assert "Complete blood count" in text


def test_cleanup_removes_old_patients_and_their_orders(client, db_path):
    old = add_patient(client)
    recent = add_patient(client, "Recent Patient")
    client.post(f"/api/patients/{old['id']}/orders", json={
        "test_ids": ["cbc"], "doctor_name": "Dr. Sam Lee", "clinical_question": "Screening", "copies": 1,
    })
    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE patients SET created_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (old["id"],))
    preview = client.get("/api/maintenance/purge-preview?older_than_days=30").json()
    assert preview["count"] == 1
    result = client.post("/api/maintenance/purge", json={"older_than_days": 30})
    assert result.status_code == 200 and result.json()["deleted"] == 1
    assert client.get(f"/api/patients/{old['id']}").status_code == 404
    assert client.get("/api/patients").json()[0]["id"] == recent["id"]


def test_local_fillable_pdf_can_replace_generated_request_form(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    pdf_path = assets / "lab.pdf"
    pdf = canvas.Canvas(str(pdf_path))
    pdf.drawString(72, 740, "Local laboratory request")
    for index, field_name in enumerate(["PatientName", "PatientCode", "Tests", "Question"]):
        pdf.acroForm.textfield(name=field_name, x=72, y=680 - index * 55, width=380, height=30)
    pdf.save()
    (assets / "manifest.json").write_text(json.dumps({"forms": [{
        "id": "lab-request", "filename": "lab.pdf",
        "fields": {
            "patient.name": "PatientName", "patient.code": "PatientCode",
            "fields.tests_requested": "Tests", "fields.clinical_question": "Question",
        },
    }]}), encoding="utf-8")
    local = TestClient(create_app(database_path=tmp_path / "patients.sqlite3", form_asset_source=LocalFormAssetSource(assets)))
    patient = add_patient(local)
    order = local.post(f"/api/patients/{patient['id']}/orders", json={
        "test_ids": ["cbc", "crp"], "doctor_name": "Dr. Sam Lee", "clinical_question": "Screening", "copies": 1,
    }).json()
    response = local.get(f"/api/orders/{order['id']}/documents")
    assert response.status_code == 200
    fields = PdfReader(BytesIO(response.content)).get_fields()
    assert fields["PatientName"]["/V"] == "Alex Morgan"
    assert fields["PatientCode"]["/V"] == "P-000001"
    assert "Complete blood count" in fields["Tests"]["/V"]
    assert "C-reactive protein" in fields["Tests"]["/V"]
