from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user_id, get_matching_service
from app.core.errors import ErrorResponse
from app.domains.matching.schemas import MatchReport, MatchRequest
from app.domains.matching.service import MatchingService

router = APIRouter(prefix="/jobs", tags=["matching"])


@router.post(
    "/{job_id}/match",
    response_model=MatchReport,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def build_match_report(
    job_id: str,
    payload: MatchRequest,
    service: Annotated[MatchingService, Depends(get_matching_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> MatchReport:
    return service.build_report(
        user_id=user_id,
        job_id=job_id,
        resume_document_id=payload.resume_document_id,
    )
