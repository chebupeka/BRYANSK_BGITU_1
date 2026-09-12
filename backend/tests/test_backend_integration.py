"""Backend integration contracts, cache behavior and failure isolation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cache import ProcessCache, processing_key
from app.catalog import document_types
from app.llm import OpenAIProcessor
from app.main import DOCX_MEDIA_TYPE, create_app
from app.processing import ProcessorUnavailable, StubProcessor, prepare_document
from app.schemas import ErrorResponse, ProcessRequest
from app.settings import Settings

PAYLOAD = {"doc_type": "service_memo", "draft": "Поставка до 25.09.2026 при согласовании."}


def settings(**values):
    return Settings(_env_file=None, text_processor="stub", **values)


class CountingProcessor(StubProcessor):
    def __init__(self):
        self.calls = 0

    def process(self, request):
        self.calls += 1
        return super().process(request)


def test_cache_uses_content_not_requisite_order_and_download_never_processes():
    processor = CountingProcessor()
    with TestClient(create_app(settings(), processor=processor)) as client:
        payload = PAYLOAD | {"requisites": {"subject": "Тема", "recipient": "Директору"}}
        first = client.post("/api/process", json=payload)
        second = client.post(
            "/api/process",
            json=payload
            | {
                "requisites": {"recipient": "Директору", "subject": "Тема"},
            },
        )
        assert first.headers["x-cache"] == "MISS"
        assert second.headers["x-cache"] == "HIT"
        assert first.json() == second.json()
        for template_id in ("classic", "modern"):
            response = client.post(
                "/api/documents/download",
                json={
                    "document": first.json()["document"],
                    "template_id": template_id,
                },
            )
            assert response.status_code == 200
        assert processor.calls == 1
        for update in (
            {"draft": "Другой черновик"},
            {"doc_type": "report_memo"},
            {"requisites": {"subject": "Другая тема"}},
        ):
            response = client.post("/api/process", json=payload | update)
            assert response.status_code == 200
            assert response.headers["x-cache"] == "MISS"
        assert processor.calls == 4


def test_cache_expiry_lru_and_copies():
    now = [10.0]
    cache = ProcessCache(2, 5, clock=lambda: now[0])
    request = ProcessRequest(**PAYLOAD)
    result = prepare_document(request, document_types()[request.doc_type], StubProcessor())
    cache.put("a", result)
    result.document.body[0] = "caller mutation"
    assert cache.get("a").document.body == [PAYLOAD["draft"]]
    cache.put("b", result)
    cached = cache.get("a")
    cached.document.body[0] = "another mutation"
    cache.put("c", result)
    assert cache.get("b") is None
    assert cache.get("a").document.body == [PAYLOAD["draft"]]
    now[0] = 15.0
    assert cache.get("a") is None
    assert cache.get("c") is None


def test_cache_distinguishes_missing_and_explicitly_cleared_requisite():
    processor = CountingProcessor()
    with TestClient(create_app(settings(), processor=processor)) as client:
        first = client.post("/api/process", json=PAYLOAD)
        cleared = client.post("/api/process", json=PAYLOAD | {"requisites": {"subject": ""}})
        assert first.json()["document"]["requisites"] == {}
        assert cleared.json()["document"]["requisites"] == {"subject": ""}
        assert cleared.headers["x-cache"] == "MISS"
        assert processor.calls == 2


@pytest.mark.parametrize("option", [{"cache_max_entries": 0}, {"cache_ttl_seconds": 0}])
def test_cache_can_be_disabled(option):
    processor = CountingProcessor()
    with TestClient(create_app(settings(**option), processor=processor)) as client:
        for _ in range(2):
            response = client.post("/api/process", json=PAYLOAD)
            assert response.status_code == 200
            assert response.headers["x-cache"] == "BYPASS"
    assert processor.calls == 2


def test_cache_cleared_at_shutdown_and_is_not_shared_between_apps():
    processor = CountingProcessor()
    application = create_app(settings(), processor=processor)
    with TestClient(application) as client:
        client.post("/api/process", json=PAYLOAD)
    assert application.state.process_cache.get(processing_key(ProcessRequest(**PAYLOAD))) is None
    with TestClient(create_app(settings(), processor=processor)) as client:
        assert client.post("/api/process", json=PAYLOAD).headers["x-cache"] == "MISS"
    assert processor.calls == 2


def test_failed_request_is_not_cached_and_slot_is_released():
    class FailsOnce(CountingProcessor):
        def process(self, request):
            if self.calls == 0:
                self.calls += 1
                raise ProcessorUnavailable()
            return super().process(request)

    processor = FailsOnce()
    with TestClient(
        create_app(settings(max_concurrent_processes=1), processor=processor)
    ) as client:
        failed = client.post("/api/process", json=PAYLOAD)
        assert failed.status_code == 503
        assert "x-cache" not in failed.headers
        assert client.post("/api/process", json=PAYLOAD).status_code == 200
    assert processor.calls == 2


def test_busy_requests_fail_fast_but_health_and_download_stay_available():
    entered, release = Event(), Event()

    class BlockingProcessor(StubProcessor):
        def process(self, request):
            entered.set()
            assert release.wait(timeout=5)
            return super().process(request)

    application = create_app(settings(max_concurrent_processes=1), processor=BlockingProcessor())
    with TestClient(application) as client, ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, "/api/process", json=PAYLOAD)
        try:
            assert entered.wait(timeout=3)
            busy = client.post("/api/process", json=PAYLOAD | {"draft": "Другой текст"})
            assert busy.status_code == 503
            assert busy.json()["error"]["code"] == "processor_busy"
            assert busy.headers["retry-after"] == "1"
            assert client.get("/api/health").status_code == 200
            document = StubProcessor().process(ProcessRequest(**PAYLOAD)).document
            assert (
                client.post(
                    "/api/documents/download",
                    json={
                        "document": document.model_dump(),
                        "template_id": "classic",
                    },
                ).status_code
                == 200
            )
        finally:
            release.set()
        assert future.result(timeout=3).status_code == 200


@pytest.mark.parametrize(
    "payload,code",
    [
        (PAYLOAD | {"draft": ""}, "validation_error"),
        (PAYLOAD | {"secret_unknown_property": "private text"}, "validation_error"),
        (PAYLOAD | {"doc_type": "unknown"}, "unknown_doc_type"),
        (PAYLOAD | {"requisites": {"invented": "private text"}}, "unknown_requisites"),
    ],
)
def test_error_envelope_request_id_and_no_input_echo(payload, code):
    with TestClient(create_app(settings())) as client:
        response = client.post(
            "/api/process", json=payload, headers={"X-Request-ID": "qa-request.1"}
        )
        assert response.status_code == 422
        error = ErrorResponse.model_validate(response.json())
        assert error.detail == error.error.message
        assert error.error.code == code
        assert error.error.request_id == response.headers["x-request-id"] == "qa-request.1"
        assert not error.error.retryable
        assert "private text" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_request_id_is_sanitized_and_http_errors_use_the_same_envelope():
    with TestClient(create_app(settings())) as client:
        for path, method in (("/api/missing", "get"), ("/api/health", "post")):
            response = getattr(client, method)(path, headers={"X-Request-ID": "bad id"})
            error = ErrorResponse.model_validate(response.json())
            assert error.error.code == "http_error"
            assert len(error.error.request_id) == 32
            assert response.headers["x-request-id"] == error.error.request_id


def test_unexpected_failure_hides_private_exception_and_keeps_cors(caplog):
    class BrokenProcessor(StubProcessor):
        def process(self, request):
            raise RuntimeError("private-draft-and-key")

    with TestClient(create_app(settings(), processor=BrokenProcessor())) as client:
        response = client.post(
            "/api/process",
            json=PAYLOAD,
            headers={
                "Origin": "http://localhost:5173",
            },
        )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
        assert "private-draft-and-key" not in response.text + caplog.text


def test_cors_allows_only_configured_origins_and_exposes_download_headers():
    with TestClient(create_app(settings())) as client:
        response = client.options(
            "/api/process",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-Request-ID",
            },
        )
        assert response.status_code == 200
        denied = client.options(
            "/api/process",
            headers={
                "Origin": "https://unknown.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in denied.headers
        response = client.get("/api/catalog", headers={"Origin": "http://localhost:5173"})
        assert "Content-Disposition" in response.headers["access-control-expose-headers"]


def test_readiness_distinguishes_config_from_liveness():
    for mode, expected in (("stub", 200), ("unavailable", 503), ("openai", 503)):
        config = Settings(_env_file=None, text_processor=mode, llm_model="")
        with TestClient(create_app(config)) as client:
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/ready").status_code == expected
    # A deliberately unreachable URL still passes configuration readiness; no network call.
    config = Settings(
        _env_file=None,
        text_processor="openai",
        llm_model="mock-model",
        llm_base_url="http://127.0.0.1:1/v1",
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/api/ready").status_code == 200


def test_renderer_injection_receives_typed_catalog_objects():
    calls = []

    def renderer(content, doc_type, template):
        calls.append((content.doc_type, doc_type.id, template.id))
        return b"test-document"

    with TestClient(create_app(settings(), renderer=renderer)) as client:
        response = client.post(
            "/api/documents/download",
            json={
                "document": {"doc_type": "service_memo", "body": ["Text"]},
                "template_id": "modern",
            },
        )
        assert response.content == b"test-document"
        assert response.headers["content-type"] == DOCX_MEDIA_TYPE
        assert calls == [("service_memo", "service_memo", "modern")]


def test_real_transport_to_http_api_error_and_cached_success():
    calls = []

    def upstream(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("private-provider-detail")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"requisites":{},"body":["Text"],"changes":[]}'},
                    }
                ]
            },
        )

    config = Settings(_env_file=None, text_processor="openai", llm_model="test-model")
    with httpx.Client(transport=httpx.MockTransport(upstream)) as upstream_client:
        processor = OpenAIProcessor(config, client=upstream_client)
        with TestClient(create_app(config, processor=processor)) as client:
            payload = PAYLOAD | {"draft": "Text"}
            failed = client.post("/api/process", json=payload)
            assert failed.status_code == 504
            assert failed.json()["error"]["code"] == "llm_timeout"
            assert "private-provider-detail" not in failed.text
            success = client.post("/api/process", json=payload)
            assert success.status_code == 200
            assert success.json()["processor_mode"] == "openai"
            assert client.post("/api/process", json=payload).headers["x-cache"] == "HIT"
    assert len(calls) == 2


def test_openapi_has_error_models_and_binary_download():
    schema = create_app(settings()).openapi()
    responses = schema["paths"]["/api/process"]["post"]["responses"]
    for status in ("422", "500", "502", "503", "504"):
        assert responses[status]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ErrorResponse"
        )
    download = schema["paths"]["/api/documents/download"]["post"]["responses"]["200"]
    assert download["content"][DOCX_MEDIA_TYPE]["schema"]["format"] == "binary"
    assert "application/json" not in download["content"]
