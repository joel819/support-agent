from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.knowledge.vector_store import get_policy_store
from app.models import Order

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "demo_mode": s.demo_mode,
        "agent": "rule-based (demo)" if s.demo_mode else s.groq_model,
        "embeddings": "hash" if s.embedding_backend == "hash" else s.embedding_model,
        "orders": db.scalar(select(func.count()).select_from(Order)),
        "policy_sections": get_policy_store().count(),
    }
