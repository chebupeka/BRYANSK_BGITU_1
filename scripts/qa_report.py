"""Отчёт проверки: прогон корпуса черновиков и сверка сервиса с эталоном кейса.

Автотесты отвечают «прошло или нет», а этот отчёт показывает картину целиком: что стало
с каждым черновиком и чем настройки сервиса отличаются от требований заказчика.

Запуск из корня репозитория (нужен backend с установленными зависимостями):
    backend/.venv/Scripts/python scripts/qa_report.py
    backend/.venv/Scripts/python scripts/qa_report.py --out qa_samples

Ключ --out дополнительно сохраняет каждый тип документа в каждом шаблоне и один длинный
многостраничный документ, чтобы открыть их в Word или LibreOffice и проверить вёрстку глазами.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples" / "reference" / "case_reference.yaml"
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend" / "tests")]

LAYOUT_KEYS = (
    "font", "font_size", "line_spacing", "first_line_indent_mm",
    "title_alignment", "recipient_alignment", "body_alignment",
)


def build_client():
    from app.main import create_app
    from app.settings import Settings
    from fastapi.testclient import TestClient

    settings = Settings()
    return TestClient(create_app(settings)), settings.text_processor


def write_samples(client, out_dir, catalog):
    """Готовит файлы для просмотра глазами: каждый тип в каждом шаблоне и длинный документ."""
    from qa_support import case_by_id, download, process

    long_draft = "\n".join(
        "Отдел аналитики продолжает работу по плану, утверждённому 12.03.2025, "
        "и передаёт сведения для включения в сводный отчёт. " * 3
        for _ in range(40)
    )
    for doc_type in catalog["doc_types"]:
        case = case_by_id(f"{doc_type['id']}_01_structured")
        document = process(client, case.draft, doc_type["id"])["document"]
        for template in catalog["templates"]:
            data = download(client, document, template["id"])
            (out_dir / f"{doc_type['id']}-{template['id']}.docx").write_bytes(data)

    long_document = process(client, long_draft, "information_note")["document"]
    data = download(client, long_document, "classic")
    (out_dir / "long-information_note-classic.docx").write_bytes(data)


def check_corpus(client):
    """Гоняет каждый черновик до готового файла и собирает замечания по каждому случаю."""
    from qa_support import (
        assert_editable_docx,
        docx_text,
        download,
        keeps,
        load_cases,
        process,
        significant_numbers,
    )

    rows = []
    for case in load_cases():
        prepared = process(client, case.draft, case.doc_type)
        document = prepared["document"]
        data = download(client, document, "classic")
        text = docx_text(data)

        problems = []
        problems += [f"потеряно «{value}»" for value in case.must_keep if not keeps(text, value)]
        invented = sorted(significant_numbers(text) - significant_numbers(case.draft))
        if invented:
            problems.append(f"новые числа {invented}")
        problems += [
            f"реквизит «{field}» заполнен без основания"
            for field in case.not_in_draft
            if document["requisites"].get(field, "").strip()
        ]
        try:
            assert_editable_docx(data)
        except AssertionError as error:
            problems.append(f"файл: {error}")

        rows.append((case, len(prepared["missing_fields"]), problems))
    return rows


def check_reference(catalog):
    """Сверяет типы и шаблоны сервиса с перечнем реквизитов и описанием шаблонов из кейса."""
    import yaml

    reference = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    types = {item["id"]: item for item in catalog["doc_types"]}
    templates = {item["id"]: item for item in catalog["templates"]}
    findings = []

    for type_id, spec in reference["doc_types"].items():
        actual = types.get(type_id)
        if actual is None:
            findings.append(f"{spec['name']}: тип не реализован")
            continue
        required_now = {field["id"] for field in actual["fields"] if field["required"]}
        expected = {item["field"]: item["name"] for item in spec["required"] if "field" in item}
        for field_id, name in sorted(expected.items()):
            if field_id not in required_now:
                findings.append(
                    f"{spec['name']}: эталон требует «{name}» ({field_id}), в сервисе такого "
                    "обязательного реквизита нет"
                )
        known = {item.get("field") for item in spec["required"] + spec["optional"]}
        for field_id in sorted(required_now - known):
            findings.append(
                f"{spec['name']}: сервис требует «{field_id}», хотя в эталоне такого реквизита нет"
            )

    for template_id, spec in reference["templates"].items():
        actual = templates.get(template_id)
        if actual is None:
            findings.append(f"Шаблон «{spec['name']}» не реализован")
            continue
        for key in LAYOUT_KEYS:
            if actual.get(key) != spec[key]:
                findings.append(
                    f"Шаблон «{spec['name']}»: {key} = {actual.get(key)}, эталон — {spec[key]}"
                )
        for side, value in spec["margins_mm"].items():
            if actual["margins_mm"].get(side) != value:
                findings.append(
                    f"Шаблон «{spec['name']}»: поле {side} = "
                    f"{actual['margins_mm'].get(side)} мм, эталон — {value} мм"
                )
        if "header" not in actual:
            findings.append(
                f"Шаблон «{spec['name']}»: колонтитулы не заданы "
                f"(эталон: верхний — {spec['header']}, нижний — {spec['footer']})"
            )
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="куда сложить образцы DOCX для просмотра")
    arguments = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    out_dir = arguments.out
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    client, mode = build_client()
    with client:
        catalog = client.get("/api/catalog").json()
        rows = check_corpus(client)
        findings = check_reference(catalog)
        if out_dir:
            write_samples(client, out_dir, catalog)

    failed = sum(1 for _, _, problems in rows if problems)
    lines = [
        f"Режим обработки текста: {mode}",
        f"Типов документов: {len(catalog['doc_types'])}, шаблонов: {len(catalog['templates'])}",
        "",
        "КОРПУС ЧЕРНОВИКОВ",
    ]
    for case, missing, problems in rows:
        status = "ok  " if not problems else "ОШИБКА"
        lines.append(f"  {status} {case.id:<32} пропусков реквизитов: {missing:<2} {case.label}")
        lines += [f"         └ {problem}" for problem in problems]
    lines += ["", "СВЕРКА С ЭТАЛОНОМ КЕЙСА"]
    lines += [f"  — {finding}" for finding in findings] or ["  расхождений нет"]
    lines += [
        "",
        f"Итог: черновиков с замечаниями {failed} из {len(rows)}, "
        f"расхождений с эталоном {len(findings)}",
    ]

    print("\n".join(lines))
    if out_dir:
        (out_dir / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nОтчёт и образцы документов сохранены в {out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
