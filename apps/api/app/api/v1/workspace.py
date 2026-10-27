from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile, status

from app.api.dependencies import (
    get_current_user_id,
    get_job_catalog_service,
    get_workspace_application_service,
)
from app.core.errors import ErrorResponse
from app.domains.ai.schemas import AI_CONFIG_HEADER, decode_ai_config
from app.domains.applications.schemas import (
    ApplicationCreatedResult,
    ApplicationCreateRequest,
    ApplicationDetailResult,
    ApplicationListQuery,
    ApplicationListResult,
    ApplicationMetricsResult,
    ApplicationStageDetailRead,
    ApplicationUpdateRequest,
    StageDetailUpsert,
)
from app.domains.applications.service import WorkspaceApplicationService
from app.domains.jobs.schemas import (
    JobAnnouncementDetail,
    JobCatalogList,
    JobCatalogQuery,
    JobFacets,
    JobImportArticleRequest,
    JobImportConfirm,
    JobImportList,
    JobImportRead,
    JobImportTextRequest,
    JobMarkBatch,
    JobMarkRead,
    JobMarkUpdate,
    JobTablePreference,
    JobTablePreferenceUpdate,
)
from app.domains.jobs.service import JobCatalogService
from app.domains.resumes.schemas import ResumeVersionLockRequest

# Plan §5.3.5: optional LLM extraction enhancement, per request, never persisted.
AI_CONFIG_HEADER_DEP = Annotated[
    str | None, Header(alias=AI_CONFIG_HEADER, include_in_schema=False)
]

router = APIRouter(prefix="/workspace", tags=["workspace"])

JOB_ERRORS = {
    404: {"model": ErrorResponse, "description": "Announcement not found"},
    422: {"model": ErrorResponse, "description": "Invalid request"},
}
IMPORT_ERRORS = {
    409: {"model": ErrorResponse, "description": "Duplicate announcement"},
    422: {"model": ErrorResponse, "description": "Import failed"},
}
APPLICATION_ERRORS = {
    404: {"model": ErrorResponse, "description": "Application not found"},
    409: {"model": ErrorResponse, "description": "Invalid transition or stale version"},
    422: {"model": ErrorResponse, "description": "Invalid payload"},
}


def _query(
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    company: Annotated[str | None, Query(max_length=200)] = None,
    job_status: Annotated[str | None, Query(alias="status", max_length=30)] = None,
    company_type: Annotated[str | None, Query(max_length=20)] = None,
    recruitment_type: Annotated[str | None, Query(max_length=20)] = None,
    target_cohort: Annotated[str | None, Query(max_length=20)] = None,
    location: Annotated[str | None, Query(max_length=50)] = None,
    job_category: Annotated[str | None, Query(max_length=50)] = None,
    sort: Annotated[str, Query(pattern="^(updated_desc|published_desc|deadline_asc)$")] = (
        "updated_desc"
    ),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JobCatalogQuery:
    return JobCatalogQuery(
        keyword=keyword,
        company=company,
        status=job_status,
        company_type=company_type,
        recruitment_type=recruitment_type,
        target_cohort=target_cohort,
        location=location,
        job_category=job_category,
        sort=sort,  # type: ignore[arg-type]
        page=page,
        page_size=page_size,
    )


@router.get("/jobs", response_model=JobCatalogList)
def list_jobs(
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    query: Annotated[JobCatalogQuery, Depends(_query)],
) -> JobCatalogList:
    return service.list_catalog(user_id=user_id, query=query)


@router.get("/jobs/filters", response_model=JobFacets)
def job_filters(
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobFacets:
    return service.facets(user_id=user_id)


# Declared before ``/jobs/{announcement_id}`` so "marks" is not read as an id.
@router.patch("/jobs/marks", response_model=list[JobMarkRead], responses=JOB_ERRORS)
def mark_jobs_batch(
    payload: JobMarkBatch,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> list[JobMarkRead]:
    return service.set_marks(user_id=user_id, payload=payload)


@router.get("/jobs/export")
def export_jobs(
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    query: Annotated[JobCatalogQuery, Depends(_query)],
) -> Response:
    content = service.export_csv(user_id=user_id, query=query)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jobs.csv"'},
    )


# -- import pipeline (declared before /jobs/{id}) ---------------------------
@router.get("/jobs/imports", response_model=JobImportList)
def list_job_imports(
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobImportList:
    return service.list_imports(user_id=user_id)


@router.post(
    "/jobs/import/text",
    response_model=JobImportRead,
    status_code=status.HTTP_201_CREATED,
    responses=IMPORT_ERRORS,
)
def import_job_text(
    payload: JobImportTextRequest,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    ai_config: AI_CONFIG_HEADER_DEP = None,
) -> JobImportRead:
    return service.start_text_import(
        user_id=user_id,
        raw_text=payload.raw_text,
        source_name=payload.source_name,
        source_url=str(payload.source_url) if payload.source_url else None,
        ai_config=decode_ai_config(ai_config),
    )


@router.post(
    "/jobs/import/file",
    response_model=JobImportRead,
    status_code=status.HTTP_201_CREATED,
    responses=IMPORT_ERRORS,
)
def import_job_file(
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    file: Annotated[UploadFile, File()],
    ai_config: AI_CONFIG_HEADER_DEP = None,
) -> JobImportRead:
    content = file.file.read()
    return service.start_file_import(
        user_id=user_id,
        file_name=file.filename or "announcement.txt",
        content=content,
        ai_config=decode_ai_config(ai_config),
    )


@router.post(
    "/jobs/import/article",
    response_model=JobImportRead,
    status_code=status.HTTP_201_CREATED,
    responses=IMPORT_ERRORS,
)
def import_job_article(
    payload: JobImportArticleRequest,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    ai_config: AI_CONFIG_HEADER_DEP = None,
) -> JobImportRead:
    return service.start_article_import(
        user_id=user_id,
        url=str(payload.url),
        source_name=payload.source_name,
        ai_config=decode_ai_config(ai_config),
    )


@router.post(
    "/jobs/imports/{import_id}/confirm",
    response_model=JobAnnouncementDetail,
    responses={**JOB_ERRORS, **IMPORT_ERRORS},
)
def confirm_job_import(
    import_id: str,
    payload: JobImportConfirm,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobAnnouncementDetail:
    return service.confirm_import(user_id=user_id, import_id=import_id, payload=payload)


@router.delete(
    "/jobs/imports/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def delete_job_import(
    import_id: str,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> Response:
    service.delete_import(user_id=user_id, import_id=import_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- single announcement ----------------------------------------------------
@router.get("/jobs/{announcement_id}", response_model=JobAnnouncementDetail, responses=JOB_ERRORS)
def get_job_announcement(
    announcement_id: str,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobAnnouncementDetail:
    return service.get_announcement(user_id=user_id, announcement_id=announcement_id)


@router.patch(
    "/jobs/{announcement_id}/mark",
    response_model=JobMarkRead,
    responses=JOB_ERRORS,
)
def mark_job(
    announcement_id: str,
    payload: JobMarkUpdate,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobMarkRead:
    return service.set_mark(user_id=user_id, announcement_id=announcement_id, payload=payload)


# -- preferences ------------------------------------------------------------
@router.get("/preferences/job-table", response_model=JobTablePreference)
def get_job_table_preference(
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobTablePreference:
    return service.get_table_preference(user_id=user_id)


@router.put("/preferences/job-table", response_model=JobTablePreference)
def put_job_table_preference(
    payload: JobTablePreferenceUpdate,
    service: Annotated[JobCatalogService, Depends(get_job_catalog_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobTablePreference:
    return service.save_table_preference(
        user_id=user_id, visible_columns=payload.visible_columns
    )


# -- application records (module 2) ----------------------------------------
def _application_query(
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    application_status: Annotated[
        str | None,
        Query(
            alias="status",
            max_length=30,
            pattern=(
                "^(not_applied|applied|written_test|interview_done|offer|rejected|withdrawn)$"
            ),
        ),
    ] = None,
    sort: Annotated[
        str, Query(pattern="^(applied_desc|updated_desc|follow_up_asc)$")
    ] = "applied_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApplicationListQuery:
    return ApplicationListQuery(
        keyword=keyword,
        status=application_status,
        sort=sort,  # type: ignore[arg-type]
        page=page,
        page_size=page_size,
    )


@router.get("/applications", response_model=ApplicationListResult)
def list_applications(
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    query: Annotated[ApplicationListQuery, Depends(_application_query)],
) -> ApplicationListResult:
    return service.list(user_id=user_id, query=query)


@router.get("/applications/follow-ups", response_model=ApplicationListResult)
def list_application_followups(
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    before: Annotated[str | None, Query(max_length=40)] = None,
) -> ApplicationListResult:
    cutoff = datetime.now(timezone.utc)
    if before:
        cutoff = datetime.fromisoformat(before)
    return service.followups(user_id=user_id, before=cutoff)


@router.get("/applications/metrics", response_model=ApplicationMetricsResult)
def application_metrics(
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationMetricsResult:
    return service.metrics(user_id=user_id)


@router.get("/applications/export")
def export_applications(
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    query: Annotated[ApplicationListQuery, Depends(_application_query)],
) -> Response:
    content = service.export_csv(user_id=user_id, query=query)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="applications.csv"'},
    )


@router.post(
    "/applications",
    response_model=ApplicationCreatedResult,
    status_code=status.HTTP_201_CREATED,
    responses={**APPLICATION_ERRORS, 404: {"model": ErrorResponse}},
)
def create_applications(
    payload: ApplicationCreateRequest,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationCreatedResult:
    items = service.create(user_id=user_id, payload=payload)
    return ApplicationCreatedResult(items=items, total=len(items))


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationDetailResult,
    responses=APPLICATION_ERRORS,
)
def get_application(
    application_id: str,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationDetailResult:
    return service.detail(user_id=user_id, application_id=application_id)


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationDetailResult,
    responses=APPLICATION_ERRORS,
)
def update_application(
    application_id: str,
    payload: ApplicationUpdateRequest,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationDetailResult:
    return service.update(user_id=user_id, application_id=application_id, payload=payload)


@router.delete(
    "/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def delete_application(
    application_id: str,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> Response:
    service.delete(user_id=user_id, application_id=application_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/applications/{application_id}/resume-version",
    response_model=ApplicationDetailResult,
    responses=APPLICATION_ERRORS,
)
def lock_application_resume_version(
    application_id: str,
    payload: ResumeVersionLockRequest,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationDetailResult:
    return service.lock_resume_version(
        user_id=user_id,
        application_id=application_id,
        resume_id=payload.resume_id,
        note=payload.note,
    )


@router.get(
    "/applications/{application_id}/stage-details",
    response_model=list[ApplicationStageDetailRead],
    responses={404: {"model": ErrorResponse}},
)
def list_stage_details(
    application_id: str,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> list[ApplicationStageDetailRead]:
    return service.stage_details(user_id=user_id, application_id=application_id)


@router.put(
    "/applications/{application_id}/stage-details/{stage}",
    response_model=ApplicationStageDetailRead,
    responses=APPLICATION_ERRORS,
)
def upsert_stage_detail(
    application_id: str,
    stage: str,
    payload: StageDetailUpsert,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationStageDetailRead:
    return service.upsert_stage_detail(
        user_id=user_id,
        application_id=application_id,
        stage=stage,
        payload=payload,
    )


@router.delete(
    "/applications/{application_id}/stage-details/{stage}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def delete_stage_detail(
    application_id: str,
    stage: str,
    service: Annotated[WorkspaceApplicationService, Depends(get_workspace_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> Response:
    service.delete_stage_detail(user_id=user_id, application_id=application_id, stage=stage)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
