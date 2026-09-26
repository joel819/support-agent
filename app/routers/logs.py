import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import QueryLog
from app.schemas import LogOut

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[LogOut])
def list_logs(
    route: str | None = Query(None, pattern="^(policy_search|order_status|both|none)$"),
    mode: str | None = Query(None, pattern="^(groq|demo|fallback)$"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = select(QueryLog).order_by(QueryLog.id.desc()).limit(limit)
    if route:
        q = q.where(QueryLog.route == route)
    if mode:
        q = q.where(QueryLog.mode == mode)
    return [LogOut(**{**{c.name: getattr(r, c.name) for c in QueryLog.__table__.columns},
                      "tool_calls": json.loads(r.tool_calls)})
            for r in db.scalars(q).all()]


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    by_route = dict(db.execute(select(QueryLog.route, func.count()).group_by(QueryLog.route)).all())
    by_mode = dict(db.execute(select(QueryLog.mode, func.count()).group_by(QueryLog.mode)).all())
    total, avg_ms, errors = db.execute(
        select(func.count(), func.avg(QueryLog.latency_ms), func.count(QueryLog.error))
    ).one()
    return {
        "total": total,
        "by_route": {r: by_route.get(r, 0) for r in ("policy_search", "order_status", "both", "none")},
        "by_mode": by_mode,
        "avg_latency_ms": round(avg_ms or 0),
        "llm_errors": errors,
    }
