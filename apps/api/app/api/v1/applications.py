from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_application_service,
    get_autofill_service,
    get_current_user_id,
    get_personalization_service,
)
from app.core.errors import ErrorResponse
from app.domains.applications.model import ApplicationStatus
from app.domains.applications.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationList,
    ApplicationMetrics,
    ApplicationRead,
    ApplicationUpdate,
    AutofillPlan,
    AutofillRequest,
    FeedbackRead,
    FeedbackUpsert,
    PersonalizationRequest,
    PersonalizationResult,
)
from app.domains.applications.service import (
    ApplicationService,
    AutofillService,
    PersonalizationService,
)

router = APIRouter(tags=["applications"])
ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}

# Legacy job-based application endpoints. They stay functional for one release
# (plan §9.6 / §13.3) but the workspace equivalents under ``/workspace/applications``
# are the supported path: they are position-scoped, carry snapshots and drive the
# catalog's derived status.
_LEGACY = (
    "旧接口，仅保留兼容；新代码请使用 /workspace/applications（岗位级、带快照与派生状态）。"
)


@router.get("/applications", response_model=ApplicationList, deprecated=True, description=_LEGACY)
def list_applications(
    service: Annotated[ApplicationService, Depends(get_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    application_status: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
) -> ApplicationList:
    return service.list(user_id=user_id, status=application_status)


@router.get(
    "/applications/follow-ups",
    response_model=ApplicationList,
    deprecated=True,
    description=_LEGACY,
)
def list_followups(
    service: Annotated[ApplicationService, Depends(get_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    before: Annotated[datetime | None, Query()] = None,
) -> ApplicationList:
    return service.followups(user_id=user_id, before=before or datetime.now(timezone.utc))


@router.get(
    "/applications/metrics",
    response_model=ApplicationMetrics,
    deprecated=True,
    description=_LEGACY,
)
def application_metrics(
    service: Annotated[ApplicationService, Depends(get_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationMetrics:
    return service.metrics(user_id=user_id)


@router.post(
    "/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    deprecated=True,
    description=_LEGACY,
)
def create_application(
    payload: ApplicationCreate,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationRead:
    return service.create(user_id=user_id, payload=payload)


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationDetail,
    responses=ERRORS,
    deprecated=True,
    description=_LEGACY,
)
def get_application(
    application_id: str,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationDetail:
    return service.get(user_id=user_id, application_id=application_id)


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationDetail,
    responses=ERRORS,
    deprecated=True,
    description=_LEGACY,
)
def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ApplicationDetail:
    return service.update(user_id=user_id, application_id=application_id, payload=payload)


@router.post(
    "/applications/{application_id}/autofill-plan",
    response_model=AutofillPlan,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_autofill_plan(
    application_id: str,
    payload: AutofillRequest,
    service: Annotated[AutofillService, Depends(get_autofill_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> AutofillPlan:
    return service.plan(user_id=user_id, application_id=application_id, payload=payload)


@router.put("/jobs/{job_id}/feedback", response_model=FeedbackRead)
def upsert_feedback(
    job_id: str,
    payload: FeedbackUpsert,
    service: Annotated[ApplicationService, Depends(get_application_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> FeedbackRead:
    return service.upsert_feedback(user_id=user_id, job_id=job_id, payload=payload)


@router.post(
    "/jobs/{job_id}/personalization",
    response_model=PersonalizationResult,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def generate_personalization(
    job_id: str,
    payload: PersonalizationRequest,
    service: Annotated[PersonalizationService, Depends(get_personalization_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> PersonalizationResult:
    return service.generate(
        user_id=user_id,
        job_id=job_id,
        resume_document_id=payload.resume_document_id,
    )
