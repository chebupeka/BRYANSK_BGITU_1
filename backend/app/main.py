from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from app.catalog import document_types, templates, validate_requisite_keys
from app.docx_generator import generate_docx
from app.extraction import suggest_requisites
from app.processing import (
    ProcessorUnavailable,
    TextProcessor,
    get_processor,
    prepare_document,
)
from app.schemas import (
    Catalog,
    DownloadRequest,
    ProcessRequest,
    ProcessResponse,
    RequisiteSuggestions,
    SuggestRequest,
)
from app.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    document_types()
    templates()
    yield


def create_app(
    settings: Settings | None = None, processor: TextProcessor | None = None
) -> FastAPI:
    settings = settings or Settings()
    processor = processor or get_processor(
        settings.text_processor,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_api_key=settings.llm_api_key,
        llm_timeout_seconds=settings.llm_timeout_seconds,
    )
    app = FastAPI(title="Документ за 3 шага", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "processor_mode": settings.text_processor}

    @app.get("/api/catalog", response_model=Catalog)
    def catalog():
        return Catalog(
            doc_types=list(document_types().values()),
            templates=list(templates().values()),
            processor_mode=settings.text_processor,
        )

    def selected_type(type_id: str, requisites: dict[str, str]):
        doc_type = document_types().get(type_id)
        if doc_type is None:
            raise HTTPException(422, "Неизвестный тип документа")
        try:
            validate_requisite_keys(doc_type, requisites)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return doc_type

    @app.post("/api/requisites/suggest", response_model=RequisiteSuggestions)
    def suggest(request: SuggestRequest):
        # Подсказка формы, а не обработка: модель здесь не участвует и ошибки её не влияют.
        doc_type = selected_type(request.doc_type, {})
        return RequisiteSuggestions(requisites=suggest_requisites(request.draft, doc_type))

    @app.post("/api/process", response_model=ProcessResponse)
    def process(request: ProcessRequest):
        doc_type = selected_type(request.doc_type, request.requisites)
        try:
            return prepare_document(request, doc_type, processor)
        except ProcessorUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @app.post("/api/documents/download")
    def download(request: DownloadRequest):
        doc_type = selected_type(request.document.doc_type, request.document.requisites)
        template = templates().get(request.template_id)
        if template is None:
            raise HTTPException(422, "Неизвестный шаблон оформления")
        content = generate_docx(request.document, doc_type, template)
        filename = f"{doc_type.id}-{template.id}.docx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


app = create_app()
