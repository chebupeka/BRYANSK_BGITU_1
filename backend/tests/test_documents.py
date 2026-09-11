from io import BytesIO
from zipfile import ZipFile

import pytest
from docx import Document
from docx.shared import Mm
from fastapi.testclient import TestClient

from app.catalog import document_types, templates
from app.main import create_app
from app.settings import Settings

DRAFT = (
    "Иванов И. И. просит согласовать 30 000 рублей до 25.09.2026.\n"
    "Поставка возможна только после согласования бюджета."
)


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
    doc = Document(BytesIO(response.content))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert document_types()[type_id].title in text
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
    doc = Document(BytesIO(download(client, result["document"]).content))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
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
