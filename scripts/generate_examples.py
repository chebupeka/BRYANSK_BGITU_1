"""Демонстрационные документы: черновики из examples/drafts проходят весь сценарий через API.

Запуск из корня репозитория (нужен только Python 3.12+, сторонние библиотеки не нужны):
    python3 scripts/generate_examples.py
    python3 scripts/generate_examples.py https://doc3.codeboom.pro

Для каждого случая из examples/drafts/manifest.yaml выполняются те же три запроса, что
делает интерфейс: подсказка реквизитов, обработка текста, выгрузка DOCX. Результат —
examples/generated/<имя черновика>.docx в оформлении classic; для первого черновика
каждого типа дополнительно <имя черновика>.modern.docx. Обработка ограничена по частоте,
поэтому между вызовами /api/process выдерживается пауза, а ответы 429 и 503 и обрывы
соединения повторяются.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "examples" / "drafts"
OUTPUT = ROOT / "examples" / "generated"

PROCESS_PAUSE = 3.5  # секунд между вызовами /api/process
RETRY_PAUSE = 20.0  # секунд ожидания после 429 или «сервис занят»
ATTEMPTS = 6
TIMEOUT = 300  # обработка текста моделью может занимать минуты


def read_manifest(path: Path) -> list[dict[str, str]]:
    """Достаёт из манифеста id, file и doc_type каждого случая.

    Манифест читается без PyYAML: скрипту нужны только три скалярных поля верхнего
    уровня случая, а они всегда записаны строкой «ключ: значение».
    """
    cases: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        start = re.match(r"^  - id:\s*(\S+)\s*$", line)
        if start:
            cases.append({"id": start.group(1)})
            continue
        field = re.match(r"^    (file|doc_type):\s*(\S+)\s*$", line)
        if field and cases:
            cases[-1][field.group(1)] = field.group(2)
    for case in cases:
        if "file" not in case or "doc_type" not in case:
            raise SystemExit(f"В манифесте у случая {case['id']} нет file или doc_type")
    return cases


def call(base: str, path: str, payload: dict) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, ATTEMPTS + 1):
        request = urllib.request.Request(
            base + path,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            if error.code in (429, 503) and attempt < ATTEMPTS:
                print(f"    {path}: {error.code}, повтор через {RETRY_PAUSE:.0f} с", flush=True)
                time.sleep(RETRY_PAUSE)
                continue
            raise SystemExit(f"{path}: HTTP {error.code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt < ATTEMPTS:
                print(f"    {path}: сеть ({error}), повтор через {RETRY_PAUSE:.0f} с", flush=True)
                time.sleep(RETRY_PAUSE)
                continue
            raise SystemExit(f"{path}: нет соединения: {error}") from error
    raise SystemExit(f"{path}: не удалось получить ответ за {ATTEMPTS} попыток")


def call_json(base: str, path: str, payload: dict) -> dict:
    content, _ = call(base, path, payload)
    return json.loads(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "base", nargs="?", default="http://localhost:8080", help="адрес сервиса без /api"
    )
    parser.add_argument(
        "--responses",
        type=Path,
        help="каталог, куда сохранить ответы /api/process в JSON (для разбора результата)",
    )
    parser.add_argument(
        "--only",
        action="append",
        metavar="ЧЕРНОВИК",
        help="обработать только этот черновик (имя файла без .txt); можно указать несколько раз",
    )
    arguments = parser.parse_args()
    base = arguments.base.rstrip("/")

    cases = read_manifest(DRAFTS / "manifest.yaml")
    known = {Path(case["file"]).stem for case in cases}
    unknown = sorted(set(arguments.only or []) - known)
    if unknown:
        raise SystemExit(f"В манифесте нет черновиков: {', '.join(unknown)}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if arguments.responses:
        arguments.responses.mkdir(parents=True, exist_ok=True)

    modern_done: set[str] = set()
    last_process = 0.0
    for case in cases:
        draft_path = DRAFTS / case["file"]
        name = draft_path.stem
        doc_type = case["doc_type"]
        # Оформление modern получает первый черновик типа по манифесту, даже если
        # обрабатываются не все черновики: иначе --only создал бы лишние .modern.docx.
        templates = ["classic"]
        if doc_type not in modern_done:
            templates.append("modern")
            modern_done.add(doc_type)
        if arguments.only and name not in arguments.only:
            continue
        draft = draft_path.read_text(encoding="utf-8")
        print(f"{name} ({doc_type})", flush=True)

        suggested = call_json(
            base, "/api/requisites/suggest", {"draft": draft, "doc_type": doc_type}
        )["requisites"]

        wait = PROCESS_PAUSE - (time.monotonic() - last_process)
        if wait > 0:
            time.sleep(wait)
        processed = call_json(
            base,
            "/api/process",
            {"draft": draft, "doc_type": doc_type, "requisites": suggested},
        )
        last_process = time.monotonic()
        if arguments.responses:
            (arguments.responses / f"{name}.json").write_text(
                json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        for template_id in templates:
            content, _ = call(
                base,
                "/api/documents/download",
                {"document": processed["document"], "template_id": template_id},
            )
            suffix = "" if template_id == "classic" else f".{template_id}"
            target = OUTPUT / f"{name}{suffix}.docx"
            target.write_bytes(content)
            print(f"  -> {target.relative_to(ROOT)}", flush=True)

        missing = ", ".join(field["label"] for field in processed["missing_fields"]) or "нет"
        print(
            f"  режим: {processed['processor_mode']}; не хватает: {missing}; "
            f"правок: {len(processed['changes'])}; предупреждений: {len(processed['warnings'])}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
