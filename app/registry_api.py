from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .catalog import LocalTestCatalog
from .database import Database
from .form_assets import FormAssetSource
from .models import OrderCreate, Patient, PurgeRequest
from .orders import render_order_documents, required_template_ids
from .repository import TemplateSource
from .summary import render_patient_summary


def create_registry_router(database: Database, catalog: LocalTestCatalog, source: TemplateSource, asset_source: FormAssetSource) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/catalog")
    def list_catalog():
        try:
            return [lab.model_dump() for lab in catalog.list_labs()]
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Catalog error: {exc}") from exc

    @router.get("/patients")
    def list_patients():
        return database.list_patients()

    @router.post("/patients", status_code=201)
    def create_patient(patient: Patient):
        return database.create_patient(patient)

    @router.get("/patients/{patient_id}")
    def get_patient(patient_id: int):
        patient = database.get_patient(patient_id)
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient

    @router.put("/patients/{patient_id}")
    def update_patient(patient_id: int, patient: Patient):
        updated = database.update_patient(patient_id, patient)
        if updated is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        return updated

    @router.delete("/patients/{patient_id}", status_code=204)
    def delete_patient(patient_id: int):
        if not database.delete_patient(patient_id):
            raise HTTPException(status_code=404, detail="Patient not found")
        return Response(status_code=204)

    @router.get("/patients/{patient_id}/orders")
    def list_orders(patient_id: int):
        if database.get_patient(patient_id) is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        return database.list_orders(patient_id)

    @router.post("/patients/{patient_id}/orders", status_code=201)
    def create_order(patient_id: int, request: OrderCreate):
        if database.get_patient(patient_id) is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        try:
            tests = catalog.resolve(request.test_ids)
            available = {template.id for template in source.list_templates()} | asset_source.list_asset_ids()
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        missing = required_template_ids(tests) - available
        if missing:
            raise HTTPException(status_code=422, detail=f"Request form unavailable: {', '.join(sorted(missing))}")
        return database.create_order(patient_id, request, tests)

    @router.delete("/patients/{patient_id}/orders/{order_id}", status_code=204)
    def delete_order(patient_id: int, order_id: int):
        if not database.delete_order(patient_id, order_id):
            raise HTTPException(status_code=404, detail="Order not found")
        return Response(status_code=204)

    @router.get("/orders/{order_id}/documents")
    def download_order_documents(order_id: int):
        order = database.get_order(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        patient = database.get_patient(order["patient_id"])
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        try:
            documents = render_order_documents(order, patient, source, asset_source)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        if len(documents) == 1:
            filename, content = documents[0]
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            return Response(content, media_type="application/pdf", headers=headers)
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for filename, content in documents:
                archive.writestr(filename, content)
        headers["Content-Disposition"] = f'attachment; filename="{patient["code"]}-order-{order_id}.zip"'
        return Response(buffer.getvalue(), media_type="application/zip", headers=headers)

    @router.get("/summary.pdf")
    def patient_summary():
        patients = database.list_patients()
        orders = {patient["id"]: database.list_orders(patient["id"]) for patient in patients}
        content = render_patient_summary(patients, orders)
        return Response(content, media_type="application/pdf", headers={
            "Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="patient-summary.pdf"',
        })

    @router.get("/maintenance/purge-preview")
    def purge_preview(older_than_days: int):
        if not 1 <= older_than_days <= 3650:
            raise HTTPException(status_code=422, detail="Days must be between 1 and 3650")
        return {"count": database.purge_preview(older_than_days)}

    @router.post("/maintenance/purge")
    def purge(request: PurgeRequest):
        return {"deleted": database.purge(request.older_than_days)}

    return router
