"""Synchronous OpenAI-compatible transport with a replaceable content policy."""

import json

import httpx
from pydantic import ValidationError

from app.content_policy import ContentPolicy, ModelOutput, PolicyViolation, PreserveSourcePolicy
from app.processing import ProcessorResult, ProcessorUnavailable
from app.schemas import DocumentContent, ProcessRequest
from app.settings import Settings


class InvalidModelResponse(Exception):
    pass


class OpenAIProcessor:
    def __init__(
        self,
        settings: Settings,
        *,
        content_policy: ContentPolicy | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._timeout = httpx.Timeout(
            settings.llm_timeout_seconds,
            connect=min(5, settings.llm_timeout_seconds),
            write=min(5, settings.llm_timeout_seconds),
            pool=min(5, settings.llm_timeout_seconds),
        )
        self.policy = content_policy if content_policy is not None else PreserveSourcePolicy()
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(
            timeout=self._timeout,
            follow_redirects=False,
            transport=httpx.HTTPTransport(retries=0),
        )

    def close(self) -> None:
        """The application owns this processor; an injected client belongs to its caller."""
        if self._owns_client:
            self._client.close()

    def _request(self, messages: list[dict[str, str]]) -> ModelOutput:
        headers = {"Content-Type": "application/json"}
        key = self.settings.llm_api_key.get_secret_value()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "max_tokens": self.settings.llm_max_tokens,
            "stream": False,
        }
        if self.settings.llm_response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        try:
            response = self._client.post(
                f"{self.settings.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self._timeout,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            raise ProcessorUnavailable(
                "Модель не ответила вовремя. Попробуйте ещё раз.",
                code="llm_timeout", status=504,
            ) from None
        except httpx.RequestError:
            raise ProcessorUnavailable(
                "Не удалось связаться с моделью. Попробуйте ещё раз.",
                code="llm_connection_error", status=503,
            ) from None
        if response.status_code in {401, 403}:
            raise ProcessorUnavailable(
                "Проверьте настройки доступа к модели.",
                code="llm_auth_error", status=503, retryable=False,
            )
        if response.status_code == 429:
            raise ProcessorUnavailable(
                "Модель временно перегружена. Попробуйте позже.",
                code="llm_rate_limited", status=503,
            )
        if response.status_code >= 500:
            raise ProcessorUnavailable(
                "Сервис модели временно недоступен.",
                code="llm_upstream_error", status=502,
            )
        if not 200 <= response.status_code < 300:
            raise ProcessorUnavailable(
                "Сервис модели отклонил запрос. Проверьте настройки модели.",
                code="llm_request_rejected", status=502, retryable=False,
            )
        try:
            envelope = response.json()
            choice = envelope["choices"][0]
            message = choice["message"]
            if message.get("refusal") or choice.get("finish_reason") not in {"stop", None}:
                raise InvalidModelResponse()
            content = message["content"]
            if not isinstance(content, str):
                raise InvalidModelResponse()
            return ModelOutput.model_validate_json(content)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise InvalidModelResponse() from None

    def process(self, request: ProcessRequest) -> ProcessorResult:
        if not self.settings.llm_model:
            raise ProcessorUnavailable(
                "Укажите LLM_MODEL для подключения модели.",
                code="llm_not_configured", status=503, retryable=False,
            )
        schema = json.dumps(ModelOutput.model_json_schema(), ensure_ascii=False)
        messages = [
            {
                "role": "system",
                "content": self.policy.system_prompt()
                + "\nReturn only JSON matching this schema, without markdown:\n" + schema,
            },
            {"role": "user", "content": request.model_dump_json()},
        ]
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                result = self._request(messages)
                self.policy.validate(request, result)
            except (InvalidModelResponse, ValidationError, PolicyViolation):
                if attempt < self.settings.llm_max_retries:
                    # Never echo an invalid provider response or private validation details.
                    messages = messages + [{
                        "role": "user",
                        "content": (
                            "The previous output failed JSON validation or the content policy. "
                            "Try once more. Follow the system rules and preserve source facts. "
                            "Return only the required JSON object."
                        ),
                    }]
                    continue
                raise ProcessorUnavailable(
                    "Ответ модели не прошёл проверку. Исходный текст сохранён в форме.",
                    code="llm_invalid_output", status=502, retryable=False,
                ) from None
            return ProcessorResult(
                document=DocumentContent(
                    doc_type=request.doc_type,
                    requisites=result.requisites,
                    body=result.body,
                ),
                changes=result.changes,
                warnings=self.policy.warnings(),
                processor_mode="openai",
            )
        raise AssertionError("Unreachable retry limit")
