from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class WorkflowState(TypedDict, total=False):
    message: str
    explicit_intent: str | None
    intent: str
    inputs: dict[str, object]
    action: dict[str, object]
    requires_confirmation: bool
    approved: bool
    ready: bool
    step_count: int
    max_steps: int


def _step(state: WorkflowState) -> int:
    count = int(state.get("step_count", 0)) + 1
    if count > int(state.get("max_steps", 8)):
        raise RuntimeError("Agent exceeded max_steps")
    return count


def route_intent(state: WorkflowState) -> dict[str, object]:
    explicit = state.get("explicit_intent")
    message = state.get("message", "").lower()
    if explicit:
        intent = explicit
    elif any(word in message for word in ("创建申请", "加入看板", "收藏职位")):
        intent = "create_application"
    elif any(word in message for word in ("更新申请", "面试", "offer", "拒绝")):
        intent = "update_application"
    elif any(word in message for word in ("缺什么", "技能差距", "补强")):
        intent = "skill_gap"
    elif any(word in message for word in ("匹配", "适合")):
        intent = "match_report"
    else:
        intent = "job_search"
    return {"intent": intent, "step_count": _step(state)}


def plan_action(state: WorkflowState) -> dict[str, object]:
    intent = state["intent"]
    inputs = state.get("inputs", {})
    argument_names = {
        "job_search": ("query", "city"),
        "match_report": ("job_id", "resume_document_id"),
        "skill_gap": ("job_id", "resume_document_id"),
        "create_application": ("job_id",),
        "update_application": ("application_id", "application_status"),
    }
    arguments = {
        name: inputs[name] for name in argument_names[intent] if inputs.get(name) is not None
    }
    action = {"tool": intent, "arguments": arguments}
    return {
        "action": action,
        "requires_confirmation": intent in {"create_application", "update_application"},
        "step_count": _step(state),
    }


def ask_for_approval(state: WorkflowState) -> dict[str, object]:
    approved = interrupt(
        {
            "kind": "tool_confirmation",
            "action": state["action"],
            "message": "该操作会修改申请数据，请确认。",
        }
    )
    return {"approved": bool(approved), "step_count": _step(state)}


def finish_plan(state: WorkflowState) -> dict[str, object]:
    requires_confirmation = bool(state.get("requires_confirmation"))
    approved = bool(state.get("approved"))
    return {
        "ready": not requires_confirmation or approved,
        "step_count": _step(state),
    }


def confirmation_route(state: WorkflowState) -> str:
    return "approval" if state.get("requires_confirmation") else "finish"


builder = StateGraph(WorkflowState)
builder.add_node("route", route_intent)
builder.add_node("plan", plan_action)
builder.add_node("approval", ask_for_approval)
builder.add_node("finish", finish_plan)
builder.add_edge(START, "route")
builder.add_edge("route", "plan")
builder.add_conditional_edges(
    "plan", confirmation_route, {"approval": "approval", "finish": "finish"}
)
builder.add_edge("approval", "finish")
builder.add_edge("finish", END)

CHECKPOINTER = InMemorySaver()
WORKFLOW_GRAPH = builder.compile(checkpointer=CHECKPOINTER)
