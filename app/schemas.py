from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Route = Literal["policy_search", "order_status", "both", "none"]
Mode = Literal["groq", "demo", "fallback"]


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=20, description="Earlier turns, oldest first")


class ToolCallOut(BaseModel):
    name: str
    arguments: dict[str, Any]
    ok: bool
    result: Any = None


class Source(BaseModel):
    section: str
    score: float


class ChatOut(BaseModel):
    answer: str
    route: Route
    mode: Mode
    tool_calls: list[ToolCallOut]
    sources: list[Source]
    log_id: int


class LogOut(BaseModel):
    id: int
    created_at: datetime
    question: str
    route: str
    mode: str
    tool_calls: list[dict[str, Any]]
    latency_ms: int
    error: str | None
    answer: str
