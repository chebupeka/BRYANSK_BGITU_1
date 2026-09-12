import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,49}$")]
ShortText = Annotated[str, StringConstraints(max_length=500)]
Paragraph = Annotated[str, StringConstraints(min_length=1, max_length=20000)]
Alignment = Literal["left", "center", "right", "justify"]
# Where a requisite goes in the DOCX. Neighbouring fields with the same placement form one block.
Placement = Literal[
    "labeled",  # «Подпись поля: значение» — for requisites without a standard position
    "letterhead",  # organization: page header or the top of the page, see Template.header
    "addressee",  # «кому» / «от кого»: corner block or table, see Template.recipient_layout
    "registration",  # one line: «11.09.2026 № 47-СЗ»
    "headline",  # heading to the text: «О закупке мониторов»
    "salutation",  # «Уважаемый Иван Иванович!» before the text
    "paragraph",  # separate paragraph after the text, e.g. «Приложение: …»
    "signature",  # position and name, see Template.signature_alignment
    "executor",  # executor and phone at the end, smaller font
]


def check_xml_text(value: str) -> str:
    # XML 1.0 cannot represent these characters. Reject instead of losing user text.
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", value):
        raise ValueError("Текст содержит недопустимые управляющие символы")
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class RequisiteField(Contract):
    id: Identifier
    label: str
    required: bool = False
    placement: Placement = "labeled"
    # Static text before the value, e.g. «№ » or «Приложение: ». Not used by «labeled».
    prefix: str = ""


class DocumentType(Contract):
    id: Identifier
    name: str
    description: str
    title: str
    # Whether the document type name («СЛУЖЕБНАЯ ЗАПИСКА») is printed on the page.
    show_title: bool = True
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
    # Also used for the salutation of a letter.
    title_alignment: Alignment
    # right: addressee block in the right part of the page; left/center: block alignment.
    recipient_alignment: Alignment
    body_alignment: Alignment
    signature_alignment: Alignment = "left"
    # block: addressee lines as paragraphs; table: two columns «Кому | значение».
    recipient_layout: Literal["block", "table"] = "block"
    # organization: letterhead fields go to the page header on every page.
    header: Literal["none", "organization"] = "none"
    # title_and_date: «Служебная записка от 11.09.2026».
    footer: Literal["none", "page_number", "title_and_date"] = "none"
    header_footer_font_size: float = Field(default=10, ge=8, le=14)
    letterhead_alignment: Alignment = "center"
    headline_alignment: Alignment = "left"
    headline_bold: bool = False
    addressee_width_mm: float = Field(default=80, ge=50, le=120)
    small_font_size: float = Field(default=10, ge=8, le=14)


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


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    processor_mode: str


class ReadyResponse(Contract):
    status: Literal["ready"] = "ready"
    processor_mode: str
    checks: dict[str, bool]


class ErrorIssue(Contract):
    field: str
    message: str
    type: str


class ErrorInfo(Contract):
    code: str
    message: str
    retryable: bool
    request_id: str
    details: list[ErrorIssue] = Field(default_factory=list)


class ErrorResponse(Contract):
    # Retained for the existing frontend; new clients should also inspect error.code.
    detail: str
    error: ErrorInfo
