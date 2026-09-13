import pytest

from app.catalog import document_types
from app.extraction import body_lines, suggest_requisites

DRAFT = """Кому: Директору колледжа Иванову И. И.
От кого: лаборант Петрова А. А.
Тема — закупка мониторов
Дата: 11.09.2026
№ 12-45
Стоимость: 30 000 рублей

Прошу сагласовать закупку двух мониторов до 25.09.2026."""


def suggest(draft: str, type_id: str = "service_memo") -> dict[str, str]:
    return suggest_requisites(draft, document_types()[type_id])


def test_labelled_lines_become_requisites():
    found = suggest(DRAFT)
    assert found["recipient"] == "Директору колледжа Иванову И. И."
    assert found["sender"] == "лаборант Петрова А. А."
    assert found["subject"] == "закупка мониторов"
    assert found["date"] == "11.09.2026"


def test_only_fields_of_the_chosen_type_are_offered():
    memo, letter = suggest(DRAFT), suggest(DRAFT, "letter")
    assert memo["number"] == "12-45", "номер есть у записки по эталону кейса"
    assert letter["number"] == "12-45", "«№ 12-45» — это исходящий номер"
    assert "sender" not in letter, "у письма нет поля «От кого»"
    assert "purpose" not in memo, "«Назначение справки» есть только у справки"


def test_unknown_labels_are_left_alone():
    found = suggest(DRAFT)
    assert "30 000" not in " ".join(found.values()), "«Стоимость» не реквизит"
    assert set(found) <= {"recipient", "sender", "subject", "date", "number", "signer"}


@pytest.mark.parametrize("line", [
    "Дата поставки: 25.09.2026",
    "Тема письма от коллег: закупка",
    "Прошу учесть: сроки горят",
    "Кому:",
])
def test_near_misses_are_not_guessed(line):
    assert suggest(line + "\nПрошу согласовать закупку.") == {}


def test_label_may_be_written_loosely():
    draft = "- КОМУ  —  Директору\n* от кого: Петрова А. А.\nО чём: ремонт кабинета"
    found = suggest(draft)
    assert found == {
        "recipient": "Директору",
        "sender": "Петрова А. А.",
        "subject": "ремонт кабинета",
    }


def test_first_mention_wins_and_empty_values_are_skipped():
    draft = "Кому: Директору\nКому: Заместителю\nТема:   \nПрошу согласовать."
    found = suggest(draft)
    assert found == {"recipient": "Директору"}


def test_overlong_value_is_not_offered():
    assert suggest("Тема: " + "а" * 501 + "\nПрошу согласовать.") == {}


def test_suggest_endpoint_returns_only_known_fields():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.settings import Settings

    with TestClient(create_app(Settings(text_processor="stub"))) as client:
        response = client.post("/api/requisites/suggest", json={
            "draft": DRAFT, "doc_type": "service_memo",
        })
        assert response.status_code == 200
        requisites = response.json()["requisites"]
        assert requisites["recipient"] == "Директору колледжа Иванову И. И."
        assert requisites["number"] == "12-45"
        assert "30 000" not in " ".join(requisites.values()), "«Стоимость» не реквизит"

        unknown = client.post("/api/requisites/suggest", json={
            "draft": DRAFT, "doc_type": "нет_такого",
        })
        assert unknown.status_code == 422

        empty = client.post("/api/requisites/suggest", json={
            "draft": "   ", "doc_type": "service_memo",
        })
        assert empty.status_code == 422


def test_suggest_endpoint_works_without_a_model():
    """Подсказки не зависят от Ollama: они нужны до подготовки документа."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.settings import Settings

    with TestClient(create_app(Settings(text_processor="unavailable"))) as client:
        response = client.post("/api/requisites/suggest", json={
            "draft": "Кому: Директору\nПрошу согласовать закупку.", "doc_type": "service_memo",
        })
        assert response.json()["requisites"] == {"recipient": "Директору"}


def test_labelled_lines_do_not_repeat_in_the_document_text():
    kept = body_lines(DRAFT.splitlines(), document_types()["service_memo"])
    assert kept == ["Стоимость: 30 000 рублей",
                    "Прошу сагласовать закупку двух мониторов до 25.09.2026."]


def test_draft_made_only_of_requisites_keeps_its_lines():
    lines = ["Кому: Директору", "Тема: закупка"]
    assert body_lines(lines, document_types()["service_memo"]) == lines


def test_labelled_line_goes_to_a_requisite_and_leaves_the_text():
    """Разобранная строка шапки не должна попасть в текст документа второй раз."""
    draft = "Кому: Директору\nПрошу согласовать закупку двух мониторов."
    doc_type = document_types()["service_memo"]

    assert suggest_requisites(draft, doc_type) == {"recipient": "Директору"}
    assert body_lines(draft.splitlines(), doc_type) == [
        "Прошу согласовать закупку двух мониторов."
    ]


def test_header_requisites_are_recovered_without_asking_for_suggestions():
    """Обработчик роли 2 разбирает шапку сам: клиент может не звать подсказки."""
    draft = "Кому: Директору колледжа\nДата: 11.09.2026\nПрошу согласовать закупку."
    doc_type = document_types()["service_memo"]

    found = suggest_requisites(draft, doc_type)
    assert found["recipient"] == "Директору колледжа"
    assert found["date"] == "11.09.2026"
    assert body_lines(draft.splitlines(), doc_type) == ["Прошу согласовать закупку."]


def test_user_answer_beats_the_header_line():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.settings import Settings

    draft = "Кому: Директору колледжа\nПрошу согласовать закупку."
    with TestClient(create_app(Settings(text_processor="stub"))) as client:
        result = client.post("/api/process", json={
            "draft": draft, "doc_type": "service_memo",
            "requisites": {"recipient": "Заместителю директора"},
        }).json()
    assert result["document"]["requisites"]["recipient"] == "Заместителю директора"


def test_date_on_its_own_line_is_the_document_date():
    assert suggest("11.09.2026\nПрошу закупить мониторы.") == {"date": "11.09.2026"}
    assert suggest("11 сентября 2026 года\nПрошу закупить.") == {"date": "11 сентября 2026"}


def test_deadline_inside_a_sentence_is_not_the_document_date():
    assert suggest("Прошу закупить мониторы до 25.09.2026, если бюджет согласуют.") == {}


def test_outgoing_number_line_splits_into_number_and_date():
    draft = "Исх. № 12-45 от 11.09.2026\nПрошу прислать коммерческое предложение."
    assert suggest(draft, "letter") == {"number": "12-45", "date": "11.09.2026"}
    kept = body_lines(draft.splitlines(), document_types()["letter"])
    assert kept == ["Прошу прислать коммерческое предложение."]


def test_attachment_line_keeps_only_its_description():
    draft = "Прошу заменить окно в кабинете 204.\nПриложение на 2 листах"
    found = suggest(draft, "report_memo")
    assert found["attachment"] == "на 2 листах", "слово «Приложение» добавит генератор"


@pytest.mark.parametrize(
    "separator", [": ", " — ", " - ", " "], ids=["colon", "em-dash", "dash", "none"],
)
@pytest.mark.parametrize(("label", "value", "field_id", "expected"), [
    ("Дата", "12.03.2025", "date", "12.03.2025"),
    ("Номер", "47-СЗ", "number", "47-СЗ"),
    ("Заголовок", "О закупке офисной техники", "subject", "О закупке офисной техники"),
    ("Тема", "Об оплате поставки", "subject", "Об оплате поставки"),
    ("Подпись", "Петров.", "signer", "Петров"),
    ("Подписант", "Петров П.П.", "signer", "Петров П.П."),
])
def test_each_way_of_writing_a_label_gives_the_requisite(
    separator, label, value, field_id, expected,
):
    line = f"{label}{separator}{value}"
    draft = f"{line}\nПрошу согласовать закупку."
    doc_type = document_types()["service_memo"]

    assert suggest_requisites(draft, doc_type) == {field_id: expected}
    assert body_lines(draft.splitlines(), doc_type) == ["Прошу согласовать закупку."]


@pytest.mark.parametrize(("line", "found"), [
    ("Дата 11 сентября 2026 года", {"date": "11 сентября 2026"}),
    ("Номер № 12-45 от 11.09.2026", {"number": "12-45", "date": "11.09.2026"}),
    ("Подписант П. П. Петров", {"signer": "П. П. Петров"}),
    ("ПОДПИСЬ Николаева Н.Н.", {"signer": "Николаева Н.Н."}),
    ("Тема Про ремонт кабинета 204", {"subject": "Про ремонт кабинета 204"}),
])
def test_unseparated_label_accepts_usual_forms_of_the_value(line, found):
    assert suggest(line + "\nПрошу согласовать закупку.") == found


def test_unseparated_outgoing_number_of_a_letter():
    draft = "Исходящий номер 88-П\nПрошу прислать коммерческое предложение."
    assert suggest(draft, "letter") == {"number": "88-П"}


@pytest.mark.parametrize("line", [
    "От этого зависит срок поставки",
    "Дата поставки пока не известна",
    "Тема встречи обсуждалась вчера",
    "Номер телефона не указан",
    "Кому-то придётся задержаться",
    "Подпись поставят позже",
    "Номер 2 в очереди — отдел продаж",
    "Дата поставки 25.09.2026",
    "Номер телефона 8-900-000-00-00",
    "Номер 12 45",
    "Тема о закупке обсуждалась вчера",
    "Тема О закупке обсуждалась вчера. Решения нет",
    "Заголовок статьи уже придумали",
    "Подпись Отсутствует",
    "Подпись директора обязательна",
    "Подписант Петров поставит подпись завтра",
])
def test_prose_starting_with_a_label_word_is_not_a_requisite(line):
    draft = f"{line}\nПрошу согласовать закупку."
    doc_type = document_types()["service_memo"]

    assert suggest_requisites(draft, doc_type) == {}
    assert body_lines(draft.splitlines(), doc_type) == draft.splitlines(), (
        "строка без извлечённого реквизита остаётся в тексте"
    )


def test_label_word_at_the_end_of_a_paragraph_is_not_a_requisite():
    draft = "Нам надо купить три компьютера до 25.09.2026. Подпись Петров."
    assert suggest(draft) == {}


def test_unlabelled_fields_are_not_guessed_from_prose():
    draft = "Директор колледжа Иванов И. И. просит лаборанта Петрову А. А. закупить мониторы."
    assert suggest(draft) == {}, "адресата и подписанта из текста не выводим"
