import json
from pathlib import Path

from pydantic import BaseModel, Field


class CatalogTest(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1)
    template_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")


class CatalogLab(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1)
    tests: list[CatalogTest] = Field(min_length=1)


class LocalTestCatalog:
    """Read the editable local list of labs, tests, and request-form mappings."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def list_labs(self) -> list[CatalogLab]:
        with self.path.open(encoding="utf-8") as handle:
            labs = [CatalogLab.model_validate(item) for item in json.load(handle)]
        lab_ids = [lab.id for lab in labs]
        test_ids = [test.id for lab in labs for test in lab.tests]
        if len(lab_ids) != len(set(lab_ids)) or len(test_ids) != len(set(test_ids)):
            raise ValueError("Lab and test IDs must be unique")
        return labs

    def resolve(self, test_ids: list[str]) -> list[dict]:
        lookup = {
            test.id: {"id": test.id, "name": test.name, "lab_id": lab.id, "lab_name": lab.name, "template_id": test.template_id}
            for lab in self.list_labs()
            for test in lab.tests
        }
        missing = [test_id for test_id in test_ids if test_id not in lookup]
        if missing:
            raise ValueError(f"Unknown test: {', '.join(missing)}")
        return [lookup[test_id] for test_id in test_ids]
