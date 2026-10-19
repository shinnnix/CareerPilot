from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class JobNotFoundError(AppError):
    def __init__(self, job_id: str) -> None:
        super().__init__(
            code="JOB_NOT_FOUND",
            message="职位不存在或已被删除",
            status_code=404,
            details={"job_id": job_id},
        )


class DocumentNotFoundError(AppError):
    def __init__(self, document_id: str) -> None:
        super().__init__(
            code="DOCUMENT_NOT_FOUND",
            message="知识库文档不存在或已被删除",
            status_code=404,
            details={"document_id": document_id},
        )


class DuplicateDocumentError(AppError):
    def __init__(self, document_id: str) -> None:
        super().__init__(
            code="DUPLICATE_DOCUMENT",
            message="相同内容已经导入，无需重复建立索引",
            status_code=409,
            details={"existing_document_id": document_id},
        )


class UnsupportedDocumentError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="UNSUPPORTED_DOCUMENT",
            message=message,
            status_code=415,
        )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        payload = ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=getattr(request.state, "request_id", "unknown"),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        payload = ErrorResponse(
            code="VALIDATION_ERROR",
            message="请求字段校验失败",
            details={
                "errors": [
                    {
                        "location": list(error["loc"]),
                        "message": error["msg"],
                        "type": error["type"],
                    }
                    for error in exc.errors()
                ]
            },
            request_id=getattr(request.state, "request_id", "unknown"),
        )
        return JSONResponse(status_code=422, content=payload.model_dump())
