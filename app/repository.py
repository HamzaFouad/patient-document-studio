import json
from pathlib import Path
from typing import Protocol

from .models import DocumentTemplate


class TemplateSource(Protocol):
    """Return source-independent document templates."""

    def list_templates(self) -> list[DocumentTemplate]: ...

    def get_template(self, template_id: str) -> DocumentTemplate | None: ...


class LocalTemplateSource:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def list_templates(self) -> list[DocumentTemplate]:
        templates: list[DocumentTemplate] = []
        seen: set[str] = set()
        for path in sorted(self.directory.glob("*.json")):
            with path.open(encoding="utf-8") as handle:
                template = DocumentTemplate.model_validate(json.load(handle))
            if template.id in seen:
                raise ValueError(f"Duplicate template ID: {template.id}")
            seen.add(template.id)
            templates.append(template)
        return templates

    def get_template(self, template_id: str) -> DocumentTemplate | None:
        return next((item for item in self.list_templates() if item.id == template_id), None)
