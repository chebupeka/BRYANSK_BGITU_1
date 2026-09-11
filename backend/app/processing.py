from typing import Protocol

from app.schemas import DocumentContent, DocumentType, ProcessRequest, ProcessResponse


class ProcessorUnavailable(Exception):
    pass


class TextProcessor(Protocol):
    """Replace this boundary with a schema-validated, fact-checked LLM adapter."""

    def process(self, request: ProcessRequest) -> DocumentContent: ...


class StubProcessor:
    def process(self, request: ProcessRequest) -> DocumentContent:
        # No rewriting or fact extraction: every nonempty source line stays verbatim.
        return DocumentContent(
            doc_type=request.doc_type,
            requisites=request.requisites,
            body=[line for line in request.draft.splitlines() if line.strip()],
        )


class UnavailableProcessor:
    def process(self, request: ProcessRequest) -> DocumentContent:
        raise ProcessorUnavailable("Обработка временно недоступна. Черновик сохранён в форме.")


def get_processor(mode: str) -> TextProcessor:
    if mode == "stub":
        return StubProcessor()
    if mode == "unavailable":
        return UnavailableProcessor()
    raise ValueError(f"Unsupported text processor: {mode}")


def prepare_document(
    request: ProcessRequest, doc_type: DocumentType, processor: TextProcessor
) -> ProcessResponse:
    document = processor.process(request)
    missing = [field for field in doc_type.fields if field.required
               and not document.requisites.get(field.id, "").strip()]
    return ProcessResponse(
        document=document,
        missing_fields=missing,
        changes=[],
        warnings=[
            "Демонстрационный режим: текст перенесён без исправлений. "
            "Проверка орфографии и делового стиля пока не подключена."
        ],
        processor_mode="stub",
    )
