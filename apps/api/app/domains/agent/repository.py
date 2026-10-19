from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.agent.model import AgentEvent, AgentRun, ToolReceipt


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run(self, *, user_id: str, run_id: str, for_update: bool = False) -> AgentRun | None:
        statement = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def add_run(self, run: AgentRun) -> None:
        self.session.add(run)
        self.session.flush()

    def add_event(
        self,
        *,
        run: AgentRun,
        event_type: str,
        node: str,
        payload: dict[str, object],
    ) -> AgentEvent:
        sequence = (
            int(
                self.session.scalar(
                    select(func.coalesce(func.max(AgentEvent.sequence), 0)).where(
                        AgentEvent.run_id == run.id
                    )
                )
                or 0
            )
            + 1
        )
        event = AgentEvent(
            run_id=run.id,
            user_id=run.user_id,
            sequence=sequence,
            event_type=event_type,
            node=node,
            payload=payload,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_events(
        self, *, user_id: str, run_id: str, after_sequence: int = 0
    ) -> list[AgentEvent]:
        return list(
            self.session.scalars(
                select(AgentEvent)
                .where(
                    AgentEvent.user_id == user_id,
                    AgentEvent.run_id == run_id,
                    AgentEvent.sequence > after_sequence,
                )
                .order_by(AgentEvent.sequence)
            )
        )

    def get_receipt(self, *, user_id: str, idempotency_key: str) -> ToolReceipt | None:
        return self.session.scalar(
            select(ToolReceipt).where(
                ToolReceipt.user_id == user_id,
                ToolReceipt.idempotency_key == idempotency_key,
            )
        )

    def add_receipt(self, receipt: ToolReceipt) -> None:
        self.session.add(receipt)
        self.session.flush()
