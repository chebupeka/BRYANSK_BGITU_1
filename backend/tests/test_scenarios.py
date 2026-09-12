"""Сценарии готовности 1–6 из критериев оценки кейса.

Проверка идёт только через публичный API, поэтому набор одинаково применим к заглушке
и к реальной модели: меняется обработчик, а не условия сценария.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from qa_support import (
    ALIGNMENT_NAMES,
    assert_editable_docx,
    body_paragraphs,
    case_by_id,
    docx_text,
    download,
    keeps,
    measured_layout,
    process,
    significant_numbers,
)

COLLOQUIAL = "service_memo_02_colloquial"
INCOMPLETE = "service_memo_03_incomplete"


# Сценарий 1. Полный путь до DOCX.

def test_scenario_1_service_offers_four_types_and_two_templates(catalog):
    assert len(catalog["doc_types"]) >= 4, "Нужны все четыре обязательных типа документов"
    assert len(catalog["templates"]) >= 2, "Нужно не менее двух шаблонов оформления"


def test_scenario_1_draft_becomes_editable_docx(client):
    case = case_by_id("service_memo_01_structured")
    prepared = process(client, case.draft, case.doc_type)

    data = download(client, prepared["document"], "classic")

    assert_editable_docx(data)
    text = docx_text(data)
    assert "СЛУЖЕБНАЯ ЗАПИСКА" in text, "В файле нет заголовка выбранного типа"
    for value in case.must_keep:
        assert keeps(text, value), f"Значение «{value}» не дошло до готового файла"


# Сценарии 2 и 4. Обработка текста и сохранение смысла.

def test_scenario_2_and_4_facts_of_a_colloquial_draft_reach_the_document(client):
    case = case_by_id(COLLOQUIAL)
    prepared = process(client, case.draft, case.doc_type)

    text = docx_text(download(client, prepared["document"], "classic"))

    for value in case.must_keep:
        assert keeps(text, value), f"Значение «{value}» потеряно при обработке"


def test_scenario_2_and_4_processing_adds_no_numbers_of_its_own(client):
    case = case_by_id(COLLOQUIAL)
    prepared = process(client, case.draft, case.doc_type)

    text = docx_text(download(client, prepared["document"], "classic"))

    invented = significant_numbers(text) - significant_numbers(case.draft)
    assert not invented, f"В документе появились числа, которых не было в черновике: {invented}"


def test_scenario_2_and_4_result_states_what_was_done_with_the_text(client):
    case = case_by_id(COLLOQUIAL)

    prepared = process(client, case.draft, case.doc_type)

    assert prepared["processor_mode"], "Пользователь должен видеть, чем обработан текст"
    assert prepared["changes"] or prepared["warnings"], (
        "Результат без перечня правок и без предупреждения выглядит как молчаливая замена текста"
    )


# Сценарий 3. Работа с недостающими реквизитами.

def test_scenario_3_absent_requisites_are_reported_and_left_empty(client):
    case = case_by_id(INCOMPLETE)

    prepared = process(client, case.draft, case.doc_type)

    reported = {field["id"] for field in prepared["missing_fields"]}
    assert set(case.not_in_draft) <= reported, (
        f"Не сообщено о пропуске обязательных реквизитов: {set(case.not_in_draft) - reported}"
    )
    for field_id in case.not_in_draft:
        value = prepared["document"]["requisites"].get(field_id, "")
        assert not value.strip(), f"Реквизит «{field_id}» заполнен значением «{value}» из ниоткуда"


def test_scenario_3_unfilled_requisites_are_marked_in_the_file(client):
    case = case_by_id(INCOMPLETE)
    prepared = process(client, case.draft, case.doc_type)

    text = docx_text(download(client, prepared["document"], "classic"))

    for field in prepared["missing_fields"]:
        assert f"[Заполнить: {field['label']}]" in text, (
            f"Незаполненный реквизит «{field['label']}» не помечен в документе"
        )


def test_scenario_3_values_entered_by_the_user_reach_the_file(client):
    case = case_by_id(INCOMPLETE)
    answers = {
        "recipient": "Генеральному директору ООО «Ромашка» Иванову И.И.",
        "date": "12.03.2025",
    }

    prepared = process(client, case.draft, case.doc_type, answers)

    reported = {field["id"] for field in prepared["missing_fields"]}
    assert not reported & set(answers), "Введённый реквизит всё ещё считается недостающим"
    text = docx_text(download(client, prepared["document"], "classic"))
    for value in answers.values():
        assert value in text, f"Введённое пользователем значение «{value}» не попало в документ"


# Сценарий 5. Типы документов и шаблоны.

def test_scenario_5_every_type_keeps_its_own_structure(client, catalog, required_fields):
    draft = case_by_id("service_memo_01_structured").draft
    seen = {}
    for doc_type in catalog["doc_types"]:
        prepared = process(client, draft, doc_type["id"])
        text = docx_text(download(client, prepared["document"], "classic"))
        assert doc_type["title"] in text, f"В файле нет заголовка типа «{doc_type['name']}»"
        for field in doc_type["fields"]:
            if field["required"]:
                assert field["label"] in text, (
                    f"У типа «{doc_type['name']}» пропущен реквизит «{field['label']}»"
                )
        seen[doc_type["id"]] = set(required_fields[doc_type["id"]])

    assert len(set(map(frozenset, seen.values()))) > 1, (
        "Смена типа документа обязана менять состав обязательных реквизитов"
    )


@pytest.mark.parametrize("type_id", ["service_memo", "report_memo", "information_note", "letter"])
def test_scenario_5_template_changes_look_not_content(client, type_id):
    draft = case_by_id("service_memo_01_structured").draft
    document = process(client, draft, type_id)["document"]

    classic = download(client, document, "classic")
    modern = download(client, document, "modern")

    assert docx_text(classic) == docx_text(modern), "Смена шаблона изменила содержание документа"
    differences = {
        key for key, value in measured_layout(classic).items()
        if measured_layout(modern)[key] != value
    }
    assert len(differences) >= 3, (
        f"Шаблоны почти не отличаются оформлением, различий всего: {differences}"
    )


def test_scenario_5_body_alignment_and_indent_follow_the_template(client, template_rules):
    draft = case_by_id("service_memo_01_structured").draft
    document = process(client, draft, "service_memo")["document"]

    for template_id, rules in template_rules.items():
        data = download(client, document, template_id)
        paragraphs = body_paragraphs(data, document["body"])
        assert paragraphs, f"В файле шаблона «{template_id}» не нашлось основного текста"
        for paragraph in paragraphs:
            assert ALIGNMENT_NAMES[paragraph.alignment] == rules["body_alignment"]
            indent = paragraph.paragraph_format.first_line_indent
            assert abs(indent.mm - rules["first_line_indent_mm"]) < 0.2


# Сценарий 6. Обработка ошибок.

def test_scenario_6_unavailable_processor_answers_clearly_and_keeps_serving(unavailable_client):
    case = case_by_id(COLLOQUIAL)

    response = unavailable_client.post("/api/process", json={
        "draft": case.draft, "doc_type": case.doc_type, "requisites": {},
    })

    assert response.status_code == 503, "Отказ обработки должен быть явной ошибкой сервиса"
    detail = response.json()["detail"]
    assert "Traceback" not in detail and len(detail) < 300, "Пользователю показан технический сбой"
    assert "недоступна" in detail.casefold(), "Сообщение не объясняет, что именно произошло"
    assert "document" not in response.json(), "При отказе не должен возвращаться документ"
    assert unavailable_client.get("/api/health").status_code == 200, "Сервис перестал отвечать"


def test_scenario_6_retry_after_failure_behaves_the_same(unavailable_client):
    case = case_by_id(COLLOQUIAL)
    payload = {"draft": case.draft, "doc_type": case.doc_type, "requisites": {}}

    answers = [unavailable_client.post("/api/process", json=payload) for _ in range(3)]

    assert [answer.status_code for answer in answers] == [503, 503, 503], (
        "Повторная попытка обязана вести себя предсказуемо, а не ломать сервис"
    )


def test_scenario_6_already_prepared_document_still_downloads(client, unavailable_client):
    document = process(client, case_by_id(COLLOQUIAL).draft, "service_memo")["document"]

    data = download(unavailable_client, document, "modern")

    assert_editable_docx(data)


@pytest.mark.parametrize("payload, reason", [
    ({"draft": "   ", "doc_type": "service_memo", "requisites": {}}, "пустой черновик"),
    ({"draft": "текст", "doc_type": "unknown", "requisites": {}}, "неизвестный тип"),
    ({"draft": "текст", "doc_type": "service_memo", "requisites": {"nope": "x"}}, "чужой реквизит"),
])
def test_scenario_6_invalid_input_is_refused_without_a_server_error(client, payload, reason):
    response = client.post("/api/process", json=payload)

    assert response.status_code == 422, f"Ожидался понятный отказ: {reason}"
    assert response.json()["detail"], "Отказ без объяснения причины"


# Дополнительные проверки устойчивости, не привязанные к одному сценарию.

def test_long_draft_reaches_the_file_completely(client):
    sentence = (
        "Отдел аналитики продолжает работу по плану, утверждённому 12.03.2025, "
        "и передаёт сведения для включения в сводный отчёт. "
    )
    draft = "\n".join(sentence * 3 for _ in range(40))

    prepared = process(client, draft, "information_note")
    data = download(client, prepared["document"], "classic")

    assert_editable_docx(data)
    assert len(prepared["document"]["body"]) == 40, "Часть абзацев потерялась при обработке"
    assert docx_text(data).count(sentence.strip()[:40]) >= 40, "Длинный текст обрезан в файле"


def test_same_document_produces_the_same_text_every_time(client):
    document = process(client, case_by_id(COLLOQUIAL).draft, "service_memo")["document"]

    first = docx_text(download(client, document, "classic"))
    second = docx_text(download(client, document, "classic"))

    assert first == second, "Повторное скачивание дало другой документ"


def test_simultaneous_users_never_receive_each_others_data(client):
    # Ловит общий кэш или глобальное состояние, из-за которых черновик одного
    # пользователя может оказаться в документе другого.
    def prepare(number):
        draft = f"Прошу согласовать заявку {number:03d}-ПРОВЕРКА на сумму {number * 1000} рублей."
        prepared = process(client, draft, "service_memo")
        return number, docx_text(download(client, prepared["document"], "classic"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(prepare, range(1, 25)))

    for number, text in results:
        assert f"{number:03d}-ПРОВЕРКА" in text, f"Пользователь {number} не получил свой текст"
        foreign = [n for n, _ in results if n != number and f"{n:03d}-ПРОВЕРКА" in text]
        assert not foreign, f"В документ пользователя {number} попали чужие данные: {foreign}"


def test_largest_allowed_draft_is_turned_into_a_document_quickly(client):
    line = "Отдел аналитики передаёт сведения для включения в сводный отчёт за квартал.\n"
    draft = (line * (20000 // len(line) + 1))[:20000]

    started = time.perf_counter()
    prepared = process(client, draft, "information_note")
    data = download(client, prepared["document"], "classic")
    elapsed = time.perf_counter() - started

    assert_editable_docx(data)
    assert elapsed < 10, f"Документ максимального размера формировался {elapsed:.1f} с"
