"""Проверки самих проверок.

Большинство сценарных тестов проходит и на заглушке, которая переносит текст дословно.
Эти тесты показывают, что набор не пустой: подмена фактов и испорченный файл будут пойманы.
"""

from io import BytesIO
from zipfile import BadZipFile

import pytest
from docx import Document
from qa_support import assert_editable_docx, keeps, significant_numbers


@pytest.mark.parametrize("text, value, found", [
    ("сумма 180000 рублей", "180 000", True),
    ("сумма 180 000 рублей", "180000", True),
    ("подписал ПЕТРОВ П.П.", "Петров", True),
    ("текст без суммы", "180 000", False),
    ("срок до 25.03.2025", "25.03.2026", False),
])
def test_value_comparison_ignores_case_and_spacing_inside_numbers(text, value, found):
    assert keeps(text, value) is found


def test_number_added_to_the_text_is_detected():
    draft = "Стоимость 180 000 рублей, срок до 25.03.2025."

    rewritten = draft + " Договор № 17 от 2024 года."

    assert significant_numbers(rewritten) - significant_numbers(draft) == {"17", "2024"}


def test_rewording_without_new_numbers_raises_no_suspicion():
    draft = "Стоимость 180 000 рублей, срок до 25.03.2025."

    rewritten = "Срок исполнения — 25.03.2025, стоимость составляет 180000 рублей."

    assert not significant_numbers(rewritten) - significant_numbers(draft)


def test_file_that_is_not_a_document_is_refused():
    with pytest.raises(BadZipFile):
        assert_editable_docx(b"just some bytes")


def test_document_without_any_text_is_refused():
    empty = BytesIO()
    Document().save(empty)

    with pytest.raises(AssertionError, match="пуст"):
        assert_editable_docx(empty.getvalue())
