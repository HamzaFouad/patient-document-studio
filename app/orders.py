from collections import OrderedDict
from datetime import date

from .form_assets import FormAssetSource, fill_pdf_asset
from .models import Doctor, GenerateRequest, Patient
from .render import render_pdf
from .repository import TemplateSource


def required_template_ids(tests: list[dict]) -> set[str]:
    return {test["template_id"] for test in tests}


def render_order_documents(order: dict, patient: dict, source: TemplateSource, asset_source: FormAssetSource) -> list[tuple[str, bytes]]:
    groups: OrderedDict[tuple[str, str], list[dict]] = OrderedDict()
    for test in order["tests"]:
        groups.setdefault((test["lab_id"], test["template_id"]), []).append(test)

    documents = []
    for (lab_id, template_id), tests in groups.items():
        values = {
            "patient.name": patient["name"], "patient.code": patient["code"],
            "patient.age": str(patient["age"]), "patient.medical_history": patient["medical_history"],
            "doctor.name": order["doctor_name"], "today": date.today().isoformat(),
            "fields.tests_requested": "\n".join(test["name"] for test in tests),
            "fields.clinical_question": order["clinical_question"], "fields.lab_name": tests[0]["lab_name"],
        }
        asset = asset_source.get_asset(template_id)
        template = source.get_template(template_id) if asset is None else None
        if asset is None and template is None:
            raise ValueError(f"Request form unavailable: {template_id}")
        request = GenerateRequest(
            patient=Patient(name=patient["name"], age=patient["age"], medical_history=patient["medical_history"], code=patient["code"]),
            doctor=Doctor(name=order["doctor_name"] or "—"),
            template_ids=[template_id],
            fields={template_id: {
                "tests_requested": values["fields.tests_requested"],
                "clinical_question": order["clinical_question"],
                "lab_name": tests[0]["lab_name"],
            }},
        )
        content = fill_pdf_asset(asset, values) if asset else render_pdf(template, request)
        stem = f"{patient['code']}-order-{order['id']}-{lab_id}-{template_id}"
        for copy in range(1, order["copies"] + 1):
            suffix = f"-copy-{copy}" if order["copies"] > 1 else ""
            documents.append((f"{stem}{suffix}.pdf", content))
    return documents
