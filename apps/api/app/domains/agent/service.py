import hashlib
import json

from langchain_core.tools import StructuredTool
from langgraph.types import Command
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.agent.graph import WORKFLOW_GRAPH
from app.domains.agent.model import (
    AgentIntent,
    AgentRun,
    AgentRunStatus,
    ToolReceipt,
)
from app.domains.agent.repository import AgentRepository
from app.domains.agent.schemas import AgentConfirm, AgentRunCreate, AgentRunRead
from app.domains.applications.model import ApplicationStatus
from app.domains.applications.schemas import ApplicationCreate, ApplicationUpdate
from app.domains.applications.service import ApplicationService
from app.domains.jobs.service import JobService
from app.domains.matching.service import MatchingService


class AgentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AgentRepository(session)
        self.jobs = JobService(session)
        self.matching = MatchingService(session)
        self.applications = ApplicationService(session)

    def create_run(self, *, user_id: str, payload: AgentRunCreate) -> AgentRunRead:
        run = AgentRun(
            user_id=user_id,
            intent=payload.intent,
            status=AgentRunStatus.running,
            current_node="start",
            step_count=0,
            max_steps=payload.max_steps,
            input_payload=payload.model_dump(mode="json"),
            checkpoint_state={},
        )
        self.repository.add_run(run)
        self.repository.add_event(
            run=run,
            event_type="run_started",
            node="start",
            payload={"message_length": len(payload.message)},
        )
        self.session.commit()
        return self._process_new_run(run=run, payload=payload)

    def get_run(self, *, user_id: str, run_id: str) -> AgentRunRead:
        return AgentRunRead.model_validate(self._get_run(user_id=user_id, run_id=run_id))

    def confirm(self, *, user_id: str, run_id: str, payload: AgentConfirm) -> AgentRunRead:
        run = self._get_run(user_id=user_id, run_id=run_id, for_update=True)
        if run.status != AgentRunStatus.waiting_confirmation or not run.pending_action:
            raise AppError(
                code="RUN_NOT_WAITING_CONFIRMATION",
                message="该 Agent Run 当前没有等待确认的操作",
                status_code=409,
            )
        if not payload.approved:
            self._resume_graph_if_available(run, approved=False)
            run.status = AgentRunStatus.cancelled
            run.current_node = "cancelled"
            run.result = {"approved": False, "message": "用户拒绝了写操作"}
            run.pending_action = None
            self.repository.add_event(
                run=run,
                event_type="confirmation_rejected",
                node="approval",
                payload=run.result,
            )
            self.session.commit()
            return AgentRunRead.model_validate(run)

        self._resume_graph_if_available(run, approved=True)
        try:
            result = self._execute_write_idempotently(
                user_id=user_id,
                action=run.pending_action,
                idempotency_key=payload.idempotency_key,
            )
            self._complete(run=run, result=result, node="tool")
        except Exception as exc:
            self._fail(run=run, exc=exc, node="tool")
            raise
        return AgentRunRead.model_validate(run)

    def resume(self, *, user_id: str, run_id: str) -> AgentRunRead:
        run = self._get_run(user_id=user_id, run_id=run_id, for_update=True)
        if run.status in {
            AgentRunStatus.completed,
            AgentRunStatus.cancelled,
            AgentRunStatus.waiting_confirmation,
        }:
            return AgentRunRead.model_validate(run)
        action = run.pending_action or run.checkpoint_state.get("action")
        if not isinstance(action, dict):
            payload = AgentRunCreate.model_validate(run.input_payload)
            return self._process_new_run(run=run, payload=payload)
        if action.get("tool") in {"create_application", "update_application"}:
            run.status = AgentRunStatus.waiting_confirmation
            run.current_node = "approval"
            run.pending_action = action
            self.repository.add_event(
                run=run,
                event_type="checkpoint_recovered",
                node="approval",
                payload={"requires_confirmation": True},
            )
            self.session.commit()
            return AgentRunRead.model_validate(run)
        try:
            result = self._execute_read(user_id=user_id, action=action)
            self._complete(run=run, result=result, node="tool")
        except Exception as exc:
            self._fail(run=run, exc=exc, node="tool")
            raise
        return AgentRunRead.model_validate(run)

    def _process_new_run(self, *, run: AgentRun, payload: AgentRunCreate) -> AgentRunRead:
        inputs = {
            key: value
            for key, value in payload.model_dump(mode="json").items()
            if key
            in {
                "query",
                "city",
                "job_id",
                "resume_document_id",
                "application_id",
                "application_status",
            }
            and value is not None
        }
        initial_state = {
            "message": payload.message,
            "explicit_intent": payload.intent.value if payload.intent else None,
            "inputs": inputs,
            "step_count": run.step_count,
            "max_steps": run.max_steps,
        }
        try:
            state = WORKFLOW_GRAPH.invoke(initial_state, {"configurable": {"thread_id": run.id}})
            clean_state = {key: value for key, value in state.items() if key != "__interrupt__"}
            run.checkpoint_state = clean_state
            run.intent = AgentIntent(state["intent"])
            run.step_count = int(state.get("step_count", run.step_count))
            action = state.get("action")
            if not isinstance(action, dict):
                raise TypeError("LangGraph did not produce an action")
            self._validate_action(action)
            run.pending_action = action
            self.repository.add_event(
                run=run,
                event_type="intent_routed",
                node="route",
                payload={"intent": run.intent.value},
            )
            self.repository.add_event(
                run=run,
                event_type="tool_planned",
                node="plan",
                payload=action,
            )
            if "__interrupt__" in state:
                run.status = AgentRunStatus.waiting_confirmation
                run.current_node = "approval"
                self.repository.add_event(
                    run=run,
                    event_type="confirmation_required",
                    node="approval",
                    payload={"action": action},
                )
                self.session.commit()
                return AgentRunRead.model_validate(run)
            run.current_node = "tool"
            self.repository.add_event(
                run=run,
                event_type="tool_started",
                node="tool",
                payload={"tool": action["tool"]},
            )
            self.session.commit()
            result = self._execute_read(user_id=run.user_id, action=action)
            self._complete(run=run, result=result, node="tool")
        except Exception as exc:
            self._fail(run=run, exc=exc, node=run.current_node)
            raise
        return AgentRunRead.model_validate(run)

    def _execute_read(self, *, user_id: str, action: dict[str, object]) -> dict[str, object]:
        tools = self._build_read_tools(user_id=user_id)
        tool_name = str(action["tool"])
        tool = tools.get(tool_name)
        if tool is None:
            raise AppError(
                code="TOOL_REQUIRES_CONFIRMATION",
                message="写操作必须先经过人工确认",
                status_code=409,
            )
        return tool.invoke(action.get("arguments", {}))

    def _build_read_tools(self, *, user_id: str) -> dict[str, StructuredTool]:
        def search_jobs(query: str = "", city: str | None = None) -> dict[str, object]:
            result = self.jobs.list_jobs(
                user_id=user_id,
                keyword=query or None,
                city=city,
                status=None,
                page=1,
                page_size=10,
            )
            return result.model_dump(mode="json")

        def match_report(job_id: str, resume_document_id: str) -> dict[str, object]:
            return self.matching.build_report(
                user_id=user_id,
                job_id=job_id,
                resume_document_id=resume_document_id,
            ).model_dump(mode="json")

        def skill_gap(job_id: str, resume_document_id: str) -> dict[str, object]:
            report = self.matching.build_report(
                user_id=user_id,
                job_id=job_id,
                resume_document_id=resume_document_id,
            )
            return {
                "job_id": job_id,
                "missing_required_skills": report.missing_required_skills,
                "missing_preferred_skills": report.missing_preferred_skills,
                "evidence": [item.model_dump(mode="json") for item in report.evidence],
            }

        return {
            "job_search": StructuredTool.from_function(
                search_jobs,
                name="job_search",
                description="Search owned internship jobs with keyword and city filters.",
            ),
            "match_report": StructuredTool.from_function(
                match_report,
                name="match_report",
                description="Build an explainable job-to-resume match report.",
            ),
            "skill_gap": StructuredTool.from_function(
                skill_gap,
                name="skill_gap",
                description="List skill gaps backed by job and resume evidence.",
            ),
        }

    def _execute_write_idempotently(
        self,
        *,
        user_id: str,
        action: dict[str, object],
        idempotency_key: str,
    ) -> dict[str, object]:
        request_hash = hashlib.sha256(
            json.dumps(action, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        receipt = self.repository.get_receipt(user_id=user_id, idempotency_key=idempotency_key)
        if receipt:
            if receipt.request_hash != request_hash:
                raise AppError(
                    code="IDEMPOTENCY_KEY_REUSED",
                    message="同一幂等 Key 不能用于不同操作",
                    status_code=409,
                )
            return receipt.result
        tool_name = str(action["tool"])
        arguments = dict(action.get("arguments", {}))
        if tool_name == "create_application":
            job_id = str(arguments.get("job_id") or "")
            existing = self.applications.repository.get_by_job(user_id=user_id, job_id=job_id)
            if existing:
                result = self.applications.get(
                    user_id=user_id, application_id=existing.id
                ).model_dump(mode="json")
            else:
                result = self.applications.create(
                    user_id=user_id, payload=ApplicationCreate(job_id=job_id)
                ).model_dump(mode="json")
        elif tool_name == "update_application":
            status = ApplicationStatus(str(arguments.get("application_status")))
            result = self.applications.update(
                user_id=user_id,
                application_id=str(arguments.get("application_id") or ""),
                payload=ApplicationUpdate(status=status, event_note="Agent confirmed update"),
            ).model_dump(mode="json")
        else:
            raise AppError(
                code="UNKNOWN_TOOL",
                message=f"未知写操作：{tool_name}",
                status_code=422,
            )
        try:
            self.repository.add_receipt(
                ToolReceipt(
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                    tool_name=tool_name,
                    request_hash=request_hash,
                    result=result,
                )
            )
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            concurrent = self.repository.get_receipt(
                user_id=user_id, idempotency_key=idempotency_key
            )
            if concurrent and concurrent.request_hash == request_hash:
                return concurrent.result
            raise AppError(
                code="IDEMPOTENCY_KEY_REUSED",
                message="同一幂等 Key 不能用于不同操作",
                status_code=409,
            ) from None
        return result

    @staticmethod
    def _validate_action(action: dict[str, object]) -> None:
        tool_name = str(action.get("tool") or "")
        arguments = action.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        required = {
            "job_search": (),
            "match_report": ("job_id", "resume_document_id"),
            "skill_gap": ("job_id", "resume_document_id"),
            "create_application": ("job_id",),
            "update_application": ("application_id", "application_status"),
        }
        if tool_name not in required:
            raise AppError(
                code="UNKNOWN_TOOL",
                message=f"未知工具：{tool_name}",
                status_code=422,
            )
        missing = [name for name in required[tool_name] if not arguments.get(name)]
        if missing:
            raise AppError(
                code="AGENT_INPUT_MISSING",
                message=f"Agent 缺少必要输入：{', '.join(missing)}",
                status_code=422,
                details={"missing": missing},
            )

    def _resume_graph_if_available(self, run: AgentRun, *, approved: bool) -> None:
        try:
            state = WORKFLOW_GRAPH.invoke(
                Command(resume=approved),
                {"configurable": {"thread_id": run.id}},
            )
            if state.get("action") == run.pending_action:
                run.step_count = int(state.get("step_count", run.step_count))
                run.checkpoint_state = {
                    key: value for key, value in state.items() if key != "__interrupt__"
                }
                return
        except (KeyError, RuntimeError, TypeError, ValueError):
            # The durable database checkpoint below is the restart fallback.
            ...
        self.repository.add_event(
            run=run,
            event_type="checkpoint_recovered",
            node="approval",
            payload={"source": "database", "approved": approved},
        )
        if not approved:
            run.step_count = min(run.step_count + 1, run.max_steps)
            return
        if run.step_count + 2 > run.max_steps:
            raise AppError(
                code="MAX_STEPS_EXCEEDED",
                message="Agent 超过最大步骤数，已停止执行",
                status_code=409,
            )
        run.step_count += 2

    def _complete(self, *, run: AgentRun, result: dict[str, object], node: str) -> None:
        if run.step_count + 1 > run.max_steps:
            raise AppError(
                code="MAX_STEPS_EXCEEDED",
                message="Agent 超过最大步骤数，已停止执行",
                status_code=409,
            )
        run.step_count += 1
        run.status = AgentRunStatus.completed
        run.current_node = "completed"
        run.result = result
        run.pending_action = None
        run.last_error = None
        self.repository.add_event(
            run=run,
            event_type="run_completed",
            node=node,
            payload={"summary": self._result_summary(result)},
        )
        self.session.commit()

    @staticmethod
    def _result_summary(result: dict[str, object]) -> dict[str, object]:
        summary: dict[str, object] = {
            "keys": sorted(result.keys()),
        }
        for key in ("id", "job_id", "application_id", "total", "eligible"):
            value = result.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                summary[key] = value
        items = result.get("items")
        if isinstance(items, list):
            summary["item_count"] = len(items)
            summary["item_ids"] = [
                item.get("id")
                for item in items[:10]
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
        evidence = result.get("evidence")
        if isinstance(evidence, list):
            summary["citation_chunk_ids"] = [
                item.get("chunk_id")
                for item in evidence[:10]
                if isinstance(item, dict) and isinstance(item.get("chunk_id"), str)
            ]
        return summary

    def _fail(self, *, run: AgentRun, exc: Exception, node: str) -> None:
        self.session.rollback()
        run = self._get_run(user_id=run.user_id, run_id=run.id)
        run.status = AgentRunStatus.failed
        run.current_node = node
        run.last_error = str(exc)[:2000]
        self.repository.add_event(
            run=run,
            event_type="run_failed",
            node=node,
            payload={"error": run.last_error},
        )
        self.session.commit()

    def _get_run(self, *, user_id: str, run_id: str, for_update: bool = False) -> AgentRun:
        run = self.repository.get_run(user_id=user_id, run_id=run_id, for_update=for_update)
        if run is None:
            raise AppError(
                code="AGENT_RUN_NOT_FOUND",
                message="Agent Run 不存在或无权访问",
                status_code=404,
                details={"run_id": run_id},
            )
        return run
