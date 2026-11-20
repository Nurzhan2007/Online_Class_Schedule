"""Uniform API errors.

Every business error is returned as::

    {"detail": {"code": "err.conflict", "params": {"name": {...}}}}

``code`` is a translation key that already exists in the frontend's
``js/i18n.js`` (for example ``err.noSeats`` or ``auth.invalid``), so the
frontend can show the message in kk / ru / en with ``t(code, params)``.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.params = params or {}
        self.headers = headers


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "params": exc.params}},
        headers=exc.headers,
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Invalid input -> 422 {"detail": {"code": "err.validation", "params": {"fields": [...]}}}.

    Only field names are returned (never the submitted values, so a
    password can never be echoed back).
    """
    fields = sorted({
        str(error["loc"][-1])
        for error in exc.errors()
        if error.get("loc")
    })
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": "err.validation", "params": {"fields": fields}}},
    )
