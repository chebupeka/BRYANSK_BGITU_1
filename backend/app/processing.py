"""Обработка черновика: заглушка, демонстрация отказа и адаптер локальной модели.

Адаптер работает по OpenAI-совместимому API (`/v1/chat/completions`), который отдаёт
Ollama. Ответ модели проверяется схемой и независимой сверкой фактов: сведения,
которых нет в черновике или в ответах пользователя, не попадают в документ молча.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas import DocumentContent, DocumentType, ProcessRequest, ProcessResponse

MAX_ATTEMPTS = 2  # основной запрос и не более одного повтора
MAX_CHANGES = 10
MAX_CHANGE_LENGTH = 200
MAX_REQUISITE_LENGTH = 500  # совпадает с ShortText в schemas.py
MAX_LISTED_FACTS = 5

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
MONTHS = "январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр"
DATE = re.compile(
    rf"\d{{4}}[-./]\d{{1,2}}[-./]\d{{1,2}}"
    rf"|\d{{1,2}}[-./]\d{{1,2}}[-./]\d{{2,4}}"
    rf"|\d{{1,2}}\s+(?:{MONTHS})\w*(?:\s+\d{{4}})?",
    re.IGNORECASE,
)
NAME = re.compile(
    r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]*(?:ович|евич|ич|овна|евна|ична)\b"
    r"|[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]*(?:ович|евич|ич|овна|евна|ична)\b"
    r"|[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.?"
    r"|[А-ЯЁ]\.\s*[А-ЯЁ]\.?\s*[А-ЯЁ][а-яё]+"
)
NAME_WORD = re.compile(r"[А-ЯЁ][а-яё]{2,}")
NUMBER = re.compile(r"\d[\d\u00a0\u202f .,]*\d|\d")
MONTH_PREFIXES = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "ма": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}

SYSTEM_PROMPT = (
    "Ты — редактор официально-деловых документов на русском языке. Ты исправляешь орфографию "
    "и пунктуацию и переписываешь текст в официально-деловом стиле, сохраняя исходный смысл, "
    "все условия и оговорки.\n"
    "Запрещено добавлять, изменять и уточнять факты: даты, суммы, количества, номера, "
    "наименования, должности и имена. Нельзя раскрывать инициалы в полное имя, добавлять год "
    "к дате, округлять и пересчитывать суммы, переводить словесные числа в цифры.\n"
    "Если сведений нет в черновике и пользователь их не указал — оставь поле пустым. "
    "Пустое поле лучше выдуманного.\n"
    "Отвечай одним объектом JSON без пояснений и без разметки markdown."
)
RETRY_HINT = (
    "Предыдущий ответ отклонён: {problem}. Повтори ответ строго в том же формате JSON, "
    "используя только сведения из черновика и уже указанных реквизитов. "
    "Ничего не добавляй от себя."
)


class ProcessorUnavailable(Exception):
    pass


@dataclass
class ProcessorResult:
    """Что обработчик передаёт дальше: содержание, перечень правок и предупреждения."""

    document: DocumentContent
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TextProcessor(Protocol):
    """Граница обработки текста: заглушка, отказ или адаптер модели."""

    mode: str

    def process(self, request: ProcessRequest, doc_type: DocumentType) -> ProcessorResult: ...


class StubProcessor:
    mode = "stub"

    def process(self, request: ProcessRequest, doc_type: DocumentType) -> ProcessorResult:
        # No rewriting or fact extraction: every nonempty source line stays verbatim.
        document = DocumentContent(
            doc_type=request.doc_type,
            requisites=request.requisites,
            body=[line for line in request.draft.splitlines() if line.strip()],
        )
        return ProcessorResult(
            document=document,
            warnings=[
                "Демонстрационный режим: текст перенесён без исправлений. "
                "Проверка орфографии и делового стиля пока не подключена."
            ],
        )


class UnavailableProcessor:
    mode = "unavailable"

    def process(self, request: ProcessRequest, doc_type: DocumentType) -> ProcessorResult:
        raise ProcessorUnavailable("Обработка временно недоступна. Черновик сохранён в форме.")


class LLMReply(BaseModel):
    """Ожидаемая форма ответа модели. Лишние ключи игнорируются, а не ломают подготовку."""

    model_config = ConfigDict(extra="ignore")

    requisites: dict[str, str | None] = Field(default_factory=dict)
    body: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)


class LLMProcessor:
    """Адаптер модели через OpenAI-совместимый API: по умолчанию локальная Ollama."""

    mode = "llm"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=timeout)

    def process(self, request: ProcessRequest, doc_type: DocumentType) -> ProcessorResult:
        answered = {key: value for key, value in request.requisites.items() if value.strip()}
        # Факты извлекаются из источника отдельно от модели: сверять ответ с самим ответом нельзя.
        confirmed = extract_facts(request.draft, *answered.values())
        messages = build_messages(request, doc_type, answered)
        reply: LLMReply | None = None
        problem = ""
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                hint = RETRY_HINT.format(problem=problem)
                messages = [*messages, {"role": "user", "content": hint}]
            try:
                candidate = parse_reply(self._ask(messages))
            except ValueError as error:
                problem = str(error)
                continue  # схема нарушена: пробуем повтор, но сохраняем прошлый годный ответ
            reply = candidate
            invented = unconfirmed_facts(
                [*candidate.body, *candidate.requisites.values()], confirmed
            )
            if not invented:
                break
            problem = "в ответе есть сведения, которых нет в черновике: " + ", ".join(invented)
        if reply is None:
            raise ProcessorUnavailable(
                "Модель не вернула корректный ответ даже после повтора. "
                "Черновик сохранён в форме, попробуйте ещё раз."
            )
        return self._build(request, doc_type, reply, answered, confirmed)

    def _build(
        self,
        request: ProcessRequest,
        doc_type: DocumentType,
        reply: LLMReply,
        answered: dict[str, str],
        confirmed: set[str],
    ) -> ProcessorResult:
        warnings: list[str] = []
        requisites = dict(answered)
        for requisite in doc_type.fields:
            if requisite.id in requisites:
                continue  # ответ пользователя важнее догадки модели
            value = (reply.requisites.get(requisite.id) or "").strip()
            if not value or len(value) > MAX_REQUISITE_LENGTH:
                continue
            if unconfirmed_facts([value], confirmed):
                # Дискретное поле можно безопасно обнулить: останется метка «Заполнить».
                warnings.append(
                    f"Реквизит «{requisite.label}» не подтверждён черновиком и оставлен пустым."
                )
                continue
            requisites[requisite.id] = value
        body = [paragraph for paragraph in reply.body if paragraph.strip()]
        if not body:
            raise ProcessorUnavailable(
                "Модель вернула пустой текст. Черновик сохранён в форме, попробуйте ещё раз."
            )
        # Абзац удалять нельзя: вместе с лишним числом пропал бы и смысл. Поэтому помечаем.
        invented = unconfirmed_facts(body, confirmed)
        if invented:
            warnings.append(
                "Проверьте текст перед отправкой: в нём есть сведения, которых нет в черновике — "
                + ", ".join(invented)
                + "."
            )
        try:
            document = DocumentContent(
                doc_type=request.doc_type, requisites=requisites, body=body
            )
        except ValidationError as error:
            raise ProcessorUnavailable(
                "Ответ модели не прошёл проверку контракта. Черновик сохранён в форме."
            ) from error
        return ProcessorResult(document=document, changes=reply.changes, warnings=warnings)

    def _ask(self, messages: list[dict[str, str]]) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "temperature": 0.2,
            # Ollama переводит это в строгий JSON-режим; схему всё равно проверяет Pydantic.
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as error:
            raise ProcessorUnavailable(
                "Модель недоступна: проверьте, что Ollama запущена и модель загружена. "
                "Черновик сохранён в форме."
            ) from error
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProcessorUnavailable(
                "Модель вернула неожиданный ответ. Черновик сохранён в форме."
            ) from error
        if not isinstance(content, str):
            raise ProcessorUnavailable(
                "Модель вернула неожиданный ответ. Черновик сохранён в форме."
            )
        return content


def build_messages(
    request: ProcessRequest, doc_type: DocumentType, answered: dict[str, str]
) -> list[dict[str, str]]:
    lines = []
    for requisite in doc_type.fields:
        value = answered.get(requisite.id, "")
        state = f'указано пользователем: "{value}" — не меняй' if value else "не указано"
        need = "обязателен" if requisite.required else "необязателен"
        lines.append(f'- "{requisite.id}" — {requisite.label} ({need}); {state}')
    schema = (
        '{"requisites": {'
        + ", ".join(f'"{requisite.id}": ""' for requisite in doc_type.fields)
        + '}, "body": ["первый абзац", "второй абзац"], "changes": ["что исправлено"]}'
    )
    user = (
        f"Тип документа: {doc_type.name} — {doc_type.description}\n\n"
        "Реквизиты этого типа:\n" + "\n".join(lines) + "\n\n"
        f"Черновик пользователя:\n<<<\n{request.draft}\n>>>\n\n"
        "Задача:\n"
        "1. Исправь ошибки и приведи текст к официально-деловому стилю, сохранив все факты.\n"
        "2. Раздели результат на абзацы и помести их в массив body. Заголовок документа "
        "и строки реквизитов в body не включай.\n"
        "3. В requisites перенеси только значения, прямо названные в черновике; "
        "для остальных оставь пустую строку.\n"
        f"4. В changes перечисли до {MAX_CHANGES} коротких описаний правок.\n\n"
        f"Ответь строго в таком виде:\n{schema}"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_reply(raw: str) -> LLMReply:
    data = json.loads(find_json(raw))
    if not isinstance(data, dict):
        raise ValueError("ожидался объект JSON")
    try:
        reply = LLMReply.model_validate(data)
    except ValidationError as error:
        raise ValueError("ответ не соответствует схеме requisites/body/changes") from error
    reply.requisites = {
        key: clean_text(value) for key, value in reply.requisites.items() if isinstance(value, str)
    }
    reply.body = [
        line.strip()
        for paragraph in reply.body
        for line in clean_text(paragraph).split("\n")
        if line.strip()
    ]
    reply.changes = [
        clean_text(change)[:MAX_CHANGE_LENGTH] for change in reply.changes if change.strip()
    ][:MAX_CHANGES]
    if not reply.body:
        raise ValueError("в ответе нет текста документа")
    return reply


def find_json(raw: str) -> str:
    """Небольшие модели добавляют пояснения и ```json вокруг ответа: берём сам объект."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("ответ не является корректным JSON")
    return text[start : end + 1]


def clean_text(value: str) -> str:
    return CONTROL_CHARS.sub("", value.replace("\r\n", "\n")).strip()


def extract_facts(*texts: str) -> set[str]:
    """Даты, имена и числа из текста — единый вид для сравнения черновика и ответа модели."""
    facts: set[str] = set()
    for text in texts:
        if not text or not text.strip():
            continue
        for match in DATE.finditer(text):
            facts.add(f"дата {canonical_date(match.group())}")
        without_dates = DATE.sub(" ", text)
        for match in NAME.finditer(without_dates):
            # Сравниваются слова, а не написание: «Иванов И. И.» короче «Иванова Ивана», но
            # не добавляет нового. Обратное — раскрытие инициалов — добавляет и будет видно.
            facts.update(f"имя {word.lower()}" for word in NAME_WORD.findall(match.group()))
        without_names = NAME.sub(" ", without_dates)
        for match in NUMBER.finditer(without_names):
            digits = re.sub(r"\D", "", match.group())
            if len(digits) < 2 and is_list_marker(without_names, match):
                continue  # нумерация списка — оформление, а не факт
            if digits:
                facts.add(f"число {digits.lstrip('0') or '0'}")
    return facts


def unconfirmed_facts(texts: list[str], confirmed: set[str]) -> list[str]:
    invented = sorted(extract_facts(*texts) - confirmed)
    if len(invented) > MAX_LISTED_FACTS:
        return [*invented[:MAX_LISTED_FACTS], "…"]
    return invented


def is_list_marker(text: str, match: re.Match[str]) -> bool:
    before = text[: match.start()].rstrip(" \t")
    after = text[match.end() : match.end() + 1]
    return (not before or before.endswith("\n")) and after in {".", ")"}


def canonical_date(text: str) -> str:
    """«25.09.2026», «2026-09-25» и «25 сентября 2026» сводятся к одному виду."""
    parts = re.findall(r"\d+", text)
    numbers = [int(part) for part in parts]
    month_word = re.search(r"[а-яё]+", text.lower())
    if month_word:
        day = numbers[0] if numbers else 0
        month = month_number(month_word.group())
        year = numbers[1] if len(numbers) > 1 else 0
    elif len(numbers) >= 3 and len(parts[0]) == 4:
        year, month, day = numbers[0], numbers[1], numbers[2]
    elif len(numbers) >= 3:
        day, month, year = numbers[0], numbers[1], numbers[2]
    else:
        return text.lower()
    if 0 < year < 100:
        year += 2000
    return f"{day:02d}.{month:02d}.{year:04d}"


def month_number(word: str) -> int:
    for prefix in sorted(MONTH_PREFIXES, key=len, reverse=True):
        if word.startswith(prefix):
            return MONTH_PREFIXES[prefix]
    return 0


def get_processor(
    mode: str,
    *,
    llm_base_url: str = "",
    llm_model: str = "",
    llm_api_key: str = "",
    llm_timeout_seconds: float = 120.0,
) -> TextProcessor:
    if mode == "stub":
        return StubProcessor()
    if mode == "unavailable":
        return UnavailableProcessor()
    if mode == "llm":
        if not llm_base_url.strip() or not llm_model.strip():
            raise ValueError(
                "TEXT_PROCESSOR=llm требует LLM_BASE_URL и LLM_MODEL в .env "
                "(например, http://localhost:11434/v1 и qwen2.5:7b-instruct)"
            )
        return LLMProcessor(llm_base_url, llm_model, llm_api_key, llm_timeout_seconds)
    raise ValueError(f"Unsupported text processor: {mode}")


def prepare_document(
    request: ProcessRequest, doc_type: DocumentType, processor: TextProcessor
) -> ProcessResponse:
    result = processor.process(request, doc_type)
    missing = [field for field in doc_type.fields if field.required
               and not result.document.requisites.get(field.id, "").strip()]
    return ProcessResponse(
        document=result.document,
        missing_fields=missing,
        changes=result.changes,
        warnings=result.warnings,
        processor_mode=processor.mode,
    )
