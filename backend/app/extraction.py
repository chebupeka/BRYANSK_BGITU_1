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
# Номер — регистрационный: две-три части из цифр и заглавных букв через «-» или «/», хотя бы
# одна часть только из цифр («47-СЗ», «12-45», «01-12/345»). Голое число («Номер 2.») и порядковое
# числительное («Номер 1-й») номером не считаются. «от 11.09.2026» разберёт split_number_and_date.
NUMBER_PART = r"[0-9А-ЯЁA-Z]+"
NUMBER_VALUE = re.compile(
    rf"(?:№\s*)?({NUMBER_PART}(?:[-/]{NUMBER_PART}){{1,2}})(?:\s+от\s+(?i:{DATE.pattern}))?"
)
ORDINAL_ENDINGS = {
    "Й", "Я", "Е", "ГО", "МУ", "М", "Х", "Ю", "ЫЙ", "ИЙ", "ОЙ", "АЯ", "ЯЯ", "ОЕ", "ЕЕ",
    "ЫЕ", "ИЕ", "ЫХ", "ИХ", "ЫМ", "ИМ", "ОМ", "ЕМ", "УЮ", "ЮЮ", "ОГО", "ЕГО",
}
# «12 марта 2025 года» — в значение идёт только сама дата, как у даты отдельной строкой.
DATE_VALUE = re.compile(rf"({DATE.pattern})(?:\s*(?:г\.?|года))?", re.IGNORECASE)
# Фамилия с инициалами до или после.
INITIALS = r"[А-ЯЁ]\.\s?(?:[А-ЯЁ]\.)?"
SURNAME = r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?"
SIGNER_VALUE = re.compile(rf"(?:{INITIALS}\s*{SURNAME}|{SURNAME}\s+{INITIALS})\.?")
# Одно слово с заглавной буквы может быть чем угодно («Подпись Женская», «Подпись Петрович»),
# поэтому одна фамилия — подписант, только если тот же человек назван в черновике с инициалами.
BARE_SURNAME_VALUE = re.compile(rf"({SURNAME})\.?")
# Тема без разделителя — заголовок делового документа: «О закупке офисной техники».
# Предлог «О», «Об» или «Обо», за ним существительное в предложном падеже, дальше только
# строчные слова и числа, без запятых и знаков конца фразы. Слова с окончаниями личных форм
# глагола, инфинитива, возвратных форм и прошедшего времени во множественном числе, а также
# наречия времени и частицы означают фразу: «О закупке обсудим завтра», «Об отчёте придумаем позже».
HEADLINE_PREPOSITIONS = {"О", "Об", "Обо"}
HEADLINE_HEAD = re.compile(r"[а-яё]+(?:е|и|ах|ях)")
HEADLINE_WORD = re.compile(r"[а-яё]+(?:-[а-яё]+)*|\d+")
VERB_FORM = re.compile(r"(?:ем|им|ём|ут|ют|ят|ет|ит|ешь|ишь|[аиыяу]ли|с[яь]|[аяеиыуо]ть|чь)$")
NOT_HEADLINE_WORDS = {
    "не", "ни", "уже", "ещё", "еще", "вчера", "сегодня", "завтра", "позже", "потом", "пока",
    "сейчас", "скоро", "давно", "трижды", "дважды", "опять", "снова", "тоже", "также", "лишь",
    "только", "здесь", "там", "тут", "так", "как", "что", "чтобы", "если", "когда", "где",
    "куда", "это", "себе", "мне", "тебе",
}
MAX_HEADLINE_WORDS = 15
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
# Метки всех типов: ключевые слова уже записаны так, как их приводит normalize.
KNOWN_LABELS = {keyword for keywords in FIELD_KEYWORDS.values() for keyword in keywords}


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
    plain = [
        labelled_value(line, labels) or unseparated_value(line, fields) or usual_value(line, fields)
        for line in lines
    ]
    for index, found in enumerate(plain):
        found = found or value_in_context(lines, plain, index, fields)
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
    """«Дата 12.03.2025», «Номер 47-СЗ», «Подпись Петров П.П.»: значение строгой формы."""
    match = UNSEPARATED_LINE.match(line)
    if not match:
        return None
    field_id = UNSEPARATED_LABELS[normalize(match.group(1))]
    value = match.group(2)
    if field_id not in fields:
        return None
    if field_id == "number" and is_registration_number(value):
        return field_id, clean_value(value.removeprefix("№").lstrip())
    if field_id == "date" and (date := DATE_VALUE.fullmatch(value)):
        return field_id, clean_value(date.group(1))
    if field_id == "signer" and SIGNER_VALUE.fullmatch(value):
        return field_id, clean_value(value)
    return None


def value_in_context(
    lines: list[str], plain: list[tuple[str, str] | None], index: int, fields: set[str]
) -> tuple[str, str] | None:
    """Тема и одна фамилия без разделителя: форма значения не отличает их от фразы,
    поэтому нужна опора в самом черновике — шапка из реквизитов или тот же человек с инициалами.
    """
    match = UNSEPARATED_LINE.match(lines[index])
    if not match:
        return None
    field_id = UNSEPARATED_LABELS[normalize(match.group(1))]
    value = match.group(2)
    if field_id not in fields:
        return None
    if field_id == "subject" and is_headline(value) and in_header(lines, plain, index):
        return field_id, clean_value(value)
    if field_id == "signer" and (surname := BARE_SURNAME_VALUE.fullmatch(value)):
        if named_with_initials(lines, index, surname.group(1)):
            return field_id, clean_value(value)
    return None


def is_registration_number(value: str) -> bool:
    match = NUMBER_VALUE.fullmatch(value)
    if not match:
        return False
    parts = re.split(r"[-/]", match.group(1))
    return any(part.isdigit() for part in parts) and not any(
        part in ORDINAL_ENDINGS for part in parts
    )


def is_headline(value: str) -> bool:
    words = value.removesuffix(".").split()
    if not 2 <= len(words) <= MAX_HEADLINE_WORDS or words[0] not in HEADLINE_PREPOSITIONS:
        return False
    if not HEADLINE_HEAD.fullmatch(words[1]):
        return False
    return all(
        HEADLINE_WORD.fullmatch(word)
        and word not in NOT_HEADLINE_WORDS
        and not VERB_FORM.search(word)
        for word in words[1:]
    )


def in_header(lines: list[str], plain: list[tuple[str, str] | None], index: int) -> bool:
    """Строка стоит в шапке: выше только реквизиты, ниже пустая строка, реквизит или конец.

    Реквизитом шапки считается и известная метка чужого типа: «От кого:» в письме полем
    не станет, но и прозой не является.
    """
    def header_line(row: int) -> bool:
        return bool(plain[row]) or not lines[row].strip() or has_known_label(lines[row])

    above = all(header_line(row) for row in range(index))
    return above and (index + 1 == len(lines) or header_line(index + 1))


def has_known_label(line: str) -> bool:
    match = LABEL_LINE.match(line)
    return bool(match) and normalize(match.group(1)) in KNOWN_LABELS


def named_with_initials(lines: list[str], index: int, surname: str) -> bool:
    """«Подпись Петров.» и «От кого: Петров П.П.» выше — это один человек."""
    other = "\n".join(line for row, line in enumerate(lines) if row != index)
    word = re.escape(surname)
    return bool(re.search(
        rf"(?<![А-ЯЁа-яё-])(?:{word}\s+{INITIALS}|{INITIALS}\s*{word}(?![А-ЯЁа-яё-]))",
        other,
    ))


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
