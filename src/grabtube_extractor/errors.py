"""Stable error codes, their HTTP mapping, and the FastAPI exception handler.

Error responses match the contract: ``{ "error": { "code": str, "message": str } }``.
Internal detail stays in logs, never in the response body (Constitution V).
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from .models.domain import ErrorCode

logger = logging.getLogger("grabtube")

# ErrorCode -> HTTP status (data-model.md).
STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.invalid_url: 400,
    ErrorCode.quality_required: 400,
    ErrorCode.unavailable: 404,
    ErrorCode.not_found: 404,
    ErrorCode.result_expired: 410,
    ErrorCode.live_unsupported: 422,
    ErrorCode.drm_protected: 422,
    ErrorCode.no_formats: 422,
    ErrorCode.rate_limited: 429,
    ErrorCode.timeout: 504,
    ErrorCode.internal: 500,
}

# Default user-safe messages; callers may override with a more specific (still safe) message.
DEFAULT_MESSAGE: dict[ErrorCode, str] = {
    ErrorCode.invalid_url: "That link isn't a supported YouTube video or playlist.",
    ErrorCode.quality_required: "A video quality must be selected for MP4 downloads.",
    ErrorCode.unavailable: "This content is unavailable (it may be private, deleted, or region-blocked).",
    ErrorCode.not_found: "No such job.",
    ErrorCode.result_expired: "This result has expired. Please request the download again.",
    ErrorCode.live_unsupported: "Live or upcoming streams aren't supported.",
    ErrorCode.drm_protected: "This content is protected and cannot be downloaded.",
    ErrorCode.no_formats: "No downloadable formats are available for this content.",
    ErrorCode.rate_limited: "Too many requests. Please slow down and try again shortly.",
    ErrorCode.timeout: "The request took too long. Please try again.",
    ErrorCode.internal: "Something went wrong. Please try again.",
}


class ServiceError(Exception):
    """An error with a stable, user-safe code + message."""

    def __init__(self, code: ErrorCode, message: str | None = None, *, retry_after: int | None = None):
        self.code = code
        self.message = message or DEFAULT_MESSAGE[code]
        self.retry_after = retry_after
        super().__init__(f"{code.value}: {self.message}")

    @property
    def http_status(self) -> int:
        return STATUS_BY_CODE[self.code]


def error_body(code: ErrorCode, message: str) -> dict:
    return {"error": {"code": code.value, "message": message}}


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    headers = {}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.http_status,
        content=error_body(exc.code, exc.message),
        headers=headers,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the real detail; return an opaque, user-safe message.
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_body(ErrorCode.internal, DEFAULT_MESSAGE[ErrorCode.internal]),
    )
