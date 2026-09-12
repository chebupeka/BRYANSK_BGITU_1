"""Прогон всего корпуса «грязных» черновиков из examples/drafts.

Сценарии проверяют отдельные случаи, а этот набор — каждый вход корпуса целиком:
факты доходят до файла, новых чисел не появляется, отсутствующие реквизиты остаются пустыми.
"""

import pytest
from qa_support import (
    CORPUS_DIR,
    assert_editable_docx,
    docx_text,
    download,
    keeps,
    load_cases,
    process,
    significant_numbers,
)

CASES = load_cases()
IDS = [case.id for case in CASES]
draft_case = pytest.mark.parametrize("case", CASES, ids=IDS)


def test_corpus_covers_every_document_type(catalog):
    covered = {case.doc_type for case in CASES}
    expected = {doc_type["id"] for doc_type in catalog["doc_types"]}

    assert covered == expected, f"Типы без тестовых черновиков: {expected - covered}"


def test_corpus_ids_are_unique_and_files_exist():
    assert len(IDS) == len(set(IDS)), "Совпадающие идентификаторы случаев в манифесте"
    for case in CASES:
        assert (CORPUS_DIR / case.file).is_file(), f"Нет файла черновика {case.file}"


@draft_case
def test_manifest_describes_the_draft_truthfully(case, field_labels):
    known = set(field_labels[case.doc_type])
    assert set(case.in_draft) <= known, f"Неизвестные реквизиты в in_draft: {case.id}"
    assert set(case.not_in_draft) <= known, f"Неизвестные реквизиты в not_in_draft: {case.id}"
    assert not set(case.in_draft) & set(case.not_in_draft), (
        f"Реквизит одновременно назван и отсутствующим: {case.id}"
    )
    for field_id, value in case.in_draft.items():
        assert keeps(case.draft, value), (
            f"Манифест обещает «{value}» для «{field_id}», но в черновике этого нет"
        )
    for value in case.must_keep:
        assert keeps(case.draft, value), f"Значение «{value}» отсутствует в самом черновике"


@draft_case
def test_draft_facts_reach_the_finished_document(client, case):
    prepared = process(client, case.draft, case.doc_type)

    text = docx_text(download(client, prepared["document"], "classic"))

    for value in case.must_keep:
        assert keeps(text, value), f"«{case.label}»: значение «{value}» потеряно"


@draft_case
def test_processing_adds_no_numbers_that_were_not_in_the_draft(client, case):
    prepared = process(client, case.draft, case.doc_type)

    text = docx_text(download(client, prepared["document"], "classic"))

    invented = significant_numbers(text) - significant_numbers(case.draft)
    assert not invented, f"«{case.label}»: в документе появились числа {invented}"


@draft_case
def test_requisites_absent_from_the_draft_stay_empty(client, case, required_fields):
    prepared = process(client, case.draft, case.doc_type)

    required = set(required_fields[case.doc_type])
    reported = {field["id"] for field in prepared["missing_fields"]}
    for field_id in case.not_in_draft:
        value = prepared["document"]["requisites"].get(field_id, "")
        assert not value.strip(), (
            f"«{case.label}»: реквизит «{field_id}» заполнен значением «{value}», "
            "которого нет в черновике"
        )
        # О пропуске сообщают по обязательным реквизитам: необязательный просто не
        # печатается, и в missing_fields его нет — но выдумывать значение нельзя и для него.
        if field_id in required:
            assert field_id in reported, (
                f"«{case.label}»: о пропуске реквизита «{field_id}» не сообщено пользователю"
            )


@draft_case
def test_every_draft_produces_an_openable_document(client, case, field_labels):
    prepared = process(client, case.draft, case.doc_type)

    data = download(client, prepared["document"], "classic")

    assert_editable_docx(data)
    text = docx_text(data)
    for field in prepared["missing_fields"]:
        assert f"[Заполнить: {field['label']}]" in text, (
            f"«{case.label}»: реквизит «{field['label']}» не помечен как незаполненный"
        )
