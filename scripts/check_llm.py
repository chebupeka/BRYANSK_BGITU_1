"""Check that a model server answers the way the llm processor needs, using only the stdlib.

Usage: python scripts/check_llm.py [base_url] [model]
Defaults come from .env (LLM_BASE_URL, LLM_MODEL), so on a configured machine
the script runs without arguments. Works against a local or a remote Ollama.
"""

import json
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DRAFT = "Прошу сагласовать закупку двух мониторов. Нужно 30 000 рублей до 25.09.2026."


def from_env_file(name, fallback):
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name and value.strip():
                return value.strip()
    return fallback


def call(url, payload=None, timeout=180):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    with urlopen(Request(url, data=data, headers=headers), timeout=timeout) as response:
        return json.loads(response.read())


def main():
    base_url = (sys.argv[1] if len(sys.argv) > 1 else
                from_env_file("LLM_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
    model = sys.argv[2] if len(sys.argv) > 2 else from_env_file("LLM_MODEL", "")
    root = base_url.removesuffix("/v1")
    print(f"Сервер: {base_url}")

    address = urlsplit(base_url)
    host, port = address.hostname or base_url, address.port or 11434
    try:
        tags = call(f"{root}/api/tags", timeout=10)
    except (URLError, HTTPError, OSError) as error:
        reason = getattr(error, "reason", error)
        print(f"Нет связи: {error}")
        looks_like_ip = host.replace(".", "").isdigit()
        if isinstance(reason, socket.gaierror):
            print(f"Имя «{host}» не удалось разрешить. Проверьте, что обе машины в одной "
                  "частной сети и что включён MagicDNS, либо укажите адрес вида 100.x.x.x.")
        elif not looks_like_ip and "timed out" in str(error):
            # Короткое имя macOS ищет через mDNS и молчит до таймаута, а не отвечает отказом.
            print(f"«{host}» не ответил вовремя. Либо имя не разрешается — компьютер не "
                  "подключён к частной сети или выключен MagicDNS, либо закрыт порт "
                  f"{port}. Проверьте адресом вида 100.x.x.x.")
        else:
            print(f"Порт {port} на «{host}» не отвечает. Проверьте, что Ollama запущена, "
                  "открыта в сеть (OLLAMA_HOST=0.0.0.0) и что брандмауэр её пропускает.")
        return 1

    names = [item["name"] for item in tags.get("models", [])]
    print("Модели на сервере:", ", ".join(names) if names else "ни одной")
    if not model:
        print("Задайте модель: LLM_MODEL в .env или вторым аргументом.")
        return 1
    if model not in names:
        print(f"Модель «{model}» на сервере не найдена. Выполните: ollama pull {model}")
        return 1

    started = time.monotonic()
    try:
        answer = call(f"{base_url}/chat/completions", {
            "model": model,
            "messages": [
                {"role": "system", "content": "Отвечай одним объектом JSON без пояснений."},
                {"role": "user", "content":
                    "Перепиши в деловом стиле, факты не меняй. Ответь строго так: "
                    '{"body": ["абзац"]}. Черновик: ' + DRAFT},
            ],
            "stream": False,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        })
    except (URLError, HTTPError, OSError) as error:
        print(f"Запрос не прошёл: {error}")
        return 1

    spent = time.monotonic() - started
    content = answer["choices"][0]["message"]["content"]
    body = json.loads(content).get("body", [])
    text = " ".join(body)
    print(f"Ответ получен за {spent:.1f} с")
    print("Текст:", text[:300] or "пусто")
    for fact in ("30 000", "25.09.2026"):
        print(f"  факт {fact} на месте:", fact in text)
    print("Проверка пройдена: сервер отвечает строгим JSON и держит факты.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
