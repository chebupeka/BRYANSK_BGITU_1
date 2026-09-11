import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.catalog import document_types
from app.main import create_app
from app.processing import (
    LLMProcessor,
    build_messages,
    describe_changes,
    extract_facts,
    get_processor,
    missing_facts,
    unconfirmed_facts,
    word_numbers,
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
    assert any("Переформулировано" in change for change in result["changes"])
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
    assert "Нет связи с Ollama" in response.json()["detail"]


def test_timeout_and_missing_model_are_told_apart():
    slow, _ = scripted(error=httpx.ReadTimeout("too slow"))
    assert "не ответила" in prepared(slow).json()["detail"]

    def missing(request: httpx.Request) -> httpx.Response:
        # Так отвечает Ollama: код 400, а не 404.
        return httpx.Response(400, json={
            "error": {"message": 'model "qwen2.5:7b-instruct" not found, try pulling it first'},
        })

    absent = LLMProcessor(
        "http://ollama:11434/v1", "qwen2.5:7b-instruct",
        client=httpx.Client(transport=httpx.MockTransport(missing)),
    )
    detail = prepared(absent).json()["detail"]
    assert "ollama pull qwen2.5:7b-instruct" in detail


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


def test_thousands_are_grouped_but_lists_are_not():
    assert extract_facts("30 000 рублей") == extract_facts("30000 рублей")
    assert extract_facts("1 234 567") == {"число 1234567"}
    assert extract_facts("15 000 25 000") == {"число 15000", "число 25000"}
    assert extract_facts("кабинеты 162, 163, 164") == {"число 162", "число 163", "число 164"}
    assert extract_facts("позиции 5, 7, 9") == {"число 5", "число 7", "число 9"}


def test_amount_in_words_matches_the_same_amount_in_digits():
    assert not unconfirmed_facts(["30 000 рублей"], extract_facts("тридцать тысяч рублей"))
    assert not unconfirmed_facts(
        ["30 000 (тридцать тысяч) рублей"], extract_facts("Нужно 30000 рублей")
    )
    assert unconfirmed_facts(
        ["сорок пять тысяч рублей"], extract_facts("Нужно 30 000 рублей")
    ) == ["число 45000"]


def test_ordinary_words_are_not_read_as_numbers():
    assert word_numbers("стоимость семинара у двери стать") == set()
    assert word_numbers("один из вариантов") == set(), "одиночная единица — оборот речи"
    assert word_numbers("две тысячи двадцать шесть") == {2026}
    assert word_numbers("сто пятьдесят") == {150}


def test_declined_surname_is_the_same_person():
    confirmed = extract_facts("Иванов И. И. согласовал заявку")
    assert not unconfirmed_facts(["Направить Иванову И. И. для исполнения."], confirmed)
    assert unconfirmed_facts(["Направить Иваненко И. И."], confirmed) == ["имя иваненко"]


def test_dropped_fact_is_reported_too():
    dropped = json.dumps({
        "requisites": {},
        "body": ["Прошу согласовать закупку мониторов."],
        "changes": [],
    }, ensure_ascii=False)
    processor, _ = scripted(dropped)
    warnings = " ".join(prepared(processor).json()["warnings"])
    assert "не попали в документ" in warnings
    assert "число 30000" in warnings


def test_fact_moved_into_a_requisite_is_not_lost():
    confirmed = extract_facts("Срок до 25.09.2026, сумма 30 000 рублей")
    assert not missing_facts(confirmed, ["Прошу выделить 30 000 рублей.", "25.09.2026"])


def test_author_name_may_disappear_when_the_text_becomes_first_person():
    confirmed = extract_facts("Иванов И. И. просит выделить 30 000 рублей")
    assert not missing_facts(confirmed, ["Прошу выделить 30 000 рублей."])
    assert missing_facts(confirmed, ["Прошу выделить средства."]) == ["число 30000"]


def test_changes_come_from_the_texts_not_from_the_model():
    fixed = describe_changes("Сообщаю что протикла батарея.", ["Сообщаю, что протекла батарея."])
    assert "Исправлено: «протикла» → «протекла»" in fixed
    assert describe_changes("Текст без правок.", ["Текст без правок."]) == []


def test_model_cannot_claim_edits_it_did_not_make():
    boastful = json.dumps({
        "requisites": {},
        "body": [DRAFT.splitlines()[0], DRAFT.splitlines()[1]],
        "changes": ["Исправлены все ошибки", "Текст полностью переписан"],
    }, ensure_ascii=False)
    processor, _ = scripted(boastful)
    assert prepared(processor).json()["changes"] == [], "текст не менялся, значит правок нет"


def test_same_draft_is_not_sent_to_the_model_twice():
    processor, sent = scripted(CLEAN_REPLY)
    first = prepared(processor).json()
    second = prepared(processor).json()
    assert len(sent) == 1, "повторная подготовка берётся из кэша"
    assert first["document"] == second["document"]


def test_changed_answers_are_prepared_again():
    processor, sent = scripted(CLEAN_REPLY, CLEAN_REPLY)
    prepared(processor)
    prepared(processor, {"recipient": "Директору"})
    assert len(sent) == 2, "другие реквизиты — другая подготовка"


def test_request_asks_to_keep_the_model_loaded():
    processor, sent = scripted(CLEAN_REPLY)
    prepared(processor)
    assert sent[0]["keep_alive"] == "30m"
    assert sent[0]["seed"] == 0


def test_cache_returns_a_copy_that_cannot_be_spoiled():
    processor, sent = scripted(CLEAN_REPLY)
    request = ProcessRequest(doc_type="service_memo", draft=DRAFT, requisites={})
    doc_type = document_types()["service_memo"]
    first = processor.process(request, doc_type)
    first.document.body.append("Приписка мимо модели.")
    first.warnings.append("чужое предупреждение")
    second = processor.process(request, doc_type)
    assert len(sent) == 1
    assert "Приписка мимо модели." not in second.document.body
    assert second.warnings == []
