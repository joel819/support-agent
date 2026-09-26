from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ChatIn, ChatOut
from app.service import handle_message

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, db: Session = Depends(get_db)) -> ChatOut:
    """Answer a customer message. The response says which route was taken (policy_search,
    order_status, both or none) and every tool call made; the same is written to /logs."""
    return await run_in_threadpool(handle_message, db, body.message.strip(), body.history)
