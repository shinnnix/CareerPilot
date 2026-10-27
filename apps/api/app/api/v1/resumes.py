from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.api.dependencies import (
    get_current_user_id,
    get_resume_optimization_service,
    get_resume_service,
    get_resume_version_service,
)
from app.core.errors import ErrorResponse
from app.domains.documents.file_text import MAX_UPLOAD_BYTES
from app.domains.resumes.model import ResumeTemplate
from app.domains.resumes.schemas import (
    ResumeApplyRequest,
    ResumeApplyResult,
    ResumeDetail,
    ResumeFromDocument,
    ResumeImportText,
    ResumeList,
    ResumeManualCreate,
    ResumeOptimizationList,
    ResumeOptimizationRead,
    ResumeOptimizeRequest,
    ResumeUpdate,
    ResumeVersionDetail,
    ResumeVersionList,
)
from app.domains.resumes.service import (
    ResumeOptimizationService,
    ResumeService,
    ResumeVersionService,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])

RESUME_ERRORS = {
    404: {"model": ErrorResponse, "description": "Resume not found"},
    409: {"model": ErrorResponse, "description": "Resume state conflict"},
    415: {"model": ErrorResponse, "description": "Unsupported resume file"},
    422: {"model": ErrorResponse, "description": "Invalid resume request"},
}


@router.get("", response_model=ResumeList)
def list_resumes(
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResumeList:
    return service.list_resumes(user_id=user_id, page=page, page_size=page_size)


@router.post(
    "/import/text",
    response_model=ResumeDetail,
    status_code=status.HTTP_201_CREATED,
    responses=RESUME_ERRORS,
)
def import_resume_text(
    payload: ResumeImportText,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeDetail:
    return service.import_text(user_id=user_id, payload=payload)


@router.post(
    "/import/upload",
    response_model=ResumeDetail,
    status_code=status.HTTP_201_CREATED,
    responses=RESUME_ERRORS,
)
def import_resume_upload(
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    file: Annotated[UploadFile, File(description="TXT, Markdown or text-based PDF resume")],
    display_name: Annotated[str, Form(min_length=1, max_length=200)],
    template: Annotated[ResumeTemplate, Form()] = ResumeTemplate.classic,
    target_job_id: Annotated[str | None, Form(max_length=36)] = None,
    target_announcement_id: Annotated[str | None, Form(max_length=36)] = None,
) -> ResumeDetail:
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    return service.import_upload(
        user_id=user_id,
        display_name=display_name,
        file_name=file.filename or display_name,
        content=content,
        template=template,
        target_job_id=target_job_id,
        target_announcement_id=target_announcement_id,
    )


@router.post(
    "/from-document",
    response_model=ResumeDetail,
    status_code=status.HTTP_201_CREATED,
    responses=RESUME_ERRORS,
)
def create_resume_from_document(
    payload: ResumeFromDocument,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeDetail:
    return service.create_from_document(user_id=user_id, payload=payload)


@router.post(
    "/manual",
    response_model=ResumeDetail,
    status_code=status.HTTP_201_CREATED,
    responses=RESUME_ERRORS,
)
def create_manual_resume(
    payload: ResumeManualCreate,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeDetail:
    return service.create_manual(user_id=user_id, payload=payload)


@router.get("/{resume_id}/versions", response_model=ResumeVersionList, responses=RESUME_ERRORS)
def list_resume_versions(
    resume_id: str,
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeVersionList:
    return service.list_for_resume(user_id=user_id, resume_id=resume_id)


@router.get(
    "/{resume_id}/versions/{version_no}",
    response_model=ResumeVersionDetail,
    responses=RESUME_ERRORS,
)
def get_resume_version(
    resume_id: str,
    version_no: int,
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeVersionDetail:
    return service.get_version(
        user_id=user_id, resume_id=resume_id, version_no=version_no
    )


@router.get("/{resume_id}", response_model=ResumeDetail, responses=RESUME_ERRORS)
def get_resume(
    resume_id: str,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeDetail:
    return service.get_resume(user_id=user_id, resume_id=resume_id)


@router.patch("/{resume_id}", response_model=ResumeDetail, responses=RESUME_ERRORS)
def update_resume(
    resume_id: str,
    payload: ResumeUpdate,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeDetail:
    return service.update_resume(user_id=user_id, resume_id=resume_id, payload=payload)


@router.post("/{resume_id}/reparse", response_model=ResumeDetail, responses=RESUME_ERRORS)
def reparse_resume(
    resume_id: str,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeDetail:
    return service.reparse_resume(user_id=user_id, resume_id=resume_id)


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: RESUME_ERRORS[404]},
)
def delete_resume(
    resume_id: str,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> Response:
    service.delete_resume(user_id=user_id, resume_id=resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{resume_id}/export", responses=RESUME_ERRORS)
def export_resume(
    resume_id: str,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    fmt: Annotated[Literal["markdown", "html"], Query(alias="format")] = "markdown",
) -> PlainTextResponse:
    content, media_type = service.export_resume(
        user_id=user_id, resume_id=resume_id, fmt=fmt
    )
    return PlainTextResponse(content=content, media_type=media_type)


@router.post(
    "/{resume_id}/optimizations",
    response_model=ResumeOptimizationRead,
    status_code=status.HTTP_201_CREATED,
    responses=RESUME_ERRORS,
)
def create_optimization(
    resume_id: str,
    payload: ResumeOptimizeRequest,
    service: Annotated[ResumeOptimizationService, Depends(get_resume_optimization_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeOptimizationRead:
    return service.optimize(user_id=user_id, resume_id=resume_id, payload=payload)


@router.get(
    "/{resume_id}/optimizations",
    response_model=ResumeOptimizationList,
    responses=RESUME_ERRORS,
)
def list_optimizations(
    resume_id: str,
    service: Annotated[ResumeOptimizationService, Depends(get_resume_optimization_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeOptimizationList:
    return service.list_optimizations(user_id=user_id, resume_id=resume_id)


@router.get(
    "/{resume_id}/optimizations/{optimization_id}",
    response_model=ResumeOptimizationRead,
    responses=RESUME_ERRORS,
)
def get_optimization(
    resume_id: str,
    optimization_id: str,
    service: Annotated[ResumeOptimizationService, Depends(get_resume_optimization_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeOptimizationRead:
    return service.get_optimization(
        user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
    )


@router.post(
    "/{resume_id}/optimizations/{optimization_id}/apply",
    response_model=ResumeApplyResult,
    responses=RESUME_ERRORS,
)
def apply_optimization(
    resume_id: str,
    optimization_id: str,
    payload: ResumeApplyRequest,
    service: Annotated[ResumeOptimizationService, Depends(get_resume_optimization_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeApplyResult:
    return service.apply(
        user_id=user_id,
        resume_id=resume_id,
        optimization_id=optimization_id,
        payload=payload,
    )


@router.post(
    "/{resume_id}/optimizations/{optimization_id}/revert",
    response_model=ResumeDetail,
    responses=RESUME_ERRORS,
)
def revert_optimization(
    resume_id: str,
    optimization_id: str,
    service: Annotated[ResumeOptimizationService, Depends(get_resume_optimization_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeDetail:
    return service.revert(
        user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
    )


@router.post(
    "/{resume_id}/optimizations/{optimization_id}/discard",
    response_model=ResumeOptimizationRead,
    responses=RESUME_ERRORS,
)
def discard_optimization(
    resume_id: str,
    optimization_id: str,
    service: Annotated[ResumeOptimizationService, Depends(get_resume_optimization_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ResumeOptimizationRead:
    return service.discard(
        user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
    )
