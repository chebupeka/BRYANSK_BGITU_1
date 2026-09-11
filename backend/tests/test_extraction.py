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
    assert "number" not in memo, "у служебной записки нет исходящего номера"
    assert letter["number"] == "12-45", "«№ 12-45» — это исходящий номер"
    assert "sender" not in letter, "у письма нет поля «От кого»"


def test_unknown_labels_are_left_alone():
    found = suggest(DRAFT)
    assert "30 000" not in " ".join(found.values()), "«Стоимость» не реквизит"
    assert set(found) <= {"recipient", "sender", "subject", "date", "signer"}


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
        assert "number" not in requisites

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
    assert kept == ["№ 12-45", "Стоимость: 30 000 рублей",
                    "Прошу сагласовать закупку двух мониторов до 25.09.2026."]


def test_draft_made_only_of_requisites_keeps_its_lines():
    lines = ["Кому: Директору", "Тема: закупка"]
    assert body_lines(lines, document_types()["service_memo"]) == lines


def test_stub_mode_puts_labelled_lines_into_requisites_only():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.settings import Settings

    draft = "Кому: Директору\nПрошу согласовать закупку двух мониторов."
    with TestClient(create_app(Settings(text_processor="stub"))) as client:
        suggested = client.post("/api/requisites/suggest", json={
            "draft": draft, "doc_type": "service_memo",
        }).json()["requisites"]
        result = client.post("/api/process", json={
            "draft": draft, "doc_type": "service_memo", "requisites": suggested,
        }).json()
    assert result["document"]["requisites"]["recipient"] == "Директору"
    assert result["document"]["body"] == ["Прошу согласовать закупку двух мониторов."]
