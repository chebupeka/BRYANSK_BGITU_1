"""Те же сценарии 2–4, но на настоящей модели, а не на заглушке.

По умолчанию набор пропускается: он требует запущенной модели и поэтому не годится
для обычного прогона и CI. Заглушка переносит текст дословно, так что проверки
сохранения фактов проходят на ней автоматически — настоящую цену они имеют здесь,
когда текст действительно переписывается.

Запуск:
    QA_LLM=1 backend/.venv/Scripts/python -m pytest tests/test_llm_scenarios.py -v

Нужны LLM_BASE_URL и LLM_MODEL в .env и доступная модель по этому адресу.
"""

import os

import pytest
from fastapi.testclient import TestClient
from qa_support import (
    assert_editable_docx,
    case_by_id,
    docx_text,
    download,
    keeps,
    prepared_text,
    process,
    significant_numbers,
)

from app.main import create_app
from app.settings import Settings

CASES = ["service_memo_02_colloquial", "report_memo_02_colloquial", "letter_02_colloquial"]


def skip_reason() -> str:
    if os.getenv("QA_LLM") != "1":
        return "нужен QA_LLM=1: проверка обращается к настоящей модели"
    modes = getattr(Settings.model_fields["text_processor"].annotation, "__args__", ())
    if "llm" not in modes:
        return "в этой ветке режим обработки llm ещё не добавлен"
    if not getattr(Settings(), "llm_model", ""):
        return "не задан LLM_MODEL в .env"
    return ""


SKIP = skip_reason()
pytestmark = pytest.mark.skipif(bool(SKIP), reason=SKIP or "модель доступна")


@pytest.fixture(scope="module")
def llm_client():
    with TestClient(create_app(Settings(text_processor="llm"))) as ready:
        yield ready


@pytest.mark.parametrize("case_id", CASES)
def test_model_rewrites_the_draft_instead_of_copying_it(llm_client, case_id):
    case = case_by_id(case_id)

    prepared = process(llm_client, case.draft, case.doc_type)

    body = "\n".join(prepared["document"]["body"])
    assert body.strip() != case.draft.strip(), "Модель вернула исходный текст без изменений"
    assert prepared["processor_mode"] == "llm"


@pytest.mark.parametrize("case_id", CASES)
def test_model_keeps_every_fact_of_the_draft(llm_client, case_id):
    case = case_by_id(case_id)

    prepared = process(llm_client, case.draft, case.doc_type)

    text = docx_text(download(llm_client, prepared["document"], "classic"))
    for value in case.must_keep:
        assert keeps(text, value), f"«{case.label}»: модель потеряла значение «{value}»"


@pytest.mark.parametrize("case_id", CASES)
def test_model_adds_no_numbers_of_its_own(llm_client, case_id):
    case = case_by_id(case_id)

    prepared = process(llm_client, case.draft, case.doc_type)

    invented = significant_numbers(prepared_text(prepared["document"]))
    invented -= significant_numbers(case.draft)
    assert not invented, f"«{case.label}»: модель добавила числа {invented}"


@pytest.mark.parametrize("case_id", ["service_memo_03_incomplete", "letter_04_flat"])
def test_model_does_not_fill_requisites_that_are_absent_from_the_draft(llm_client, case_id):
    case = case_by_id(case_id)

    prepared = process(llm_client, case.draft, case.doc_type)

    for field_id in case.not_in_draft:
        value = prepared["document"]["requisites"].get(field_id, "")
        assert not value.strip(), f"«{case.label}»: модель придумала «{field_id}» = «{value}»"
    assert_editable_docx(download(llm_client, prepared["document"], "classic"))
