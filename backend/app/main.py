from contextlib import asynccontextmanager
from threading import BoundedSemaphore

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.cache import ProcessCache, processing_key
from app.catalog import document_types, templates, validate_requisite_keys
from app.content_policy import ContentPolicy
from app.docx_generator import generate_docx
from app.errors import APIError, RequestContextMiddleware, install_error_handlers
from app.extraction import suggest_requisites
from app.ports import DocumentRenderer
from app.processing import TextProcessor, get_processor, prepare_document
from app.schemas import (
    Catalog,
    DownloadRequest,
    ErrorResponse,
    HealthResponse,
    ProcessRequest,
    ProcessResponse,
    ReadyResponse,
    RequisiteSuggestions,
    SuggestRequest,
)
from app.settings import Settings

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ERROR_RESPONSES = {
    422: {"model": ErrorResponse, "description": "Invalid input or catalog selection"},
    500: {"model": ErrorResponse, "description": "Internal processing error"},
    502: {"model": ErrorResponse, "description": "LLM returned unusable content"},
    503: {"model": ErrorResponse, "description": "Processing unavailable or busy"},
    504: {"model": ErrorResponse, "description": "LLM timed out"},
}


def create_app(
    settings: Settings | None = None,
    *,
    processor: TextProcessor | None = None,
    content_policy: ContentPolicy | None = None,
    renderer: DocumentRenderer | None = None,
) -> FastAPI:
    """Teams replace a policy, whole processor or DOCX callable at this composition root."""
    if processor is not None and content_policy is not None:
        raise ValueError("Pass processor or content_policy, not both")
    settings = settings or Settings()
    owns_processor = processor is None
    processor = processor or get_processor(settings, content_policy=content_policy)
    renderer = renderer or generate_docx
    cache = ProcessCache(settings.cache_max_entries, settings.cache_ttl_seconds)
    slots = BoundedSemaphore(settings.max_concurrent_processes)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        document_types()
        templates()
        try:
            yield
        finally:
            cache.clear()
            if owns_processor:
                processor.close()

    app = FastAPI(
        title="Документ за 3 шага",
        version="0.2.0",
        lifespan=lifespan,
        description="Backend команды: подготовка содержания и независимый экспорт DOCX.",
    )
    app.state.processor = processor
    app.state.process_cache = cache
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["Content-Disposition", "X-Request-ID", "X-Cache", "Retry-After"],
    )
    install_error_handlers(app)

    @app.get(
        "/api/health", response_model=HealthResponse, operation_id="getHealth", tags=["system"]
    )
    def health():
        """Liveness only: does not call the model or claim it is available."""
        return HealthResponse(processor_mode=settings.text_processor)

    @app.get(
        "/api/ready",
        response_model=ReadyResponse,
        operation_id="getReadiness",
        tags=["system"],
        responses={503: ERROR_RESPONSES[503]},
    )
    def ready():
        """Local configuration readiness. No request to the upstream model."""
        document_types()
        templates()
        if owns_processor and settings.text_processor == "unavailable":
            raise APIError(
                503, "processor_unavailable", "Обработка временно недоступна.", retryable=True
            )
        needs_model = settings.text_processor in {"openai", "llm"}
        if owns_processor and needs_model and not settings.llm_model:
            raise APIError(503, "llm_not_configured", "Укажите LLM_MODEL в настройках backend.")
        return ReadyResponse(
            processor_mode=settings.text_processor, checks={"catalog": True, "processor": True}
        )

    @app.get("/api/catalog", response_model=Catalog, operation_id="getCatalog", tags=["documents"])
    def catalog():
        return Catalog(
            doc_types=list(document_types().values()),
            templates=list(templates().values()),
            processor_mode=settings.text_processor,
        )

    def selected_type(type_id: str, requisites: dict[str, str]):
        doc_type = document_types().get(type_id)
        if doc_type is None:
            raise APIError(422, "unknown_doc_type", "Неизвестный тип документа.")
        try:
            validate_requisite_keys(doc_type, requisites)
        except ValueError as error:
            raise APIError(
                422,
                "unknown_requisites",
                "Переданы реквизиты, которых нет у выбранного типа документа.",
            ) from error
        return doc_type

    @app.post(
        "/api/requisites/suggest",
        response_model=RequisiteSuggestions,
        operation_id="suggestRequisites",
        tags=["documents"],
        responses=ERROR_RESPONSES,
    )
    def suggest(request: SuggestRequest):
        """A form hint, not processing: no model is involved and its failures cannot reach it."""
        doc_type = selected_type(request.doc_type, {})
        return RequisiteSuggestions(requisites=suggest_requisites(request.draft, doc_type))

    @app.post(
        "/api/process",
        response_model=ProcessResponse,
        operation_id="processDocument",
        tags=["documents"],
        responses=ERROR_RESPONSES,
    )
    def process(request: ProcessRequest, response: Response):
        """Prepare content once; template selection is intentionally absent from this request."""
        doc_type = selected_type(request.doc_type, request.requisites)
        key = processing_key(request)
        cached = cache.get(key)
        if cached is not None:
            response.headers["X-Cache"] = "HIT"
            return cached
        if not slots.acquire(blocking=False):
            raise APIError(
                503,
                "processor_busy",
                "Сервис занят обработкой документов. Повторите попытку немного позже.",
                retryable=True,
            )
        try:
            cached = cache.get(key)
            if cached is not None:
                response.headers["X-Cache"] = "HIT"
                return cached
            result = prepare_document(request, doc_type, processor)
            cache.put(key, result)
            response.headers["X-Cache"] = "MISS" if cache.enabled else "BYPASS"
            return result
        finally:
            slots.release()

    @app.post(
        "/api/documents/download",
        operation_id="downloadDocument",
        tags=["documents"],
        response_class=Response,
        responses={
            200: {
                "description": "Editable DOCX",
                "content": {
                    DOCX_MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}},
                },
            },
            422: ERROR_RESPONSES[422],
            500: ERROR_RESPONSES[500],
        },
    )
    def download(request: DownloadRequest):
        """Render user-supplied content without calling the model or claiming fact verification."""
        doc_type = selected_type(request.document.doc_type, request.document.requisites)
        template = request.custom_template or templates().get(request.template_id)
        if template is None:
            raise APIError(422, "unknown_template", "Неизвестный шаблон оформления.")
        if template.id != request.template_id:
            raise APIError(
                422,
                "unknown_template",
                "Идентификатор пользовательского оформления не совпадает с выбранным.",
            )
        content = renderer(request.document, doc_type, template)
        filename = f"{doc_type.id}-{template.id}.docx"
        return Response(
            content=content,
            media_type=DOCX_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    return app


app = create_app()
