"""Public errors omit raw input, upstream responses and unexpected exception text."""

import logging
import re
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.processing import ProcessorUnavailable
from app.schemas import ErrorInfo, ErrorIssue, ErrorResponse

logger = logging.getLogger("app.requests")


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, *, retryable: bool = False):
        self.status, self.code, self.message, self.retryable = status, code, message, retryable


def error_response(
    request_id: str,
    status: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    details: list[ErrorIssue] | None = None,
) -> JSONResponse:
    content = ErrorResponse(
        detail=message,
        error=ErrorInfo(
            code=code,
            message=message,
            retryable=retryable,
            request_id=request_id,
            details=details or [],
        ),
    )
    headers = {"X-Request-ID": request_id, "Cache-Control": "no-store"}
    if code == "processor_busy":
        headers["Retry-After"] = "1"
    return JSONResponse(content.model_dump(), status_code=status, headers=headers)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"x-request-id", b"").decode("ascii", errors="replace")
        request_id = supplied if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", supplied) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        status, started = 500, False
        began = monotonic()

        async def with_headers(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                status, started = message["status"], True
                updated = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"x-request-id", b"cache-control"}
                ]
                message["headers"] = updated + [
                    (b"x-request-id", request_id.encode()),
                    (b"cache-control", b"no-store"),
                ]
            await send(message)

        try:
            await self.app(scope, receive, with_headers)
        except Exception as error:
            # Exception messages may contain documents or keys, so log only the class.
            logger.error("request_failed request_id=%s kind=%s", request_id, type(error).__name__)
            if started:
                raise
            response = error_response(
                request_id,
                500,
                "internal_error",
                "Не удалось завершить запрос. Введённые данные остаются в форме.",
            )
            await response(scope, receive, with_headers)
        finally:
            route = scope.get("route")
            # Never log query strings, arbitrary paths, headers or request bodies.
            logger.info(
                "request request_id=%s method=%s route=%s status=%s duration_ms=%.1f",
                request_id,
                scope["method"],
                getattr(route, "path", "unmatched"),
                status,
                (monotonic() - began) * 1000,
            )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error(request: Request, error: APIError):
        return error_response(
            request.state.request_id,
            error.status,
            error.code,
            error.message,
            retryable=error.retryable,
        )

    @app.exception_handler(ProcessorUnavailable)
    async def processor_error(request: Request, error: ProcessorUnavailable):
        return error_response(
            request.state.request_id,
            error.status,
            error.code,
            str(error),
            retryable=error.retryable,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        issues = [
            ErrorIssue(
                field=".".join(map(str, item["loc"])),
                type=item["type"],
                message="Проверьте формат и ограничения поля.",
            )
            for item in error.errors()
        ]
        return error_response(
            request.state.request_id,
            422,
            "validation_error",
            "Проверьте текст, реквизиты и формат запроса.",
            details=issues,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        message = {404: "Адрес не найден.", 405: "Метод запроса не поддерживается."}.get(
            error.status_code,
            "Не удалось выполнить запрос.",
        )
        response = error_response(
            request.state.request_id, error.status_code, "http_error", message
        )
        if error.headers:
            response.headers.update(error.headers)
        return response
