"""Domain exceptions and FastAPI exception handlers.

Custom exception classes are derived from ``AppError`` so the global
handler can map them to a uniform JSON envelope.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger

logger = get_logger(__name__)


# ---- Base exception ---------------------------------------------------------


class AppError(Exception):
    """Base class for all expected, recoverable application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    safe_message: str = "An internal error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.safe_message)
        self.message = message or self.safe_message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}

    def to_dict(self, request_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            body["error"]["details"] = self.details
        if request_id:
            body["error"]["request_id"] = request_id
        return body


# ---- Specific subclasses ----------------------------------------------------


class ValidationError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "VALIDATION_ERROR"
    safe_message = "Request validation failed."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_REQUIRED"
    safe_message = "Authentication required."


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    safe_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    safe_message = "Resource not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    safe_message = "Resource conflict."


class UnsupportedFormatError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "UNSUPPORTED_FORMAT"
    safe_message = "The requested format is not supported."


class FileTooLargeError(AppError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "FILE_TOO_LARGE"
    safe_message = "Uploaded file exceeds the maximum allowed size."


class RateLimitExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"
    safe_message = "Too many requests. Please try again later."


class ConversionFailedError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "CONVERSION_FAILED"
    safe_message = "Document conversion failed."


class StorageError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "STORAGE_ERROR"
    safe_message = "Storage backend is currently unavailable."


class AntivirusError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "ANTIVIRUS_REJECTED"
    safe_message = "File rejected by anti-virus scanner."


# ---- FastAPI exception handlers ---------------------------------------------


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.info(
        "app_error",
        code=exc.code,
        status=exc.status_code,
        path=request.url.path,
        method=request.method,
        details=exc.details,
    )
    headers: dict[str, str] = {}
    if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        retry_after = exc.details.get("retry_after") if isinstance(exc.details, dict) else None
        if retry_after is not None:
            headers["Retry-After"] = str(int(retry_after))
    return JSONResponse(
        content=exc.to_dict(request_id=_request_id(request)),
        status_code=exc.status_code,
        headers=headers,
    )


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    err = AppError(
        message=str(exc.detail) if exc.detail else "HTTP error",
        code=f"HTTP_{exc.status_code}",
        status_code=exc.status_code,
    )
    return await _app_error_handler(request, err)


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: list[dict[str, Any]] = []
    for e in exc.errors():
        errors.append(
            {
                "loc": list(e.get("loc", [])),
                "msg": e.get("msg", ""),
                "type": e.get("type", ""),
            }
        )
    err = ValidationError(
        message="Request validation failed.",
        details={"errors": errors},
    )
    return await _app_error_handler(request, err)


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
    )
    err = AppError(
        message="An unexpected error occurred. The incident has been logged.",
        code="INTERNAL_ERROR",
        status_code=500,
    )
    return JSONResponse(
        content=err.to_dict(request_id=_request_id(request)),
        status_code=500,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach exception handlers to a FastAPI app."""
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


__all__ = [
    "AntivirusError",
    "AppError",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "ConversionFailedError",
    "FileTooLargeError",
    "NotFoundError",
    "RateLimitExceededError",
    "StorageError",
    "UnsupportedFormatError",
    "ValidationError",
    "register_exception_handlers",
]
