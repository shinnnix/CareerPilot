from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user_id, get_retrieval_service
from app.domains.retrieval.schemas import (
    IndexRequest,
    IndexResponse,
    SearchRequest,
    SearchResponse,
)
from app.domains.retrieval.service import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/index", response_model=IndexResponse)
def index_chunks(
    payload: IndexRequest,
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> IndexResponse:
    return service.index(user_id=user_id, payload=payload)


@router.post("/search", response_model=SearchResponse)
def search_chunks(
    payload: SearchRequest,
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> SearchResponse:
    return service.search(user_id=user_id, payload=payload)
