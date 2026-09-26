from functools import lru_cache

from app.agent.base import Agent, AgentError, AgentResult
from app.config import get_settings


@lru_cache
def get_agent() -> Agent:
    """Groq tool-calling agent when GROQ_API_KEY is set; otherwise the rule-based demo agent."""
    s = get_settings()
    if s.demo_mode:
        from app.agent.rule_agent import RuleAgent

        return RuleAgent()
    from app.agent.groq_agent import GroqAgent

    return GroqAgent(s)


__all__ = ["Agent", "AgentError", "AgentResult", "get_agent"]
