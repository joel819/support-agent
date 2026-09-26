"""Every query's path is recorded twice: a row in SQLite (queryable via /logs) and a
structured JSON log line (for whatever collects stdout)."""
import json
import logging

from sqlalchemy.orm import Session

from app.agent.base import AgentResult
from app.models import QueryLog

log = logging.getLogger("support_agent.routing")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def record(db: Session, question: str, result: AgentResult, mode: str, latency_ms: int,
           error: str | None = None) -> QueryLog:
    calls = [{"name": c.name, "arguments": c.arguments, "ok": c.ok} for c in result.tool_calls]
    row = QueryLog(
        question=question,
        route=result.route,
        mode=mode,
        tool_calls=json.dumps(calls),
        latency_ms=latency_ms,
        error=error,
        answer=result.answer[:4000],
    )
    db.add(row)
    db.commit()
    log.info(json.dumps({
        "event": "query_routed",
        "log_id": row.id,
        "route": row.route,
        "mode": mode,
        "tools": [c["name"] for c in calls],
        "latency_ms": latency_ms,
        "error": error,
        "question": question[:200],
    }))
    return row
