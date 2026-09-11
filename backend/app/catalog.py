from functools import lru_cache
from pathlib import Path

import yaml

from app.schemas import DocumentType, Template

BASE = Path(__file__).resolve().parent


@lru_cache
def document_types() -> dict[str, DocumentType]:
    result = {}
    for path in sorted((BASE / "doc_types").glob("*.yaml")):
        item = DocumentType.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        field_ids = [field.id for field in item.fields]
        if item.id in result or len(field_ids) != len(set(field_ids)):
            raise ValueError(f"Duplicate id in {path.name}")
        if set(item.blocks) != {*field_ids, "title", "body"}:
            raise ValueError(f"Each field, title and body must have a block in {path.name}")
        if len(item.blocks) != len(set(item.blocks)):
            raise ValueError(f"Duplicate block in {path.name}")
        result[item.id] = item
    if not result:
        raise ValueError("No document types configured")
    return result


@lru_cache
def templates() -> dict[str, Template]:
    result = {}
    for path in sorted((BASE / "templates").glob("*.yaml")):
        item = Template.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if item.id in result:
            raise ValueError(f"Duplicate template id in {path.name}")
        if set(item.margins_mm) != {"top", "right", "bottom", "left"}:
            raise ValueError(f"Four margins required in {path.name}")
        if any(not 10 <= margin <= 40 for margin in item.margins_mm.values()):
            raise ValueError(f"Margins must be 10–40 mm in {path.name}")
        result[item.id] = item
    if not result:
        raise ValueError("No templates configured")
    return result


def validate_requisite_keys(doc_type: DocumentType, requisites: dict[str, str]) -> None:
    unknown = set(requisites) - {field.id for field in doc_type.fields}
    if unknown:
        raise ValueError(f"Неизвестные реквизиты: {', '.join(sorted(unknown))}")
