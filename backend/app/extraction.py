"""Разбор помеченных строк черновика: «Кому: директору» — это готовый реквизит.

Здесь нет догадок. Значение берётся, только если пользователь сам подписал строку
известным словом, поэтому подставленное можно показывать в форме без проверки модели.
"""

import re

from app.schemas import MAX_REQUISITE_LENGTH, DocumentType, check_xml_text

# Метка отделяется двоеточием или тире с пробелами; тире внутри значения не мешает.
LABEL_LINE = re.compile(r"^[\s>*•·-]*([^:\n]{2,40}?)\s*(?::|\s[—–-]\s)\s*(\S.*?)\s*$")
NUMBER_LINE = re.compile(r"^[\s>*•·-]*№\s*(\S.*?)\s*$")
INITIAL_AT_END = re.compile(r"\b[А-ЯЁA-Z]\.$")
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
    """Строки вида «Кому: директору»: их номер, поле и значение."""
    labels = field_labels(doc_type)
    has_number = any(field.id == "number" for field in doc_type.fields)
    for index, line in enumerate(lines):
        match = LABEL_LINE.match(line)
        if match:
            field_id = labels.get(normalize(match.group(1)))
            value = clean_value(match.group(2))
        elif has_number and (short := NUMBER_LINE.match(line)):
            # «№ 12-45» подписью не выглядит, но означает ровно исходящий номер.
            field_id, value = "number", clean_value(short.group(1))
        else:
            continue
        if field_id and value:
            yield index, field_id, value


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
