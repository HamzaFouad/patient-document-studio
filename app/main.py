import os
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .models import GenerateRequest
from .render import render_pdf
from .repository import LocalTemplateSource, TemplateSource


ROOT = Path(__file__).resolve().parent.parent


def create_app(template_source: TemplateSource | None = None) -> FastAPI:
    source = template_source or LocalTemplateSource(Path(os.environ.get("TEMPLATE_DIR", ROOT / "templates")))
    app = FastAPI(title="Patient Document Studio", docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")

    @app.get("/")
    def home():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/api/templates")
    def list_templates():
        try:
            return [item.model_dump(exclude={"blocks"}) for item in source.list_templates()]
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Template source error: {exc}") from exc

    @app.post("/api/generate")
    def generate(request: GenerateRequest):
        try:
            catalog = {item.id: item for item in source.list_templates()}
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Template source error: {exc}") from exc

        missing = [template_id for template_id in request.template_ids if template_id not in catalog]
        if missing:
            raise HTTPException(status_code=404, detail=f"Unknown template: {', '.join(missing)}")

        selected = [catalog[template_id] for template_id in request.template_ids]
        for template in selected:
            for field in template.fields:
                if field.required and not request.fields.get(template.id, {}).get(field.key, "").strip():
                    raise HTTPException(status_code=422, detail=f"{template.title}: {field.label} is required")

        try:
            files = [(f"{template.id}.pdf", render_pdf(template, request)) for template in selected]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        if len(files) == 1:
            filename, content = files[0]
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            return Response(content, media_type="application/pdf", headers=headers)

        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for filename, content in files:
                archive.writestr(filename, content)
        headers["Content-Disposition"] = 'attachment; filename="patient-documents.zip"'
        return Response(buffer.getvalue(), media_type="application/zip", headers=headers)

    return app


app = create_app()
