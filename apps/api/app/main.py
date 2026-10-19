import re
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.errors import AppError, install_error_handlers
from app.core.observability import configure_observability, hash_identifier, log_request
from app.core.rate_limit import anonymized_rate_limit_key, rate_limiter
from app.db.session import get_db

settings = get_settings()
configure_observability()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description="REST API for the CareerPilot internship job manager.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_boundary(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", supplied_request_id)
        else f"req_{uuid4().hex}"
    )
    request.state.request_id = request_id
    started = perf_counter()
    auth_header = request.headers.get("authorization")
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    client_host = (
        forwarded_for
        if settings.trusted_proxy_headers and forwarded_for
        else request.client.host
        if request.client
        else "unknown"
    )
    identity = auth_header or client_host
    bucket = "auth" if request.url.path.startswith(f"{settings.api_v1_prefix}/auth/") else "api"
    limit = (
        settings.auth_rate_limit_per_minute if bucket == "auth" else settings.rate_limit_per_minute
    )
    allowed, retry_after = rate_limiter.check(
        key=f"{bucket}:{anonymized_rate_limit_key(identity)}",
        limit=limit,
    )
    try:
        if allowed:
            response = await call_next(request)
        else:
            response = JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMITED",
                    "message": "请求过于频繁，请稍后重试",
                    "details": {"retry_after_seconds": retry_after},
                    "request_id": request_id,
                },
                headers={"Retry-After": str(retry_after)},
            )
    except Exception as exc:
        route = request.scope.get("route")
        log_request(
            event="http_request",
            request_id=request_id,
            method=request.method,
            route=getattr(route, "path", request.url.path),
            status=500,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            user_id_hash=hash_identifier(getattr(request.state, "user_id", None)),
            error_type=type(exc).__name__,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    route = request.scope.get("route")
    log_request(
        event="http_request",
        request_id=request_id,
        method=request.method,
        route=getattr(route, "path", request.url.path),
        status=response.status_code,
        latency_ms=round((perf_counter() - started) * 1000, 3),
        user_id_hash=hash_identifier(getattr(request.state, "user_id", None)),
    )
    return response


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/ready", tags=["system"])
def readiness(session: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
        if session.get_bind().dialect.name == "postgresql":
            vector_installed = session.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
            if not vector_installed:
                raise RuntimeError("pgvector extension is not installed")
    except Exception as exc:
        raise AppError(
            code="NOT_READY",
            message="数据库或向量扩展尚未就绪",
            status_code=503,
            details={"dependency": "database"},
        ) from exc
    return {"status": "ready", "database": "ok"}


app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
install_error_handlers(app)

