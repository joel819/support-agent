from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session

from app.schemas import Turn
from app.tools import ToolCall, route_for


class AgentError(Exception):
    """The LLM path failed; the caller falls back to the rule agent."""


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def route(self) -> str:
        return route_for(self.tool_calls)

    @property
    def sources(self) -> list[dict]:
        seen, out = set(), []
        for c in self.tool_calls:
            for r in c.result.get("results", []) if c.name == "search_policy" else []:
                if r["section"] not in seen:
                    seen.add(r["section"])
                    out.append({"section": r["section"], "score": r["score"]})
        return out


class Agent(Protocol):
    name: str

    def run(self, db: Session, message: str, history: list[Turn]) -> AgentResult: ...
