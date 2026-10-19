from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_current_user_id, get_job_service
from app.core.errors import ErrorResponse
from app.domains.jobs.model import JobStatus
from app.domains.jobs.schemas import JobCreate, JobList, JobRead, JobUpdate
from app.domains.jobs.service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Job not found"},
    422: {"model": ErrorResponse, "description": "Invalid job data"},
}


@router.get("", response_model=JobList)
def list_jobs(
    service: Annotated[JobService, Depends(get_job_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    city: Annotated[str | None, Query(max_length=50)] = None,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JobList:
    return service.list_jobs(
        user_id=user_id,
        keyword=keyword,
        city=city,
        status=job_status,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobRead, responses=ERROR_RESPONSES)
def get_job(
    job_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobRead:
    return service.get_job(user_id=user_id, job_id=job_id)


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def create_job(
    payload: JobCreate,
    service: Annotated[JobService, Depends(get_job_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobRead:
    return service.create_job(user_id=user_id, payload=payload)


@router.patch("/{job_id}", response_model=JobRead, responses=ERROR_RESPONSES)
def update_job(
    job_id: str,
    payload: JobUpdate,
    service: Annotated[JobService, Depends(get_job_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> JobRead:
    return service.update_job(user_id=user_id, job_id=job_id, payload=payload)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: ERROR_RESPONSES[404]},
)
def delete_job(
    job_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> Response:
    service.delete_job(user_id=user_id, job_id=job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
