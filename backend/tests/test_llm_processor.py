import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.processing import (
    LLMProcessor,
    build_messages,
    extract_facts,
    get_processor,
    unconfirmed_facts,
)
from app.schemas import ProcessRequest
from app.settings import Settings

DRAFT = (
    "Иванов И. И. просит согласовать 30 000 рублей до 25.09.2026.\n"
    "Поставка возможна только после согласования бюджета."
)
CLEAN_REPLY = json.dumps({
    "requisites": {"subject": "О согласовании закупки", "date": "25.09.2026"},
    "body": [
        "Прошу согласовать выделение 30 000 рублей в срок до 25 сентября 2026 года.",
        "Поставка возможна только после согласования бюджета.",
    ],
    "changes": ["Текст приведён к официально-деловому стилю."],
}, ensure_ascii=False)
INVENTED_SUM_REPLY = json.dumps({
    "requisites": {},
    "body": ["Прошу согласовать выделение 45 000 рублей до 25.09.2026."],
    "changes": [],
}, ensure_ascii=False)
INVENTED_SIGNER_REPLY = json.dumps({
    "requisites": {"signer": "Петров П. П.", "subject": "О закупке"},
    "body": ["Прошу согласовать выделение 30 000 рублей до 25.09.2026."],
    "changes": [],
}, ensure_ascii=False)


def scripted(*replies: str, error: Exception | None = None):
    """Модель заменяется расписанными ответами: тесты не зависят от установленной Ollama."""
    sent: list[dict] = []
    queue = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        if error is not None:
            raise error
        assert queue, "обработчик обратился к модели больше раз, чем разрешено"
        return httpx.Response(200, json={"choices": [{"message": {"content": queue.pop(0)}}]})

    processor = LLMProcessor(
        "http://ollama:11434/v1/",
        "test-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return processor, sent


def prepared(processor, requisites=None, doc_type="service_memo"):
    app = create_app(Settings(text_processor="llm", llm_model="test-model"), processor=processor)
    with TestClient(app) as client:
        response = client.post("/api/process", json={
            "draft": DRAFT, "doc_type": doc_type, "requisites": requisites or {},
        })
    return response


def test_clean_reply_is_used_without_retry():
    processor, sent = scripted(CLEAN_REPLY)
    result = prepared(processor).json()
    assert len(sent) == 1
    assert result["processor_mode"] == "llm"
    assert result["document"]["body"][0].startswith("Прошу согласовать выделение 30 000")
    assert result["document"]["requisites"]["subject"] == "О согласовании закупки"
    assert result["changes"] == ["Текст приведён к официально-деловому стилю."]
    assert result["warnings"] == []


def test_request_payload_and_prompt_carry_the_task():
    processor, sent = scripted(CLEAN_REPLY)
    prepared(processor, {"subject": "О закупке мониторов"})
    payload = sent[0]
    assert payload["model"] == "test-model"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["stream"] is False
    prompt = payload["messages"][-1]["content"]
    assert DRAFT in prompt
    assert '"signer" — Подписант (обязателен); не указано' in prompt
    assert 'указано пользователем: "О закупке мониторов"' in prompt


def test_user_answers_win_over_model_values():
    processor, _ = scripted(CLEAN_REPLY)
    result = prepared(processor, {"subject": "О закупке мониторов"}).json()
    assert result["document"]["requisites"]["subject"] == "О закупке мониторов"


def test_unconfirmed_requisite_is_left_empty_after_retry():
    processor, sent = scripted(INVENTED_SIGNER_REPLY, INVENTED_SIGNER_REPLY)
    result = prepared(processor).json()
    assert len(sent) == 2, "неподтверждённые сведения дают ровно один повтор"
    assert "отклонён" in sent[1]["messages"][-1]["content"]
    assert "signer" not in result["document"]["requisites"]
    assert "Подписант" in " ".join(result["warnings"])
    assert "signer" in [field["id"] for field in result["missing_fields"]]
    assert result["document"]["requisites"]["subject"] == "О закупке"


def test_invented_fact_triggers_one_retry_and_clean_answer_wins():
    processor, sent = scripted(INVENTED_SUM_REPLY, CLEAN_REPLY)
    result = prepared(processor).json()
    assert len(sent) == 2
    assert "45 000" not in " ".join(result["document"]["body"])
    assert result["warnings"] == []


def test_invented_fact_after_retry_is_flagged_but_document_returned():
    processor, sent = scripted(INVENTED_SUM_REPLY, INVENTED_SUM_REPLY)
    result = prepared(processor).json()
    assert len(sent) == 2
    assert "число 45000" in " ".join(result["warnings"])
    assert result["document"]["body"] == [
        "Прошу согласовать выделение 45 000 рублей до 25.09.2026."
    ]


def test_valid_first_reply_survives_a_broken_retry():
    processor, sent = scripted(INVENTED_SUM_REPLY, "модель сломалась")
    result = prepared(processor).json()
    assert len(sent) == 2
    assert result["document"]["body"], "годный ответ не теряется из-за сбоя на повторе"
    assert "число 45000" in " ".join(result["warnings"])


def test_broken_json_is_retried_and_then_reported():
    processor, sent = scripted("не json", "тоже не json")
    response = prepared(processor)
    assert len(sent) == 2
    assert response.status_code == 503
    assert "повтора" in response.json()["detail"]


def test_prose_and_code_fence_around_json_are_tolerated():
    processor, _ = scripted("Вот результат:\n```json\n" + CLEAN_REPLY + "\n```\nГотово.")
    assert prepared(processor).json()["document"]["requisites"]["date"] == "25.09.2026"


def test_network_failure_becomes_explicit_error():
    processor, sent = scripted(error=httpx.ConnectError("connection refused"))
    response = prepared(processor)
    assert len(sent) == 1, "сетевой сбой не повторяется молча"
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_empty_body_from_model_is_refused():
    empty = json.dumps({"requisites": {}, "body": ["   "], "changes": []}, ensure_ascii=False)
    processor, sent = scripted(empty, empty)
    assert prepared(processor).status_code == 503
    assert len(sent) == 2


def test_llm_mode_requires_model_name():
    with pytest.raises(ValueError, match="LLM_MODEL"):
        get_processor("llm", llm_base_url="http://localhost:11434/v1", llm_model="")


def test_messages_include_system_rules_and_schema():
    request = ProcessRequest(doc_type="service_memo", draft=DRAFT, requisites={})
    from app.catalog import document_types

    messages = build_messages(request, document_types()["service_memo"], {})
    assert messages[0]["role"] == "system"
    assert "Запрещено добавлять" in messages[0]["content"]
    assert [message["role"] for message in messages[1:3]] == ["user", "assistant"], "пример правки"
    assert '"requisites"' in messages[-1]["content"]
    assert '"body"' in messages[-1]["content"]


@pytest.mark.parametrize("first, second", [
    ("Срок — 25.09.2026", "Срок — 25 сентября 2026 года"),
    ("Сумма 30 000 рублей", "Сумма 30000 рублей"),
    ("Сумма 30" + chr(160) + "000 рублей", "Сумма 30 000 рублей"),
    ("Дата 2026-09-25", "Дата 25.09.2026"),
])
def test_same_fact_in_different_form_is_not_new(first, second):
    assert not unconfirmed_facts([second], extract_facts(first))


def test_shortening_a_name_is_allowed_but_expanding_it_is_not():
    full = extract_facts("Иванов Иван Иванович одобрил заявку")
    short = extract_facts("Иванов И. И. одобрил заявку")
    assert not unconfirmed_facts(["Согласовано: Иванов И. И."], full)
    assert unconfirmed_facts(["Согласовано: Иванов Иван Иванович"], short)


def test_list_numbering_is_not_a_fact_but_quantities_are():
    confirmed = extract_facts(DRAFT)
    assert not unconfirmed_facts(["1. Поставка возможна после согласования бюджета."], confirmed)
    assert unconfirmed_facts(["Требуется 7 мониторов."], confirmed) == ["число 7"]


def test_long_list_of_new_facts_is_shortened():
    added = "11 рублей, 22 дня, 33 кабинета, 44 этажа, 55 корпусов, 66 пунктов"
    invented = unconfirmed_facts([added], set())
    assert len(invented) == 6 and invented[-1] == "…"


def test_space_is_a_thousands_separator_inside_one_number():
    # «30 000» и «30000» — одно число; поэтому соседние числа через пробел склеиваются.
    assert extract_facts("30 000 рублей") == extract_facts("30000 рублей")
    assert extract_facts("15 000 25 000") == {"число 1500025000"}
