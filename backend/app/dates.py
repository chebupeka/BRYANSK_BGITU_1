"""Записи дат, общие для сверки фактов и разбора черновика.

«25.09.2026», «2026-09-25» и «25 сентября 2026» — одна дата, поэтому образцы держим
в одном месте: иначе проверка и подстановка начнут понимать текст по-разному.
"""

import re

MONTHS = "январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр"
DATE = re.compile(
    rf"\d{{4}}[-./]\d{{1,2}}[-./]\d{{1,2}}"
    rf"|\d{{1,2}}[-./]\d{{1,2}}[-./]\d{{2,4}}"
    rf"|\d{{1,2}}\s+(?:{MONTHS})\w*(?:\s+\d{{4}})?",
    re.IGNORECASE,
)
MONTH_PREFIXES = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "ма": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}


def canonical_date(text: str) -> str:
    """Единый вид для сравнения: день, месяц и год через точку."""
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
