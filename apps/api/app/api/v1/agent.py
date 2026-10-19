import json
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_agent_service, get_current_user_id
from app.core.errors import ErrorResponse
from app.domains.agent.schemas import AgentConfirm, AgentRunCreate, AgentRunRead
from app.domains.agent.service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])
ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}


@router.post("/runs", response_model=AgentRunRead, responses=ERRORS)
def create_run(
    payload: AgentRunCreate,
    service: Annotated[AgentService, Depends(get_agent_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> AgentRunRead:
    return service.create_run(user_id=user_id, payload=payload)


@router.get("/runs/{run_id}", response_model=AgentRunRead, responses=ERRORS)
def get_run(
    run_id: str,
    service: Annotated[AgentService, Depends(get_agent_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> AgentRunRead:
    return service.get_run(user_id=user_id, run_id=run_id)


@router.post("/runs/{run_id}/confirm", response_model=AgentRunRead, responses=ERRORS)
def confirm_run(
    run_id: str,
    payload: AgentConfirm,
    service: Annotated[AgentService, Depends(get_agent_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> AgentRunRead:
    return service.confirm(user_id=user_id, run_id=run_id, payload=payload)


@router.post("/runs/{run_id}/resume", response_model=AgentRunRead, responses=ERRORS)
def resume_run(
    run_id: str,
    service: Annotated[AgentService, Depends(get_agent_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> AgentRunRead:
    return service.resume(user_id=user_id, run_id=run_id)


@router.get("/runs/{run_id}/events", responses=ERRORS)
def stream_events(
    run_id: str,
    service: Annotated[AgentService, Depends(get_agent_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    run = service.get_run(user_id=user_id, run_id=run_id)
    try:
        after_sequence = int(last_event_id or 0)
    except ValueError:
        after_sequence = 0
    events = service.repository.list_events(
        user_id=user_id, run_id=run_id, after_sequence=after_sequence
    )

    def generate() -> Iterator[str]:
        for event in events:
            data = json.dumps(event.payload, ensure_ascii=False)
            yield (f"id: {event.sequence}\nevent: {event.event_type}\ndata: {data}\n\n")
        final_data = json.dumps({"run_id": run.id, "status": run.status.value}, ensure_ascii=False)
        yield f"event: stream_end\ndata: {final_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
