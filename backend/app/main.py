"""FastAPI application entry point.

Run from the ``backend`` folder:

    uvicorn app.main:app --reload

The JSON API lives under ``/api``; everything else is served from the
existing frontend folder ``online-class-schedule/`` (unchanged).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.database import close_db, init_db
from app.errors import ApiError, api_error_handler, validation_error_handler
from app.routers import admin, auth, courses, health, me, teacher

logger = logging.getLogger("kbtu")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    try:
        yield
    finally:
        close_db()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Only needed when the frontend is opened from another origin
    # (e.g. VS Code Live Server on port 5500). When the backend serves the
    # frontend itself, requests are same-origin and CORS is not involved.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(courses.router, prefix="/api")
    app.include_router(me.router, prefix="/api")
    app.include_router(teacher.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    # Must stay AFTER all API routers: unknown /api/... paths get a JSON 404
    # instead of falling through to the static frontend.
    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def api_not_found(path: str) -> None:
        raise ApiError(404, "err.apiNotFound", {"path": "/api/" + path})

    if settings.frontend_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.frontend_dir, html=True),
            name="frontend",
        )
    else:
        logger.warning("Frontend folder not found: %s", settings.frontend_dir)

    return app


app = create_app()
