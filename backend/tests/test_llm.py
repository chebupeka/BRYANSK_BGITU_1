import json
import logging
import traceback

import httpx
import pytest
from pydantic import ValidationError

from app.catalog import document_types
from app.content_policy import ModelOutput, PolicyViolation, PreserveSourcePolicy
from app.llm import OpenAIProcessor
from app.processing import (
    ProcessorResult,
    ProcessorUnavailable,
    StubProcessor,
    get_processor,
    prepare_document,
)
from app.schemas import DocumentContent, ProcessRequest
from app.settings import Settings

SECRET = "test-secret-do-not-log"
PRIVATE_DRAFT = "Прошу отпуск с 15.09.2026.\n\n  С уважением, Иванов.  "


def settings(**overrides):
    return Settings(_env_file=None, **{
        "text_processor": "openai",
        "llm_base_url": "https://model.example/v1/",
        "llm_model": "test-model",
        "llm_api_key": SECRET,
        **overrides,
    })


def source():
    return ProcessRequest(
        doc_type="service_memo", draft=PRIVATE_DRAFT, requisites={"sender": "Иванов"}
    )


def output(**overrides):
    request = source()
    return {
        "requisites": request.requisites,
        "body": [line for line in request.draft.splitlines() if line.strip()],
        "changes": [],
        **overrides,
    }


def completion(value=None, *, finish_reason="stop", refusal=None):
    content = json.dumps(output() if value is None else value, ensure_ascii=False)
    return httpx.Response(200, json={"choices": [{
        "finish_reason": finish_reason,
        "message": {"content": content, "refusal": refusal},
    }]})


def test_endpoint_auth_payload_schema_and_phase_timeouts():
    seen = []

    def handler(request):
        seen.append(request)
        return completion()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        processor = get_processor(settings(), client=client)
        result = processor.process(source())
        processor.close()
        assert not client.is_closed  # Injected clients belong to the caller.
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://model.example/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {SECRET}"
    payload = json.loads(request.content)
    assert payload["model"] == "test-model"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 4096
    assert payload["stream"] is False
    assert SECRET not in request.content.decode()
    assert json.loads(payload["messages"][1]["content"]) == source().model_dump()
    assert '"additionalProperties": false' in payload["messages"][0]["content"]
    assert request.extensions["timeout"] == {
        "connect": 5, "read": 20, "write": 5, "pool": 5,
    }
    assert result.processor_mode == "openai"
    assert result.document.doc_type == source().doc_type
    assert result.document.body == output()["body"]
    assert result.changes == []
    assert "сохранения исходного текста" in result.warnings[0]


def test_local_keyless_provider_and_optional_response_format():
    def handler(request):
        assert "authorization" not in request.headers
        assert "response_format" not in json.loads(request.content)
        return completion()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        processor = OpenAIProcessor(
            settings(llm_api_key="", llm_response_format="none"), client=client
        )
        assert processor.process(source()).processor_mode == "openai"


@pytest.mark.parametrize("bad", [
    {"body": []},
    {"unexpected": "field"},
    {"body": ["Changed date to 16.09.2026"]},
    {"requisites": {"sender": "Петров"}},
    {"changes": ["Claim an edit that did not occur"]},
    {"body": ["Invalid XML\u0001"]},
    {"body": ["x" * 20000, "x"]},
])
def test_invalid_schema_or_policy_gets_one_retry_then_recovers(bad):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return completion(output(**bad)) if len(seen) == 1 else completion()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = OpenAIProcessor(settings(), client=client).process(source())
    assert len(seen) == 2
    assert len(seen[1]["messages"]) == 3
    assert all(message["role"] != "assistant" for message in seen[1]["messages"])
    assert result.document.body == output()["body"]


@pytest.mark.parametrize("retries,expected_calls", [(0, 1), (1, 2)])
def test_retry_exhaustion_is_bounded_and_hides_provider_text(retries, expected_calls, caplog):
    calls = []
    upstream = f"private upstream body {SECRET} {PRIVATE_DRAFT}"

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=upstream)

    caplog.set_level(logging.DEBUG)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProcessorUnavailable) as raised:
            OpenAIProcessor(settings(llm_max_retries=retries), client=client).process(source())
    error = raised.value
    assert (error.code, error.status, error.retryable) == ("llm_invalid_output", 502, False)
    assert len(calls) == expected_calls
    rendered = "".join(traceback.format_exception(error)) + caplog.text
    assert SECRET not in rendered
    assert PRIVATE_DRAFT not in rendered
    assert upstream not in rendered


@pytest.mark.parametrize("response", [
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, json={"choices": None}),
    httpx.Response(200, json={"choices": [{"message": {"content": []}}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": "```json\n{}\n```"}}]}),
    completion(finish_reason="length"),
    completion(finish_reason="content_filter"),
    completion(refusal="Model refused"),
])
def test_malformed_envelopes_refusal_and_truncation_rejected(response):
    with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
        with pytest.raises(ProcessorUnavailable, match="проверку") as raised:
            OpenAIProcessor(settings(llm_max_retries=0), client=client).process(source())
    assert raised.value.code == "llm_invalid_output"


@pytest.mark.parametrize("status,code,public_status,retryable", [
    (401, "llm_auth_error", 503, False),
    (403, "llm_auth_error", 503, False),
    (429, "llm_rate_limited", 503, True),
    (500, "llm_upstream_error", 502, True),
    (503, "llm_upstream_error", 502, True),
    (400, "llm_request_rejected", 502, False),
    (404, "llm_request_rejected", 502, False),
    (307, "llm_request_rejected", 502, False),
])
def test_http_failures_never_retried_or_redirected(status, code, public_status, retryable, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=f"{SECRET} {PRIVATE_DRAFT}", headers={
            "Location": "https://other.example/receive-secrets",
        })

    caplog.set_level(logging.DEBUG)
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        with pytest.raises(ProcessorUnavailable) as raised:
            OpenAIProcessor(settings(), client=client).process(source())
    error = raised.value
    assert (error.code, error.status, error.retryable) == (code, public_status, retryable)
    assert len(calls) == 1
    assert SECRET not in str(error) + caplog.text
    assert PRIVATE_DRAFT not in str(error) + caplog.text


@pytest.mark.parametrize("exception,code,status", [
    (httpx.ReadTimeout, "llm_timeout", 504),
    (httpx.ConnectTimeout, "llm_timeout", 504),
    (httpx.ConnectError, "llm_connection_error", 503),
    (httpx.RemoteProtocolError, "llm_connection_error", 503),
])
def test_transport_failures_are_safe_and_never_retried(exception, code, status):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception(f"{SECRET} {PRIVATE_DRAFT}", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProcessorUnavailable) as raised:
            OpenAIProcessor(settings(), client=client).process(source())
    assert (raised.value.code, raised.value.status) == (code, status)
    assert raised.value.retryable
    assert len(calls) == 1
    assert SECRET not in "".join(traceback.format_exception(raised.value))


def test_replacement_policy_controls_prompt_validation_and_application_warnings():
    class ExamplePolicy:
        def system_prompt(self):
            return "Return JSON. Preserve every fact; permit a final full stop."

        def validate(self, request, result):
            if result.body != [request.draft + "."] or result.requisites != request.requisites:
                raise PolicyViolation("Not the permitted edit")

        def warnings(self):
            return ["Example policy for one punctuation change only"]

    request = source().model_copy(update={"draft": "Прошу отпуск"})

    def handler(http_request):
        payload = json.loads(http_request.content)
        assert payload["messages"][0]["content"].startswith("Return JSON. Preserve every fact")
        return completion(output(body=["Прошу отпуск."], changes=["Добавлена точка"]))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = get_processor(settings(), content_policy=ExamplePolicy(), client=client).process(
            request
        )
    assert result.document.body == ["Прошу отпуск."]
    assert result.changes == ["Добавлена точка"]
    assert result.warnings == ExamplePolicy().warnings()


def test_policy_rejection_details_are_not_echoed_on_retry():
    class RejectingPolicy(PreserveSourcePolicy):
        def validate(self, request, result):
            raise PolicyViolation(SECRET)

    calls = []

    def handler(request):
        calls.append(request)
        assert SECRET not in request.content.decode()
        return completion()

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProcessorUnavailable):
            get_processor(settings(), content_policy=RejectingPolicy(), client=client).process(
                source()
            )
    assert len(calls) == 2


def test_missing_model_is_configuration_error_without_network_request():
    def handler(request):
        pytest.fail("Unconfigured processor must not make network requests")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProcessorUnavailable) as raised:
            get_processor(settings(llm_model=""), client=client).process(source())
    assert raised.value.code == "llm_not_configured"
    assert not raised.value.retryable


def test_own_client_closed_and_settings_secret_redacted():
    processor = OpenAIProcessor(settings())
    assert SECRET not in repr(processor.settings)
    assert SECRET not in processor.settings.model_dump_json()
    processor.close()
    assert processor._client.is_closed


@pytest.mark.parametrize("overrides", [
    {"llm_max_retries": 2}, {"llm_max_retries": -1},
    {"llm_timeout_seconds": 0}, {"llm_timeout_seconds": 61},
    {"llm_base_url": "file:///private"},
    {"llm_base_url": "https://username:password@example.com/v1"},
    {"llm_base_url": "https://example.com/v1?key=secret"},
    {"llm_base_url": "http://localhost:notaport/v1"},
    {"cors_origins": ["*"]}, {"cors_origins": ["https://example.com/path"]},
    {"cors_origins": ["http://localhost:bad"]},
])
def test_unsafe_or_unbounded_settings_rejected(overrides):
    with pytest.raises(ValidationError):
        settings(**overrides)


def test_settings_json_cors_env_and_cache_disabled(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://example.com", "http://localhost:5173"]')
    config = settings(cache_max_entries=0, cache_ttl_seconds=0)
    assert config.cors_origins == ["https://example.com", "http://localhost:5173"]
    assert config.cache_max_entries == config.cache_ttl_seconds == 0


def test_model_contract_forbids_provider_control_of_document_type_and_warnings():
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(output(doc_type="other"))
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(output(warnings=["Trust me"]))


@pytest.mark.parametrize("invalid_document", [
    DocumentContent(doc_type="other", requisites={}, body=["Text"]),
    DocumentContent(doc_type="service_memo", requisites={"not_a_catalog_key": "x"}, body=["Text"]),
])
def test_processor_boundary_rejects_wrong_document_type_or_requisite_keys(invalid_document):
    class BrokenProcessor:
        def process(self, request):
            return ProcessorResult(invalid_document, [], [], "custom")

    with pytest.raises(ProcessorUnavailable) as raised:
        prepare_document(source(), document_types()["service_memo"], BrokenProcessor())
    assert (raised.value.code, raised.value.status, raised.value.retryable) == (
        "processor_invalid_output", 502, False,
    )


def test_stub_and_unavailable_still_work_through_public_factory():
    stub = get_processor("stub")
    assert isinstance(stub, StubProcessor)
    assert stub.process(source()).document.body == output()["body"]
    stub.close()
    unavailable = get_processor("unavailable")
    with pytest.raises(ProcessorUnavailable) as raised:
        unavailable.process(source())
    assert raised.value.code == "processor_unavailable"
    unavailable.close()
