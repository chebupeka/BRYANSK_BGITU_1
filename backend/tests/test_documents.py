from io import BytesIO
from zipfile import ZipFile

import pytest
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Mm
from fastapi.testclient import TestClient

from app.catalog import check_contiguous_placements, document_types, templates
from app.docx_generator import NBSP
from app.schemas import DocumentType
from app.main import create_app
from app.settings import Settings

DRAFT = (
    "Иванов И. И. просит согласовать 30 000 рублей до 25.09.2026.\n"
    "Поставка возможна только после согласования бюджета."
)
REQUISITES = {
    "organization": "ФГБОУ ВО «БГИТУ»",
    "organization_details": "г. Брянск, тел. (4832) 00-00-00",
    "department": "Кафедра информационных технологий",
    "recipient": "Руководителю учебного отдела Сидоровой А. В.",
    "sender": "заведующего лабораторией Иванова И. И.",
    "subject": "О закупке мониторов",
    "date": "11.09.2026",
    "number": "01-12/345",
    "reply_number": "15-01/77",
    "reply_date": "01.09.2026",
    "attachment": "акт на 1 л. в 1 экз.",
    "purpose": "для планово-финансового отдела",
    "signer_position": "Заведующий лабораторией",
    "signer": "И. И. Иванов",
    "executor": "Петров П. П., (4832) 00-00-01",
}


@pytest.fixture
def client():
    with TestClient(create_app(Settings(text_processor="stub"))) as client:
        yield client


def prepared(client, type_id="service_memo", requisites=None):
    response = client.post("/api/process", json={
        "draft": DRAFT, "doc_type": type_id, "requisites": requisites or {},
    })
    assert response.status_code == 200, response.text
    return response.json()


def download(client, document, template_id="classic"):
    response = client.post("/api/documents/download", json={
        "document": document, "template_id": template_id,
    })
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].endswith('.docx"')
    assert "wordprocessingml.document" in response.headers["content-type"]
    return response


def filled(type_id):
    return {field.id: REQUISITES[field.id] for field in document_types()[type_id].fields}


def paragraphs_of(content: bytes) -> list:
    return Document(BytesIO(content)).paragraphs


def document_text(content: bytes) -> str:
    # The generator keeps «№ 214» and «30 000» together with no-break spaces.
    doc = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs).replace(NBSP, " ")


def test_catalog_and_health(client):
    catalog = client.get("/api/catalog").json()
    assert len(catalog["doc_types"]) == 4
    assert len(catalog["templates"]) == 2
    assert client.get("/api/health").json()["status"] == "ok"


@pytest.mark.parametrize("type_id", list(document_types()))
@pytest.mark.parametrize("template_id", list(templates()))
def test_all_types_and_templates_generate_editable_documents(client, type_id, template_id):
    result = prepared(client, type_id)
    response = download(client, result["document"], template_id)
    text = document_text(response.content)
    doc_type = document_types()[type_id]
    assert (doc_type.title in text) == doc_type.show_title
    for line in DRAFT.splitlines():
        assert line in text
    for field in result["missing_fields"]:
        assert f'[Заполнить: {field["label"]}]' in text
    with ZipFile(BytesIO(response.content)) as archive:
        assert not any(name.startswith("word/media/") for name in archive.namelist())


def test_stub_preserves_facts_and_does_not_claim_corrections(client):
    result = prepared(client)
    assert result["document"]["body"] == DRAFT.splitlines()
    assert result["document"]["requisites"] == {}
    assert result["changes"] == []
    assert result["processor_mode"] == "stub"
    assert result["warnings"]


def test_supplied_requisites_replace_placeholders(client):
    fields = document_types()["service_memo"].fields
    values = {field.id: f"Введено пользователем: {field.label}" for field in fields}
    result = prepared(client, requisites=values)
    assert not result["missing_fields"]
    text = document_text(download(client, result["document"]).content)
    assert "[Заполнить:" not in text
    for value in values.values():
        assert value in text


def test_many_short_lines_within_draft_limit_are_valid(client):
    response = client.post("/api/process", json={
        "draft": "\n".join(["x"] * 1001), "doc_type": "service_memo", "requisites": {},
    })
    assert response.status_code == 200
    assert len(response.json()["document"]["body"]) == 1001


def test_switching_template_changes_formatting_only(client):
    document = prepared(client)["document"]
    classic = Document(BytesIO(download(client, document, "classic").content))
    modern = Document(BytesIO(download(client, document, "modern").content))
    assert [p.text for p in classic.paragraphs] == [p.text for p in modern.paragraphs]
    assert classic.styles["Normal"].font.name == "Times New Roman"
    assert modern.styles["Normal"].font.name == "Arial"
    assert classic.styles["Normal"].font.size.pt == 14
    assert modern.styles["Normal"].font.size.pt == 11
    assert abs(classic.sections[0].left_margin - Mm(30)) < Mm(0.1)
    assert abs(modern.sections[0].left_margin - Mm(25)) < Mm(0.1)


@pytest.mark.parametrize("template_id", list(templates()))
def test_styles_use_template_font_without_theme_leftovers(client, template_id):
    doc = Document(BytesIO(download(client, prepared(client)["document"], template_id).content))
    font = templates()[template_id].font
    theme_names = ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme")
    theme_attrs = [qn(f"w:{name}") for name in theme_names]
    defaults = doc.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault"))
    rpr_elements = [
        defaults.find(qn("w:rPr")),
        doc.styles["Normal"].element.rPr,
        doc.styles["Title"].element.rPr,
    ]
    for rpr in rpr_elements:
        rfonts = rpr.find(qn("w:rFonts"))
        assert not any(attr in rfonts.attrib for attr in theme_attrs)
        for name in ("ascii", "hAnsi", "eastAsia", "cs"):
            assert rfonts.get(qn(f"w:{name}")) == font
    assert defaults.find(qn("w:rPr")).find(qn("w:lang")).get(qn("w:val")) == "ru-RU"
    assert doc.styles["Title"].element.pPr.find(qn("w:pBdr")) is None


def test_numbers_are_kept_on_one_line_without_changing_text(client):
    draft = "Аудитория № 214, сумма 30 000 рублей, дата 25.09.2026."
    response = client.post("/api/process", json={
        "draft": draft, "doc_type": "service_memo", "requisites": {"subject": "Счёт № 15"},
    })
    content = download(client, response.json()["document"]).content
    paragraphs = [paragraph.text for paragraph in Document(BytesIO(content)).paragraphs]
    assert f"Аудитория №{NBSP}214, сумма 30{NBSP}000 рублей, дата 25.09.2026." in paragraphs
    assert f"Счёт №{NBSP}15" in paragraphs
    assert draft in document_text(content)


@pytest.mark.parametrize("template_id", list(templates()))
def test_requisites_are_placed_like_in_real_documents(client, template_id):
    result = prepared(client, "service_memo", filled("service_memo"))
    paragraphs = paragraphs_of(download(client, result["document"], template_id).content)
    texts = [paragraph.text for paragraph in paragraphs]
    # Requisites are printed without form labels such as «Кому:» or «Тема:».
    assert not any(text.startswith(("Кому:", "От кого:", "Тема:", "Дата:")) for text in texts)
    assert f"11.09.2026 №{NBSP}01-12/345" in texts
    assert "О закупке мониторов" in texts
    assert "Приложение: акт на 1 л. в 1 экз." in texts
    assert "Заведующий лабораторией\tИ. И. Иванов" in texts
    addressee = paragraphs[texts.index(REQUISITES["recipient"])]
    if templates()[template_id].recipient_alignment == "right":
        assert addressee.paragraph_format.left_indent > Mm(50)
    order = [texts.index(value) for value in (
        REQUISITES["recipient"], "СЛУЖЕБНАЯ ЗАПИСКА", f"11.09.2026 №{NBSP}01-12/345",
        "О закупке мониторов", DRAFT.splitlines()[1], "Заведующий лабораторией\tИ. И. Иванов",
    )]
    assert order == sorted(order)


def test_letter_has_no_type_name_and_shows_reference_and_executor(client):
    result = prepared(client, "letter", filled("letter"))
    text = document_text(download(client, result["document"]).content)
    assert "ПИСЬМО" not in text
    assert "На № 15-01/77 от 01.09.2026" in text
    assert "Петров П. П., (4832) 00-00-01" in text


def test_empty_optional_requisites_leave_no_traces(client):
    required = {field.id: REQUISITES[field.id]
                for field in document_types()["service_memo"].fields if field.required}
    result = prepared(client, "service_memo", required)
    texts = [p.text for p in paragraphs_of(download(client, result["document"]).content)]
    assert "11.09.2026" in texts
    assert "\tИ. И. Иванов" in texts
    assert not any("Приложение" in text or "№" in text for text in texts)


def test_page_numbers_start_from_the_second_page(client):
    content = download(client, prepared(client)["document"]).content
    section = Document(BytesIO(content)).sections[0]
    assert section.different_first_page_header_footer
    assert 'w:instr="PAGE"' in section.header._element.xml
    assert "PAGE" not in section.first_page_header._element.xml


def test_combined_requisites_must_be_adjacent():
    doc_type = DocumentType.model_validate({
        "id": "broken", "name": "x", "description": "x", "title": "X",
        "fields": [
            {"id": "date", "label": "Дата", "placement": "registration"},
            {"id": "number", "label": "Номер", "placement": "registration"},
        ],
        "blocks": ["date", "title", "number", "body"],
    })
    with pytest.raises(ValueError):
        check_contiguous_placements(doc_type, "broken.yaml")


@pytest.mark.parametrize("patch", [
    {"draft": "   "}, {"draft": "x" * 20001}, {"draft": "bad\x00text"},
    {"doc_type": "missing"}, {"requisites": {"invented": "value"}},
    {"requisites": {"recipient": "\x00"}}, {"extra": "not allowed"},
])
def test_invalid_processing_requests_are_rejected(client, patch):
    payload = {"draft": DRAFT, "doc_type": "service_memo", "requisites": {}} | patch
    assert client.post("/api/process", json=payload).status_code == 422


def test_download_validates_content_and_template(client):
    document = prepared(client)["document"]
    for payload in [
        {"document": document, "template_id": "unknown"},
        {"document": document | {"body": []}, "template_id": "classic"},
        {"document": document | {"body": ["bad\x00"]}, "template_id": "classic"},
        {"document": document | {"requisites": {"unknown": "x"}}, "template_id": "classic"},
    ]:
        assert client.post("/api/documents/download", json=payload).status_code == 422


def test_processor_failure_is_explicit_and_prepared_document_can_still_download(client):
    document = prepared(client)["document"]
    with TestClient(create_app(Settings(text_processor="unavailable"))) as failing:
        assert failing.get("/api/health").status_code == 200
        for _ in range(2):
            response = failing.post("/api/process", json={
                "draft": DRAFT, "doc_type": "service_memo", "requisites": {},
            })
            assert response.status_code == 503
            assert "недоступна" in response.json()["detail"]
        # Export accepts already prepared content and does not call the processor again.
        download(failing, document, "modern")
