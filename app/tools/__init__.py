"""Tool registry: OpenAI-format schemas for the LLM, and one dispatcher for both agents."""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.tools import get_order_status as _order
from app.tools import search_policy as _policy

TOOL_SCHEMAS = [_policy.SCHEMA, _order.SCHEMA]
TOOL_NAMES = {s["function"]["name"] for s in TOOL_SCHEMAS}


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return "error" not in self.result


def run_tool(db: Session, name: str, arguments: dict[str, Any]) -> ToolCall:
    """Never raises: unknown tools and bad arguments come back as error results
    the model can read and recover from."""
    call = ToolCall(name=name, arguments=arguments)
    try:
        if name == "search_policy":
            call.result = _policy.search_policy(str(arguments["query"]))
        elif name == "get_order_status":
            call.result = _order.get_order_status(db, arguments["order_id"])
        else:
            call.result = {"error": "unknown_tool", "message": f"No tool named {name!r}."}
    except KeyError as exc:
        call.result = {"error": "missing_argument", "message": f"Missing argument {exc}."}
    return call


def route_for(calls: list[ToolCall]) -> str:
    """The route is derived from what was actually called, so logs can't disagree with behaviour."""
    names = {c.name for c in calls}
    if {"search_policy", "get_order_status"} <= names:
        return "both"
    if "get_order_status" in names:
        return "order_status"
    if "search_policy" in names:
        return "policy_search"
    return "none"
