"""Small integration boundaries owned by the backend lead."""

from typing import Protocol

from app.schemas import DocumentContent, DocumentType, Template


class DocumentRenderer(Protocol):
    def __call__(
        self, content: DocumentContent, doc_type: DocumentType, template: Template
    ) -> bytes: ...
