"""Обработка черновика: заглушка, демонстрация отказа и адаптер локальной модели.

Адаптер работает по OpenAI-совместимому API (`/v1/chat/completions`), который отдаёт
Ollama. Ответ модели проверяется схемой и независимой сверкой фактов: сведения,
которых нет в черновике или в ответах пользователя, не попадают в документ молча.
"""

import difflib
import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.extraction import body_lines
from app.schemas import (
    MAX_REQUISITE_LENGTH,
    DocumentContent,
    DocumentType,
    ProcessRequest,
    ProcessResponse,
)

MAX_ATTEMPTS = 2  # основной запрос и не более одного повтора
MAX_CHANGES = 10
MAX_CHANGE_LENGTH = 200
MAX_LISTED_FACTS = 5
MAX_NUMBER_DIGITS = 15  # длиннее — это склеенный список, а не сведение
MODEL_KEEP_ALIVE = "30m"  # чтобы модель не выгружалась между шагами показа
# Ollama по умолчанию держит окно в 4096 токенов, даже если модель умеет больше, и молча
# отбрасывает то, что не поместилось. Поэтому длинный черновик режем на части сами.
MODEL_CONTEXT_TOKENS = 4096
CHARS_PER_TOKEN = 2.2  # осторожная оценка для русского текста
ANSWER_GROWTH = 1.2  # переписанный текст обычно чуть длиннее исходного
MIN_PIECE = 400  # мельче резать бессмысленно
CACHE_SIZE = 16  # небольшой кэш подготовки: возврат на шаг назад не ждёт модель заново
NAME_TAG = "имя "
MIN_NAME_PREFIX = 5  # «иванов» и «иванову» — одно лицо, «иванов» и «иваненко» — разные

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
WORD = re.compile(r"\w+|[^\w\s]")
SIMILAR_ENOUGH = 0.8  # «сагласовать» и «согласовать» — опечатка, «покупку» и «закупку» — нет
MAX_EXAMPLE_LENGTH = 60
# Пробел разделяет разряды только перед группой из трёх цифр, запятая с пробелом —
# перечисление: «5, 7, 9» это три числа, а «30 000,50» одно.
NUMBER = re.compile(r"\d+(?:[ \u00a0\u202f]\d{3})*(?:,\d+)?")
# Числа словами: «30 000 (тридцать тысяч) рублей» — обычная форма делового документа,
# поэтому цифры и слова должны давать одно и то же сведение. Окончания перечислены явно:
# совпадение по началу слова превратило бы «стоимость» в сто.
WORD_NUMBERS: tuple[tuple[str, int], ...] = (
    (r"миллиард\w*|млрд", 1_000_000_000),
    (r"миллион\w*|млн", 1_000_000),
    (r"тысяч\w*|тыс", 1_000),
    (r"девятьсот|девятист\w+|девятьюст\w+", 900),
    (r"восемьсот|восьмист\w+|восемьюст\w+", 800),
    (r"семьсот|семист\w+|семьюст\w+", 700),
    (r"шестьсот|шестист\w+|шестьюст\w+", 600),
    (r"пятьсот|пятист\w+|пятьюст\w+", 500),
    (r"четыреста|четыр[её]хсот|четыр[её]мст\w+", 400),
    (r"триста|тр[её]хсот|тр[её]мст\w+|тремяст\w+", 300),
    (r"двести|двухсот|двумст\w+|двумяст\w+", 200),
    (r"сто|ста", 100),
    (r"девяност[оа]", 90),
    (r"восемьдесят|восьмидесяти|восемьюдесятью|восьмьюдесятью", 80),
    (r"семьдесят|семидесяти|семьюдесятью", 70),
    (r"шестьдесят|шестидесяти|шестьюдесятью", 60),
    (r"пятьдесят|пятидесяти|пятьюдесятью", 50),
    (r"сорок[а]?", 40),
    (r"тридцат[ьию]|тридцатью", 30),
    (r"двадцат[ьию]|двадцатью", 20),
    (r"девятнадцат[ьию]|девятнадцатью", 19),
    (r"восемнадцат[ьию]|восемнадцатью", 18),
    (r"семнадцат[ьию]|семнадцатью", 17),
    (r"шестнадцат[ьию]|шестнадцатью", 16),
    (r"пятнадцат[ьию]|пятнадцатью", 15),
    (r"четырнадцат[ьию]|четырнадцатью", 14),
    (r"тринадцат[ьию]|тринадцатью", 13),
    (r"двенадцат[ьию]|двенадцатью", 12),
    (r"одиннадцат[ьию]|одиннадцатью", 11),
    (r"десят[ьи]|десятью", 10),
    (r"девят[ьи]|девятью", 9),
    (r"восемь|восьми|вос[ье]мью", 8),
    (r"семь|семи|семью", 7),
    (r"шесть|шести|шестью", 6),
    (r"пять|пяти|пятью", 5),
    (r"четыре|четыр[её]х|четыр[её]м|четырьмя", 4),
    (r"три|тр[её]х|тр[её]м|тремя", 3),
    (r"два|две|двух|двум|двумя", 2),
    (r"один|одна|одно|одного|одной|одному|одним|одну", 1),
)
WORD_NUMBER = re.compile(
    "|".join(
        rf"(?P<v{index}>\b(?:{pattern})\b)"
        for index, (pattern, _) in enumerate(WORD_NUMBERS)
    ),
    re.IGNORECASE,
)
WORD_VALUES = {f"v{index}": value for index, (_, value) in enumerate(WORD_NUMBERS)}
BETWEEN_WORDS = re.compile(r"^[\s-]*$")

MONTH_PREFIXES = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "ма": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}

# Числа и даты сверяются точно, а смысл — нет. Эти обороты держат условия документа:
# потеря «если» или «не» меняет его сильнее, чем любая правка стиля.
MEANING_MARKERS = (
    ("условия", re.compile(
        r"\b(?:если|при\s+условии|в\s+случае|только|не\s+позднее|при\s+наличии|иначе|"
        r"обязательно|обязан\w*|должен|должна|должны|запрещ\w+|нельзя|не\s+допускается)\b",
        re.IGNORECASE,
    )),
    ("отрицания", re.compile(
        r"\b(?:не|ни|нет|без|отсутств\w+|неисправ\w+|невозможн\w+|отказ\w*)\b",
        re.IGNORECASE,
    )),
)

SYSTEM_PROMPT = (
    "Ты — редактор официально-деловых документов на русском языке.\n"
    "Твоя работа: исправить все орфографические и пунктуационные ошибки и переписать текст "
    "в официально-деловом стиле, без разговорных оборотов, жалоб и оценок. Переписывай каждое "
    "предложение: оставить опечатку или разговорную фразу — ошибка редактора.\n"
    "Запрещено добавлять, изменять и уточнять факты: даты, суммы, количества, номера, "
    "наименования, должности и имена. Нельзя раскрывать инициалы в полное имя, добавлять год "
    "к дате, округлять и пересчитывать суммы, переводить словесные числа в цифры. "
    "Слова менять нужно, факты — нельзя.\n"
    "Если сведений нет в черновике и пользователь их не указал — оставь поле пустым. "
    "Пустое поле лучше выдуманного.\n"
    "Отвечай одним объектом JSON без пояснений и без разметки markdown."
)
# Один пример вместо длинных инструкций: небольшие модели точнее повторяют образец.
EXAMPLE_DRAFT = (
    "Прошу выдилить деньги на ремонт принтера, а то он совсем сломался и печатать нечем. "
    "Нужно 12 000 рублей, желательно до 14.03.2026, только если деньги есть."
)
EXAMPLE_REPLY = (
    '{"requisites": {"subject": "О ремонте принтера"}, '
    '"body": ["Прошу выделить средства на ремонт принтера в связи с выходом оборудования '
    'из строя.", "Стоимость ремонта составляет 12 000 рублей. Работы необходимо выполнить '
    'до 14.03.2026 при условии наличия средств."]}'
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


def copy_result(result: ProcessorResult) -> ProcessorResult:
    """Отдельный экземпляр результата: кэш и вызывающий код не делят изменяемые списки."""
    return ProcessorResult(
        document=result.document.model_copy(deep=True),
        changes=list(result.changes),
        warnings=list(result.warnings),
    )


class TextProcessor(Protocol):
    """Граница обработки текста: заглушка, отказ или адаптер модели."""

    mode: str

    def process(self, request: ProcessRequest, doc_type: DocumentType) -> ProcessorResult: ...


class StubProcessor:
    mode = "stub"

    def process(self, request: ProcessRequest, doc_type: DocumentType) -> ProcessorResult:
        # Слова не меняются: каждая непустая строка переносится как есть. Исключение —
        # подписанные реквизиты вроде «Кому: директору»: они принадлежат шапке документа.
        document = DocumentContent(
            doc_type=request.doc_type,
            requisites=request.requisites,
            body=body_lines(request.draft.splitlines(), doc_type),
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
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._cache: OrderedDict[tuple, ProcessorResult] = OrderedDict()
        self._lock = threading.Lock()

    def process(self, request: ProcessRequest, doc_type: DocumentType) -> ProcessorResult:
        answered = {key: value for key, value in request.requisites.items() if value.strip()}
        key = (request.doc_type, request.draft, tuple(sorted(answered.items())))
        cached = self.cached(key)
        if cached is not None:
            return cached
        # Факты извлекаются из источника отдельно от модели: сверять ответ с самим ответом нельзя.
        confirmed = extract_facts(request.draft, *answered.values())
        # Модель переписывает текст документа. Подписанные реквизиты уже разобраны и ей мешают.
        source = "\n".join(body_lines(request.draft.splitlines(), doc_type))
        pieces = split_source(source, source_budget(doc_type, answered))
        replies = [self.rewrite(piece, doc_type, answered, confirmed) for piece in pieces]
        result = self._build(
            request, doc_type, merge_replies(replies), answered, confirmed, source
        )
        if len(pieces) > 1:
            # Целиком в окно модели черновик не помещается, и об этом честнее сказать.
            result.warnings.append(
                f"Черновик длинный, он обработан частями ({len(pieces)}). "
                "Проверьте связность текста между частями."
            )
        self.remember(key, result)
        return result

    def rewrite(
        self, source: str, doc_type: DocumentType, answered: dict[str, str], confirmed: set[str]
    ) -> LLMReply:
        """Одна часть черновика: запрос, проверка и не более одного повтора."""
        messages = build_messages(source, doc_type, answered)
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
        return reply

    def cached(self, key: tuple) -> ProcessorResult | None:
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            stored = self._cache[key]
        return copy_result(stored)

    def remember(self, key: tuple, result: ProcessorResult) -> None:
        # Оформление в ключ не входит: смена шаблона не трогает обработчик вовсе.
        # Хранится копия: вызывающий код держит ссылку на возвращённый результат.
        with self._lock:
            self._cache[key] = copy_result(result)
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)

    def _build(
        self,
        request: ProcessRequest,
        doc_type: DocumentType,
        reply: LLMReply,
        answered: dict[str, str],
        confirmed: set[str],
        source: str,
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
        body = body_lines([p for p in reply.body if p.strip()], doc_type)
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
        lost_meaning = lost_markers(source, body)
        if lost_meaning:
            warnings.append(
                "Проверьте смысл: из черновика пропали " + "; ".join(lost_meaning)
                + ". Убедитесь, что оговорки документа сохранены."
            )
        # Молчаливая потеря сведений так же опасна, как выдуманные: сверка работает в обе стороны.
        lost = missing_facts(confirmed, [*body, *requisites.values()])
        if lost:
            warnings.append(
                "Из черновика не попали в документ: " + ", ".join(lost) + ". Проверьте текст."
            )
        try:
            document = DocumentContent(
                doc_type=request.doc_type, requisites=requisites, body=body
            )
        except ValidationError as error:
            raise ProcessorUnavailable(
                "Ответ модели не прошёл проверку контракта. Черновик сохранён в форме."
            ) from error
        # Правки считаются сравнением текстов: модель уже приписывала себе
        # исправления, которых не делала.
        return ProcessorResult(
            document=document,
            changes=describe_changes(source, body),
            warnings=warnings,
        )

    def _ask(self, messages: list[dict[str, str]]) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            # Ноль и постоянное зерно ради повторяемости: один черновик — один документ.
            "temperature": 0,
            "seed": 0,
            # Ollama выгружает модель через пять минут простоя; на показе это лишняя пауза.
            "keep_alive": MODEL_KEEP_ALIVE,
            # Ollama переводит это в строгий JSON-режим; схему всё равно проверяет Pydantic.
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException as error:
            # Разные причины — разные подсказки: иначе на демонстрации их не различить.
            raise ProcessorUnavailable(
                f"Модель не ответила за отведённое время ({self._timeout:.0f} с). "
                "Черновик сохранён в форме: попробуйте ещё раз или возьмите модель меньше."
            ) from error
        except httpx.HTTPStatusError as error:
            reason = server_error_text(error.response)
            # Ollama отвечает на незагруженную модель кодом 400, а не 404: смотрим и на текст.
            if error.response.status_code == 404 or "not found" in reason.lower():
                raise ProcessorUnavailable(
                    f"Модель «{self._model}» не загружена. Выполните «ollama pull {self._model}» "
                    "или укажите другую модель в LLM_MODEL. Черновик сохранён в форме."
                ) from error
            raise ProcessorUnavailable(
                f"Сервер модели ответил ошибкой {error.response.status_code}: {reason}. "
                "Черновик сохранён в форме."
            ) from error
        except httpx.HTTPError as error:
            raise ProcessorUnavailable(
                "Нет связи с Ollama по адресу из LLM_BASE_URL: проверьте, что она запущена. "
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


def describe_changes(draft: str, body: list[str]) -> list[str]:
    """Что изменилось на самом деле: сравнение слов черновика и готового текста."""
    before = WORD.findall(draft)
    after = WORD.findall(" ".join(body))
    matcher = difflib.SequenceMatcher(
        None, [word.lower() for word in before], [word.lower() for word in after], autojunk=False
    )
    fixes: list[str] = []
    examples: list[str] = []
    rephrased = 0
    for tag, start_old, end_old, start_new, end_new in matcher.get_opcodes():
        if tag == "equal":
            continue
        was = " ".join(before[start_old:end_old])
        became = " ".join(after[start_new:end_new])
        # Соседние правки приходят одним куском: разбираем его по словам, иначе
        # исправленная опечатка теряется внутри переписанной фразы.
        aligned = (
            list(zip(before[start_old:end_old], after[start_new:end_new]))
            if tag == "replace" and end_old - start_old == end_new - start_new
            else []
        )
        if aligned:
            for left, right in aligned:
                if close_words(left, right):
                    fixes.append(f"Исправлено: «{left}» → «{right}»")
                else:
                    rephrased += 1
            continue
        rephrased += 1
        # В примеры идут только цельные фрагменты: замена одного слова мало что показывает.
        if tag == "replace" and len(examples) < 2 and was.strip() and became.strip():
            examples.append(f"Переформулировано: «{shorten(was)}» → «{shorten(became)}»")
    changes = [*dict.fromkeys(fixes), *examples]
    if rephrased > len(examples):
        changes.append(f"Другие правки формулировок: {rephrased - len(examples)}")
    return [change[:MAX_CHANGE_LENGTH] for change in changes[:MAX_CHANGES]]


def close_words(first: str, second: str) -> bool:
    return difflib.SequenceMatcher(None, first.lower(), second.lower()).ratio() >= SIMILAR_ENOUGH


def shorten(value: str) -> str:
    return value if len(value) <= MAX_EXAMPLE_LENGTH else value[:MAX_EXAMPLE_LENGTH].rstrip() + "…"


def server_error_text(response: httpx.Response) -> str:
    """Сообщение сервера модели целиком не показываем, но причину отказа сохраняем."""
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:200]
    error = payload.get("error", payload) if isinstance(payload, dict) else payload
    if isinstance(error, dict):
        error = error.get("message", "")
    return str(error).strip()[:200]


def source_budget(doc_type: DocumentType, answered: dict[str, str]) -> int:
    """Сколько символов черновика помещается в окно модели вместе с ответом."""
    overhead = sum(len(message["content"]) for message in build_messages("", doc_type, answered))
    window = MODEL_CONTEXT_TOKENS * CHARS_PER_TOKEN
    return max(MIN_PIECE, int((window - overhead) / (1 + ANSWER_GROWTH)))


def split_source(text: str, budget: int) -> list[str]:
    """Части не длиннее окна. Режем по абзацам, длинный абзац — по предложениям."""
    if len(text) <= budget:
        return [text]
    pieces: list[str] = []
    current = ""
    for block in text_blocks(text, budget):
        if current and len(current) + len(block) + 1 > budget:
            pieces.append(current)
            current = block
        else:
            current = f"{current}\n{block}" if current else block
    if current:
        pieces.append(current)
    return pieces


def text_blocks(text: str, budget: int) -> list[str]:
    blocks: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            continue
        if len(paragraph) <= budget:
            blocks.append(paragraph)
        else:
            blocks.extend(split_sentences(paragraph, budget))
    return blocks


def split_sentences(paragraph: str, budget: int) -> list[str]:
    parts: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        rest = sentence.strip()
        while len(rest) > budget:  # предложение длиннее окна: режем по границе слова
            cut = rest.rfind(" ", 0, budget)
            if cut <= 0:
                cut = budget
            parts.append(rest[:cut].strip())
            rest = rest[cut:].strip()
        if rest:
            parts.append(rest)
    return parts


def merge_replies(replies: list[LLMReply]) -> LLMReply:
    """Части собираются в один ответ: текст подряд, реквизит — первый непустой."""
    if len(replies) == 1:
        return replies[0]
    merged = LLMReply()
    for reply in replies:
        merged.body.extend(reply.body)
        merged.changes.extend(reply.changes)
        for field_id, value in reply.requisites.items():
            if value and not merged.requisites.get(field_id):
                merged.requisites[field_id] = value
    merged.changes = merged.changes[:MAX_CHANGES]
    return merged


def build_messages(
    draft: str, doc_type: DocumentType, answered: dict[str, str]
) -> list[dict[str, str]]:
    lines = []
    for requisite in doc_type.fields:
        value = answered.get(requisite.id, "")
        if value:
            state = f'указано пользователем: "{value}" — не меняй'
        elif requisite.summary:
            state = "не указано; сформулируй кратко по смыслу черновика, без новых сведений"
        else:
            state = "не указано; заполни, только если названо в черновике прямо"
        need = "обязателен" if requisite.required else "необязателен"
        lines.append(f'- "{requisite.id}" — {requisite.label} ({need}); {state}')
    schema = (
        '{"requisites": {'
        + ", ".join(f'"{requisite.id}": ""' for requisite in doc_type.fields)
        + '}, "body": ["первый абзац", "второй абзац"]}'
    )
    user = (
        f"Тип документа: {doc_type.name} — {doc_type.description}\n\n"
        "Реквизиты этого типа:\n" + "\n".join(lines) + "\n\n"
        f"Черновик пользователя:\n<<<\n{draft}\n>>>\n\n"
        "Задача:\n"
        "1. Проверь каждое слово на опечатки и исправь их: ни одно слово не должно остаться "
        "с ошибкой. Затем приведи текст к официально-деловому стилю, сохранив все факты. "
        "Разговорные обороты вроде «а то», «совсем», «плохо работают», «только если» замени "
        "официальными формулировками, сохранив смысл условий.\n"
        "2. Раздели результат на абзацы и помести их в массив body. Заголовок документа "
        "и строки реквизитов в body не включай.\n"
        "3. В requisites перенеси значения по правилу из списка выше: тему сформулируй "
        "сам, остальные поля заполняй только там, где они названы в черновике прямо. "
        "Не выводи дату документа из срока и не назначай подписантом того, кто просто "
        "упомянут в тексте. Где сведений нет, оставь пустую строку.\n"
        f"Ответь строго в таком виде:\n{schema}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Черновик пользователя:\n<<<\n{EXAMPLE_DRAFT}\n>>>"},
        {"role": "assistant", "content": EXAMPLE_REPLY},
        {"role": "user", "content": user},
    ]


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
            facts.update(
                f"{NAME_TAG}{word.lower()}" for word in NAME_WORD.findall(match.group())
            )
        without_names = NAME.sub(" ", without_dates)
        facts.update(f"число {value}" for value in word_numbers(without_names))
        for match in NUMBER.finditer(without_names):
            digits = re.sub(r"\D", "", match.group())
            if len(digits) < 2 and is_list_marker(without_names, match):
                continue  # нумерация списка — оформление, а не факт
            if digits and len(digits) <= MAX_NUMBER_DIGITS:
                facts.add(f"число {digits.lstrip('0') or '0'}")
    return facts


def word_numbers(text: str) -> set[int]:
    """«тридцать тысяч» -> 30000. Соседние слова складываются в одно число, как в речи."""
    found: set[int] = set()
    total = group = 0
    previous_end = -1
    for match in WORD_NUMBER.finditer(text):
        value = WORD_VALUES[match.lastgroup]
        if previous_end >= 0 and not BETWEEN_WORDS.match(text[previous_end : match.start()]):
            found.add(total + group)
            total = group = 0
        if value >= 1000:
            total += (group or 1) * value
            group = 0
        else:
            group += value
        previous_end = match.end()
    if previous_end >= 0:
        found.add(total + group)
    # Одиночные «один» и «ноль» — обороты речи, а не сведения документа.
    return {number for number in found if number >= 2}


def unconfirmed_facts(texts: list[str], confirmed: set[str]) -> list[str]:
    """Сведения из ответа модели, которых нет в черновике: их нельзя пропускать молча."""
    return facts_not_covered(extract_facts(*texts), confirmed)


def lost_markers(source: str, texts: list[str]) -> list[str]:
    """Условия и отрицания черновика, которых почти не осталось в документе."""
    result = " ".join(texts)
    lost = []
    for name, pattern in MEANING_MARKERS:
        found = [match.group().lower() for match in pattern.finditer(source)]
        if not found:
            continue
        # Переписывание сливает обороты, поэтому тревожим только при явной потере.
        if len(pattern.findall(result)) >= max(1, len(found) // 2):
            continue
        examples = list(dict.fromkeys(found))[:3]
        lost.append(f"{name} ({', '.join(examples)})")
    return lost


def missing_facts(confirmed: set[str], texts: list[str]) -> list[str]:
    """Обратная проверка: числа и даты из черновика, которые до документа не дошли.

    Имена сюда не входят: «Иванов И. И. просит выделить...» законно становится «Прошу
    выделить...», и автор уходит в реквизит. Выдуманное имя ловится в другую сторону.
    """
    return facts_not_covered(
        {fact for fact in confirmed if not fact.startswith(NAME_TAG)}, extract_facts(*texts)
    )


def facts_not_covered(wanted: set[str], available: set[str]) -> list[str]:
    names = [fact[len(NAME_TAG):] for fact in available if fact.startswith(NAME_TAG)]
    missing = []
    for fact in sorted(wanted - available):
        if fact.startswith(NAME_TAG):
            # Деловой текст склоняет фамилии: «Иванову И. И.» — тот же человек, а не новый.
            if any(same_name(fact[len(NAME_TAG):], known) for known in names):
                continue
        missing.append(fact)
    if len(missing) > MAX_LISTED_FACTS:
        return [*missing[:MAX_LISTED_FACTS], "…"]
    return missing


def same_name(first: str, second: str) -> bool:
    shared = 0
    for left, right in zip(first, second):
        if left != right:
            break
        shared += 1
    return shared >= MIN_NAME_PREFIX and shared >= min(len(first), len(second)) - 2


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
