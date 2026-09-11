"""Отчёт о качестве обработки черновиков: один и тот же набор через выбранную модель.

Запуск из корня репозитория:
    backend/.venv/bin/python scripts/quality_report.py
    backend/.venv/bin/python scripts/quality_report.py --model qwen2.5:14b --json отчёт.json

Живая модель обязательна: скрипт меряет то, чего не видно на заглушках. Проверки берутся
из examples/quality_cases.yaml, сравнение сведений — из самого обработчика, поэтому
«30 000» и «тридцать тысяч» считаются одним и тем же. Модули приложения ввозятся внутри
функций: до этого в путь нужно добавить каталог backend.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "examples" / "quality_cases.yaml"


def use_backend() -> None:
    if str(ROOT / "backend") not in sys.path:
        sys.path.insert(0, str(ROOT / "backend"))


def check_case(case: dict, response, spent: float) -> dict:
    from app.processing import extract_facts

    document = response.document
    text = "\n".join([*document.body, *document.requisites.values()])
    known = extract_facts(text)
    checks: list[tuple[str, bool]] = []

    for fact in case.get("facts", []):
        checks.append((f"сведение «{fact}»", extract_facts(fact) <= known))
    for wrong, right in (case.get("fixed") or {}).items():
        fixed = wrong.lower() not in text.lower() and right.lower() in text.lower()
        checks.append((f"исправлено «{wrong}»", fixed))
    for phrase in case.get("forbid", []):
        checks.append((f"нет «{phrase}»", phrase.lower() not in text.lower()))
    for field in case.get("filled", []):
        checks.append((f"заполнен «{field}»", bool(document.requisites.get(field, "").strip())))
    for field in case.get("empty", []):
        checks.append((f"не выдуман «{field}»", not document.requisites.get(field, "").strip()))
    if case.get("keep_meaning"):
        kept = not any(word in " ".join(response.warnings) for word in ("смысл", "уточнения"))
        checks.append(("смысл сохранён", kept))
    if case.get("no_warnings"):
        checks.append(("без предупреждений", not response.warnings))

    passed = sum(1 for _, ok in checks if ok)
    return {
        "id": case["id"],
        "seconds": round(spent, 1),
        "passed": passed,
        "total": len(checks),
        "warnings": len(response.warnings),
        "failed": [name for name, ok in checks if not ok],
        "body": document.body,
        "requisites": document.requisites,
        "warning_texts": response.warnings,
    }


def run(model: str, base_url: str, timeout: float) -> list[dict]:
    import yaml

    from app.catalog import document_types
    from app.processing import LLMProcessor, ProcessorUnavailable, prepare_document
    from app.schemas import ProcessRequest

    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    types = document_types()
    results = []
    for case in cases:
        processor = LLMProcessor(base_url, model, timeout=timeout)  # свой кэш на каждый случай
        request = ProcessRequest(
            doc_type=case["doc_type"],
            draft=case["draft"].strip(),
            requisites=case.get("requisites") or {},
        )
        started = time.monotonic()
        try:
            response = prepare_document(request, types[case["doc_type"]], processor)
        except ProcessorUnavailable as error:
            results.append({"id": case["id"], "error": str(error), "passed": 0,
                            "total": 1, "seconds": round(time.monotonic() - started, 1),
                            "warnings": 0, "failed": ["обработка не удалась"]})
            print(f"  {case['id']}: отказ — {error}")
            continue
        result = check_case(case, response, time.monotonic() - started)
        results.append(result)
        mark = "ок" if result["passed"] == result["total"] else "внимание"
        print(f"  {result['id']}: {result['passed']}/{result['total']} "
              f"за {result['seconds']} с — {mark}")
    return results


def report(model: str, results: list[dict]) -> None:
    passed = sum(result["passed"] for result in results)
    total = sum(result["total"] for result in results)
    clean = sum(1 for result in results if result["passed"] == result["total"])
    seconds = sum(result["seconds"] for result in results)
    print(f"\nМодель: {model}")
    print(f"{'случай':<20} {'проверки':>10} {'предупр.':>9} {'секунды':>8}")
    for result in results:
        print(f"{result['id']:<20} {result['passed']:>4}/{result['total']:<5} "
              f"{result.get('warnings', 0):>9} {result['seconds']:>8}")
    print(f"{'итого':<20} {passed:>4}/{total:<5} {'':>9} {round(seconds, 1):>8}")
    print(f"случаев без замечаний: {clean} из {len(results)}")
    for result in results:
        if result["failed"]:
            print(f"\n{result['id']}: не прошло — {', '.join(result['failed'])}")
            for warning in result.get("warning_texts", []):
                print(f"   предупреждение: {warning}")


def main() -> int:
    use_backend()
    from app.settings import Settings

    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=settings.llm_model or "qwen2.5:7b-instruct")
    parser.add_argument("--base-url", default=settings.llm_base_url)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--json", type=Path, help="куда сохранить результат для сравнения моделей")
    args = parser.parse_args()

    print(f"Проверяю {args.model} на {args.base_url}")
    results = run(args.model, args.base_url, args.timeout)
    report(args.model, results)
    if args.json:
        args.json.write_text(
            json.dumps({"model": args.model, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nПодробности: {args.json}")
    return 0 if all(result["passed"] == result["total"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
