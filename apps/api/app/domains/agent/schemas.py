from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.agent.model import AgentIntent, AgentRunStatus
from app.domains.applications.model import ApplicationStatus


class AgentRunCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    intent: AgentIntent | None = None
    query: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=50)
    job_id: str | None = None
    resume_document_id: str | None = None
    application_id: str | None = None
    application_status: ApplicationStatus | None = None
    max_steps: int = Field(default=8, ge=3, le=20)


class AgentRunRead(BaseModel):
    id: str
    intent: AgentIntent | None
    status: AgentRunStatus
    current_node: str
    step_count: int
    max_steps: int
    input_payload: dict[str, object]
    checkpoint_state: dict[str, object]
    pending_action: dict[str, object] | None
    result: dict[str, object] | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentConfirm(BaseModel):
    approved: bool
    idempotency_key: str = Field(min_length=8, max_length=100)


class AgentEventRead(BaseModel):
    sequence: int
    event_type: str
    node: str
    payload: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
