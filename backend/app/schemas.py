import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,49}$")]
ShortText = Annotated[str, StringConstraints(max_length=500)]
Paragraph = Annotated[str, StringConstraints(min_length=1, max_length=20000)]
Alignment = Literal["left", "center", "right", "justify"]


def check_xml_text(value: str) -> str:
    # XML 1.0 cannot represent these characters. Reject instead of losing user text.
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", value):
        raise ValueError("Текст содержит недопустимые управляющие символы")
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequisiteField(Contract):
    id: Identifier
    label: str
    required: bool = False


class DocumentType(Contract):
    id: Identifier
    name: str
    description: str
    title: str
    fields: list[RequisiteField]
    blocks: list[str]


class Template(Contract):
    id: Identifier
    name: str
    description: str
    font: str
    font_size: float = Field(ge=10, le=16)
    margins_mm: dict[Literal["top", "right", "bottom", "left"], float]
    line_spacing: float = Field(ge=1, le=2)
    paragraph_space_after_pt: float = Field(ge=0, le=24)
    first_line_indent_mm: float = Field(ge=0, le=20)
    title_alignment: Alignment
    recipient_alignment: Alignment
    body_alignment: Alignment


class Catalog(Contract):
    doc_types: list[DocumentType]
    templates: list[Template]
    processor_mode: str


class DocumentContent(Contract):
    doc_type: Identifier
    requisites: dict[Identifier, ShortText] = Field(default_factory=dict, max_length=30)
    body: list[Paragraph] = Field(min_length=1, max_length=10000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: list[str]) -> list[str]:
        if sum(map(len, value)) > 20000 or not any(p.strip() for p in value):
            raise ValueError("Нужен непустой текст до 20 000 символов")
        for paragraph in value:
            check_xml_text(paragraph)
        return value

    @field_validator("requisites")
    @classmethod
    def validate_requisites(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: check_xml_text(text).strip() for key, text in value.items()}


class ProcessRequest(Contract):
    doc_type: Identifier
    draft: str = Field(min_length=1, max_length=20000)
    requisites: dict[Identifier, ShortText] = Field(default_factory=dict, max_length=30)

    @field_validator("draft")
    @classmethod
    def validate_draft(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Введите черновик документа")
        return check_xml_text(value)

    @field_validator("requisites")
    @classmethod
    def validate_requisites(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: check_xml_text(text).strip() for key, text in value.items()}


class ProcessResponse(Contract):
    document: DocumentContent
    missing_fields: list[RequisiteField]
    changes: list[str]
    warnings: list[str]
    processor_mode: str


class DownloadRequest(Contract):
    document: DocumentContent
    template_id: Identifier
