import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader, PdfWriter


@dataclass(frozen=True)
class FormAsset:
    id: str
    pdf_bytes: bytes
    field_map: dict[str, str]


class FormAssetSource(Protocol):
    def list_asset_ids(self) -> set[str]: ...

    def get_asset(self, form_id: str) -> FormAsset | None: ...


class LocalFormAssetSource:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _manifest(self) -> dict[str, dict]:
        path = self.directory / "manifest.json"
        if not path.exists():
            return {}
        with path.open(encoding="utf-8") as handle:
            entries = json.load(handle).get("forms", [])
        forms = {}
        for item in entries:
            form_id = item["id"]
            if form_id in forms:
                raise ValueError(f"Duplicate form asset ID: {form_id}")
            filename = item["filename"]
            if Path(filename).name != filename or Path(filename).suffix.lower() != ".pdf":
                raise ValueError(f"Invalid form asset filename: {filename}")
            field_map = item.get("fields", {})
            if not isinstance(field_map, dict) or not field_map or not all(isinstance(key, str) and isinstance(value, str) and value for key, value in field_map.items()):
                raise ValueError(f"Invalid field map for form: {form_id}")
            forms[form_id] = item
        return forms

    def list_asset_ids(self) -> set[str]:
        entries = self._manifest()
        for item in entries.values():
            path = (self.directory / item["filename"]).resolve()
            if not path.is_relative_to(self.directory.resolve()) or not path.is_file():
                raise ValueError(f"Form asset file missing or outside directory: {item['filename']}")
        return set(entries)

    def get_asset(self, form_id: str) -> FormAsset | None:
        item = self._manifest().get(form_id)
        if item is None:
            return None
        path = (self.directory / item["filename"]).resolve()
        if not path.is_relative_to(self.directory.resolve()):
            raise ValueError("Form asset path escapes its directory")
        if not path.is_file():
            raise ValueError(f"Form asset file missing: {item['filename']}")
        return FormAsset(form_id, path.read_bytes(), item["fields"])


def fill_pdf_asset(asset: FormAsset, values: dict[str, str]) -> bytes:
    reader = PdfReader(BytesIO(asset.pdf_bytes))
    source_fields = reader.get_fields() or {}
    if not source_fields:
        raise ValueError(f"{asset.id}: PDF has no AcroForm fields")
    if any(str(field.get("/FT")) == "/Sig" for field in source_fields.values()):
        raise ValueError(f"{asset.id}: signed forms are not supported")
    field_values = {}
    for logical_name, pdf_name in asset.field_map.items():
        if logical_name not in values:
            raise ValueError(f"{asset.id}: unknown placeholder {logical_name}")
        if pdf_name not in source_fields:
            raise ValueError(f"{asset.id}: PDF field missing: {pdf_name}")
        if str(source_fields[pdf_name].get("/FT")) != "/Tx":
            raise ValueError(f"{asset.id}: only text fields are supported: {pdf_name}")
        field_values[pdf_name] = values[logical_name]

    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.update_page_form_field_values(None, field_values, auto_regenerate=False)
    buffer = BytesIO()
    writer.write(buffer)
    content = buffer.getvalue()

    verified = PdfReader(BytesIO(content))
    updated_fields = verified.get_fields() or {}
    for name, expected in field_values.items():
        if name not in updated_fields or str(updated_fields[name].get("/V", "")) != expected:
            raise ValueError(f"{asset.id}: failed to fill PDF field: {name}")
    for page in verified.pages:
        for reference in page.get("/Annots", []):
            widget = reference.get_object()
            if str(widget.get("/Subtype")) != "/Widget":
                continue
            parent = widget.get("/Parent")
            parent = parent.get_object() if parent else None
            name = str(widget.get("/T") or (parent.get("/T") if parent else ""))
            if name not in field_values:
                continue
            value = str(widget.get("/V") or (parent.get("/V") if parent else ""))
            if value != field_values[name] or not widget.get("/AP", {}).get("/N"):
                raise ValueError(f"{asset.id}: PDF appearance not updated: {name}")
    return content
