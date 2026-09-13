"""Разбор помеченных строк черновика: «Кому: директору» — это готовый реквизит.

Здесь нет догадок. Значение берётся там, где пользователь сам подписал строку известным
словом или написал её в общепринятом виде: «№ 12-45», дата отдельной строкой, «Приложение
на 2 листах». Адресата и подписанта из обычного текста не выводим: это уже догадка,
а пустое поле честнее выдуманного.
"""

import re

from app.dates import DATE
from app.schemas import MAX_REQUISITE_LENGTH, DocumentType, check_xml_text

# Метка отделяется двоеточием или тире с пробелами; тире внутри значения не мешает.
LABEL_LINE = re.compile(r"^[\s>*•·-]*([^:\n]{2,40}?)\s*(?::|\s[—–-]\s)\s*(\S.*?)\s*$")
NUMBER_LINE = re.compile(r"^[\s>*•·-]*(?:исх\.?\s*)?№\s*(\S.*?)\s*$", re.IGNORECASE)
# Дата отдельной строкой — это дата документа: в тексте она стояла бы рядом со словами.
DATE_ONLY_LINE = re.compile(
    rf"^[\s>*•·-]*({DATE.pattern})\s*(?:г\.?|года)?\s*$", re.IGNORECASE
)
ATTACHMENT_LINE = re.compile(r"^[\s>*•·-]*приложени[ея]\s+(\S.*?)\s*$", re.IGNORECASE)
INITIAL_AT_END = re.compile(r"\b[А-ЯЁA-Z]\.$")

# Метка без разделителя: «Дата 12.03.2025», «Номер 47-СЗ». В обычной фразе те же слова
# встречаются постоянно («Дата поставки пока не известна»), поэтому такая строка
# принимается только для нескольких меток и только когда значение имеет строгую форму.
UNSEPARATED_LINE = re.compile(
    r"^[\s>*•·-]*(исходящий\s+номер|номер|дата|подписант|подпись|заголовок|тема)\s+(\S.*?)\s*$",
    re.IGNORECASE,
)
UNSEPARATED_LABELS = {
    "исходящий номер": "number",
    "номер": "number",
    "дата": "date",
    "подписант": "signer",
    "подпись": "signer",
    "заголовок": "subject",
    "тема": "subject",
}
# Номер — одно слово с цифрой, без пробелов внутри; «от 11.09.2026» разберёт split_number_and_date.
NUMBER_VALUE = re.compile(rf"№?\s*[\w./-]*\d[\w./-]*(?:\s+от\s+(?:{DATE.pattern}))?", re.IGNORECASE)
# «12 марта 2025 года» — в значение идёт только сама дата, как у даты отдельной строкой.
DATE_VALUE = re.compile(rf"({DATE.pattern})(?:\s*(?:г\.?|года))?", re.IGNORECASE)
# Фамилия с инициалами до или после. Без инициалов слово с заглавной буквы может быть
# чем угодно («Подпись Отсутствует»), поэтому одна фамилия берётся только с типичным окончанием.
INITIALS = r"[А-ЯЁ]\.\s?(?:[А-ЯЁ]\.)?"
SURNAME = r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?"
SIGNER_VALUE = re.compile(rf"(?:{INITIALS}\s*{SURNAME}|{SURNAME}\s+{INITIALS})\.?")
BARE_SURNAME_VALUE = re.compile(
    r"[А-ЯЁ][а-яё]*(?:ов|ев|ёв|ин|ын|ова|ева|ёва|ина|ына|ский|цкий|ская|цкая|енко|ук|юк|ич)\.?"
)
# Тема — короткий заголовок «О чём-то» с заглавной буквы и без знаков конца фразы внутри:
# «Тема встречи обсуждалась вчера» и «тема о закупке обсуждалась» так не пишут.
SUBJECT_VALUE = re.compile(r"(?:О|Об|Обо|Про)\s[^.!?;:]{2,100}\.?")
FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "recipient": ("кому", "адресат", "получатель", "кому направляется"),
    "sender": ("от кого", "от", "отправитель", "автор", "заявитель"),
    "subject": ("тема", "о чем", "предмет", "касательно", "заголовок", "о чем справка"),
    "date": ("дата", "дата документа", "дата составления", "составлено"),
    "signer": ("подписант", "подпись", "подписывает", "подписал"),
    "organization": (
        "организация", "организация отправителя", "учреждение", "предприятие", "компания",
    ),
    "number": ("исходящий номер", "исходящий", "номер", "регистрационный номер", "рег номер"),
    "attachment": ("приложение", "приложения"),
    "purpose": ("назначение", "назначение справки", "для предъявления", "куда предъявляется"),
}


def suggest_requisites(draft: str, doc_type: DocumentType) -> dict[str, str]:
    """Реквизиты, прямо подписанные в черновике. Первое упоминание важнее повторов."""
    found: dict[str, str] = {}
    for _, field_id, value in scan(draft.splitlines(), doc_type):
        found.setdefault(field_id, value)
    return found


def body_lines(lines: list[str], doc_type: DocumentType) -> list[str]:
    """Текст без подписанных реквизитов: они уходят в шапку документа, а не в абзацы."""
    marked = {index for index, _, _ in scan(lines, doc_type)}
    kept = [line for index, line in enumerate(lines) if index not in marked and line.strip()]
    # Черновик из одних реквизитов тоже документ: лучше повтор, чем пустой текст.
    return kept or [line for line in lines if line.strip()]


def scan(lines: list[str], doc_type: DocumentType):
    """Строки-реквизиты черновика: их номер, поле и значение."""
    labels = field_labels(doc_type)
    fields = {field.id for field in doc_type.fields}
    for index, line in enumerate(lines):
        found = (
            labelled_value(line, labels)
            or unseparated_value(line, fields)
            or usual_value(line, fields)
        )
        if not found:
            continue
        for field_id, value in split_number_and_date(*found, fields):
            if field_id in fields and value:
                yield index, field_id, value


def split_number_and_date(
    field_id: str, value: str, fields: set[str]
) -> list[tuple[str, str]]:
    """«12-45 от 11.09.2026» — это номер и дата, а не номер с хвостом."""
    if field_id != "number" or "date" not in fields:
        return [(field_id, value)]
    match = re.search(rf"\bот\s+({DATE.pattern})", value, re.IGNORECASE)
    if not match:
        return [(field_id, value)]
    return [("number", clean_value(value[: match.start()])), ("date", clean_value(match.group(1)))]


def labelled_value(line: str, labels: dict[str, str]) -> tuple[str, str] | None:
    match = LABEL_LINE.match(line)
    if not match:
        return None
    field_id = labels.get(normalize(match.group(1)))
    return (field_id, clean_value(match.group(2))) if field_id else None


def unseparated_value(line: str, fields: set[str]) -> tuple[str, str] | None:
    """«Дата 12.03.2025»: метка без разделителя, значение строгой формы."""
    match = UNSEPARATED_LINE.match(line)
    if not match:
        return None
    field_id = UNSEPARATED_LABELS[normalize(match.group(1))]
    value = match.group(2)
    if field_id not in fields or not has_shape(field_id, value):
        return None
    if field_id == "number":
        value = value.removeprefix("№").lstrip()
    elif field_id == "date":
        value = DATE_VALUE.fullmatch(value).group(1)
    return field_id, clean_value(value)


def has_shape(field_id: str, value: str) -> bool:
    if field_id == "number":
        return bool(NUMBER_VALUE.fullmatch(value))
    if field_id == "date":
        return bool(DATE_VALUE.fullmatch(value))
    if field_id == "signer":
        return bool(SIGNER_VALUE.fullmatch(value) or BARE_SURNAME_VALUE.fullmatch(value))
    return bool(SUBJECT_VALUE.fullmatch(value))


def usual_value(line: str, fields: set[str]) -> tuple[str, str] | None:
    """Записи, которые подписывать не принято, но толкуются однозначно."""
    if "number" in fields and (match := NUMBER_LINE.match(line)):
        return "number", clean_value(match.group(1))
    if "date" in fields and (match := DATE_ONLY_LINE.match(line)):
        return "date", clean_value(match.group(1))
    if "attachment" in fields and (match := ATTACHMENT_LINE.match(line)):
        # Слово «Приложение» добавит генератор, в значении остаётся только описание.
        return "attachment", clean_value(match.group(1))
    return None


def field_labels(doc_type: DocumentType) -> dict[str, str]:
    labels: dict[str, str] = {}
    for field in doc_type.fields:
        for keyword in (*FIELD_KEYWORDS.get(field.id, ()), field.label):
            label = normalize(keyword)
            if label:
                labels.setdefault(label, field.id)
    return labels


def normalize(label: str) -> str:
    """«О чём справка» и «о чем справка.» — одна и та же метка."""
    return re.sub(r"\s+", " ", label.replace("ё", "е").strip(" \t.;,*•·-")).lower()


def clean_value(value: str) -> str:
    text = value.strip().rstrip(" \t;,")
    # Точку в конце убираем, но не у инициалов: «Иванову И. И.» теряет смысл без неё.
    if text.endswith(".") and not INITIAL_AT_END.search(text):
        text = text[:-1].rstrip()
    if len(text) > MAX_REQUISITE_LENGTH:
        return ""
    try:
        return check_xml_text(text)
    except ValueError:
        return ""
