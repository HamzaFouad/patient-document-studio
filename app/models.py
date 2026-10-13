from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TemplateField(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    required: bool = False
    multiline: bool = False


class TemplateBlock(BaseModel):
    type: Literal["heading", "paragraph", "field", "spacer"]
    text: str = ""
    label: str = ""


class DocumentTemplate(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = ""
    fields: list[TemplateField] = Field(default_factory=list)
    blocks: list[TemplateBlock] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_fields(self):
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Template field keys must be unique")
        return self


class Patient(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    age: int = Field(ge=0, le=120)
    medical_history: str = Field(default="", max_length=5000)
    code: str = ""

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Patient name is required")
        return value


class Doctor(BaseModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Doctor name is required")
        return value


class GenerateRequest(BaseModel):
    patient: Patient
    doctor: Doctor
    template_ids: list[str] = Field(min_length=1, max_length=20)
    fields: dict[str, dict[str, str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_templates(self):
        if len(self.template_ids) != len(set(self.template_ids)):
            raise ValueError("Select each template only once")
        return self


class OrderCreate(BaseModel):
    test_ids: list[str] = Field(min_length=1, max_length=50)
    doctor_name: str = Field(default="", max_length=160)
    clinical_question: str = Field(default="", max_length=2000)
    copies: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def valid_order(self):
        if len(self.test_ids) != len(set(self.test_ids)):
            raise ValueError("Select each test only once")
        self.doctor_name = self.doctor_name.strip()
        self.clinical_question = self.clinical_question.strip()
        return self


class PurgeRequest(BaseModel):
    older_than_days: int = Field(ge=1, le=3650)
