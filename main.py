"""FastAPI application entry point for the schema-first dashboard service."""

import os
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from api.routes import router
from schemas import ApiError, HealthResponse
from services import ExternalServiceError, ResourceNotFoundError

API_VERSION = "0.1.0"
OPENAPI_VERSION = "3.0.3"
SWAGGER_ASSET_PATH = str(files("swagger_ui_bundle").joinpath("vendor", "swagger-ui-4.15.5"))
LOCAL_STATIC_PATH = Path(__file__).resolve().parent / "static"


class ServiceIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    integration_mode: str
    swagger: str
    openapi: str


def _csv_environment(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [value.strip() for value in raw.split(",") if value.strip()]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    del application
    yield


app = FastAPI(
    title="AiSteth Dashboard API",
    summary="Standalone typed AiSteth dashboard service",
    description=(
        "Schema-first API for aggregate AiSteth dashboard operations."
    ),
    version=API_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={"name": "AiSteth Engineering"},
    license_info={"name": "Proprietary"},
)
app.openapi_version = OPENAPI_VERSION

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_csv_environment("DASHBOARD_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_csv_environment("DASHBOARD_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Request-ID"],
)
app.mount("/docs-assets", StaticFiles(directory=SWAGGER_ASSET_PATH), name="swagger-assets")
app.mount("/static", StaticFiles(directory=LOCAL_STATIC_PATH), name="local-static")


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    return response


@app.exception_handler(ResourceNotFoundError)
async def resource_not_found(request: Request, error: ResourceNotFoundError) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID")
    body = ApiError(code="resource_not_found", message=f"{error.resource} was not found", request_id=request_id)
    return JSONResponse(status_code=404, content=body.model_dump(mode="json", exclude_none=True))


@app.exception_handler(ExternalServiceError)
async def external_service_failure(request: Request, error: ExternalServiceError) -> JSONResponse:
    del error
    request_id = request.headers.get("X-Request-ID")
    body = ApiError(code="service_unavailable", message="Dashboard data is temporarily unavailable", request_id=request_id)
    return JSONResponse(status_code=502, content=body.model_dump(mode="json", exclude_none=True))


@app.get("/", response_model=ServiceIndex, include_in_schema=False)
def service_index() -> ServiceIndex:
    return ServiceIndex(name="AiSteth Dashboard API", version=API_VERSION, integration_mode="server-managed", swagger="/docs", openapi="/openapi.json")


@app.get("/health", response_model=HealthResponse, summary="Service health", tags=["System"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="aisteth-dashboard-api", version=API_VERSION, integration_mode="server-managed", timestamp=datetime.now(timezone.utc))


app.include_router(router)


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui() -> HTMLResponse:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AiSteth Dashboard API - Swagger UI</title>
  <link rel="stylesheet" href="/docs-assets/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="/docs-assets/swagger-ui-bundle.js" defer></script>
  <script src="/docs-assets/swagger-ui-standalone-preset.js" defer></script>
  <script src="/static/swagger-initializer.js" defer></script>
</body>
</html>"""
    return HTMLResponse(content=html)
