from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order

router = APIRouter(prefix="/orders", tags=["demo"])


@router.get("")
def list_orders(db: Session = Depends(get_db)) -> list[dict]:
    """Demo helper: sample order numbers and statuses to try in the chat (no personal data)."""
    return [{"order_id": o.id, "status": o.status}
            for o in db.scalars(select(Order).order_by(Order.id)).all()]
