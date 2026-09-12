"""Общие фикстуры проверок. Каталог типов и реквизитов берётся из самого сервиса,
чтобы тесты не расходились с конфигурацией при добавлении нового типа документа."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture(scope="session")
def client():
    """Сервис с заглушкой обработки: она переносит текст дословно и ничего не добавляет."""
    with TestClient(create_app(Settings(text_processor="stub"))) as ready:
        yield ready


@pytest.fixture(scope="session")
def unavailable_client():
    """Сервис, у которого обработчик текста отказывает, — имитация недоступности модели."""
    with TestClient(create_app(Settings(text_processor="unavailable"))) as ready:
        yield ready


@pytest.fixture(scope="session")
def catalog(client):
    return client.get("/api/catalog").json()


@pytest.fixture(scope="session")
def required_fields(catalog):
    return {
        doc_type["id"]: [field["id"] for field in doc_type["fields"] if field["required"]]
        for doc_type in catalog["doc_types"]
    }


@pytest.fixture(scope="session")
def field_labels(catalog):
    return {
        doc_type["id"]: {field["id"]: field["label"] for field in doc_type["fields"]}
        for doc_type in catalog["doc_types"]
    }


@pytest.fixture(scope="session")
def template_rules(catalog):
    return {template["id"]: template for template in catalog["templates"]}
