"""Вся проверка одной командой: автотесты, отчёт и образцы документов Word.

    python scripts/qa.py

При первом запуске сама создаёт окружение backend/.venv и ставит зависимости,
а при каждом следующем досинхронизирует их, если команда поменяла список библиотек.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
VENV = BACKEND / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def prepare_environment() -> None:
    if not PYTHON.exists():
        print("Первый запуск: создаю окружение, это займёт пару минут…")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    pip = [str(PYTHON), "-m", "pip", "install", "-q", "--disable-pip-version-check"]
    subprocess.check_call([*pip, "-r", str(BACKEND / "requirements-dev.lock")])
    subprocess.check_call([*pip, "--no-deps", "-e", str(BACKEND)])


def run(*arguments: str) -> int:
    # -X utf8: без него консоль Windows показывает русские сообщения об ошибках кракозябрами.
    return subprocess.call([str(PYTHON), "-X", "utf8", *arguments], cwd=ROOT)


def main() -> int:
    # Построчный вывод, иначе заголовки этапов появляются позже вывода самих проверок.
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    try:
        prepare_environment()
    except subprocess.CalledProcessError:
        print("\nНе удалось установить зависимости. Нужен Python 3.12 или новее и интернет.")
        return 1

    print("\n=== 1 из 2. Автоматические проверки ===")
    tests = run("-m", "pytest", "backend", "-q")

    print("\n=== 2 из 2. Отчёт по черновикам и сверка с заданием ===")
    report = run("scripts/qa_report.py", "--out", "qa_samples")

    print("\n=== ИТОГ ===")
    print("Автопроверки:", "всё прошло" if tests == 0 else "ЕСТЬ ОШИБКИ — ищи выше строки FAILED")
    print("Черновики:   ", "все в порядке" if report == 0 else "ЕСТЬ ЗАМЕЧАНИЯ — см. отчёт выше")
    print("Отчёт для команды: qa_samples/report.txt")
    print("Образцы документов Word: папка qa_samples")
    return 1 if tests or report else 0


if __name__ == "__main__":
    raise SystemExit(main())
