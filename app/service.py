"""One entry point for a chat message: run the agent, fall back if the LLM fails, log the route."""
import time

from sqlalchemy.orm import Session

from app import routing_log
from app.agent import AgentError, get_agent
from app.agent.rule_agent import RuleAgent
from app.schemas import ChatOut, Source, ToolCallOut, Turn


def handle_message(db: Session, message: str, history: list[Turn]) -> ChatOut:
    start = time.perf_counter()
    agent = get_agent()
    mode, error = ("demo" if agent.name == "rule" else "groq"), None
    try:
        result = agent.run(db, message, history)
    except AgentError as exc:
        mode, error = "fallback", str(exc)[:500]
        result = RuleAgent().run(db, message, history)
    latency = int((time.perf_counter() - start) * 1000)
    row = routing_log.record(db, message, result, mode, latency, error)
    return ChatOut(
        answer=result.answer,
        route=result.route,
        mode=mode,
        tool_calls=[ToolCallOut(name=c.name, arguments=c.arguments, ok=c.ok, result=c.result)
                    for c in result.tool_calls],
        sources=[Source(**s) for s in result.sources],
        log_id=row.id,
    )
