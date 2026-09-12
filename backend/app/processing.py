from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.catalog import validate_requisite_keys
from app.schemas import DocumentContent, DocumentType, ProcessRequest, ProcessResponse
from app.settings import Settings

if TYPE_CHECKING:
    import httpx

    from app.content_policy import ContentPolicy


class ProcessorUnavailable(Exception):
    """A public, safe error. Never put provider response text or keys in its message."""

    def __init__(
        self,
        message: str = "Обработка временно недоступна. Черновик сохранён в форме.",
        *,
        code: str = "processor_unavailable",
        status: int = 503,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True)
class ProcessorResult:
    document: DocumentContent
    changes: list[str]
    warnings: list[str]
    processor_mode: str


class TextProcessor(Protocol):
    def process(self, request: ProcessRequest) -> ProcessorResult: ...

    def close(self) -> None: ...


class StubProcessor:
    def process(self, request: ProcessRequest) -> ProcessorResult:
        # No rewriting or fact extraction: every nonempty source line stays verbatim.
        return ProcessorResult(
            document=DocumentContent(
                doc_type=request.doc_type,
                requisites=request.requisites,
                body=[line for line in request.draft.splitlines() if line.strip()],
            ),
            changes=[],
            warnings=[
                "Демонстрационный режим: текст перенесён без исправлений. "
                "Проверка орфографии и делового стиля пока не подключена."
            ],
            processor_mode="stub",
        )

    def close(self) -> None:
        pass


class UnavailableProcessor:
    def process(self, request: ProcessRequest) -> ProcessorResult:
        raise ProcessorUnavailable()

    def close(self) -> None:
        pass


def get_processor(
    config: Settings | str,
    *,
    content_policy: "ContentPolicy | None" = None,
    client: "httpx.Client | None" = None,
) -> TextProcessor:
    settings = Settings(text_processor=config) if isinstance(config, str) else config
    if settings.text_processor == "stub":
        return StubProcessor()
    if settings.text_processor == "unavailable":
        return UnavailableProcessor()
    from app.llm import OpenAIProcessor

    return OpenAIProcessor(settings, content_policy=content_policy, client=client)


def prepare_document(
    request: ProcessRequest, doc_type: DocumentType, processor: TextProcessor
) -> ProcessResponse:
    result = processor.process(request)
    try:
        if result.document.doc_type != request.doc_type:
            raise ValueError("Processor changed document type")
        validate_requisite_keys(doc_type, result.document.requisites)
    except ValueError:
        raise ProcessorUnavailable(
            "Модуль обработки вернул несовместимый документ.",
            code="processor_invalid_output", status=502, retryable=False,
        ) from None
    missing = [
        field
        for field in doc_type.fields
        if field.required and not result.document.requisites.get(field.id, "").strip()
    ]
    return ProcessResponse(
        document=result.document,
        missing_fields=missing,
        changes=result.changes,
        warnings=result.warnings,
        processor_mode=result.processor_mode,
    )
