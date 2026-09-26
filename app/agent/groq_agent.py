"""LLM agent: Llama 3.3 70B on Groq decides which tools to call (OpenAI tool-calling format)."""
import json

import openai
from sqlalchemy.orm import Session

from app.agent.base import AgentError, AgentResult
from app.agent.prompts import SYSTEM_PROMPT
from app.config import Settings
from app.schemas import Turn
from app.tools import TOOL_SCHEMAS, ToolCall, run_tool

MAX_TOOL_RESULT_CHARS = 6000
MAX_HISTORY_TURNS = 6


class GroqAgent:
    name = "groq"

    def __init__(self, settings: Settings):
        self.model = settings.groq_model
        self.temperature = settings.llm_temperature
        self.max_steps = max(1, settings.max_agent_steps)
        self.client = openai.OpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    def _complete(self, messages: list[dict], tools: bool):
        kwargs = {"model": self.model, "temperature": self.temperature, "messages": messages}
        if tools:
            kwargs |= {"tools": TOOL_SCHEMAS, "tool_choice": "auto"}
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except openai.OpenAIError as exc:
            raise AgentError(f"{type(exc).__name__}: {exc}") from exc
        if not resp.choices:
            raise AgentError("Empty response from model")
        return resp.choices[0].message

    def run(self, db: Session, message: str, history: list[Turn]) -> AgentResult:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": t.role, "content": t.content} for t in history[-MAX_HISTORY_TURNS:]]
        messages.append({"role": "user", "content": message})
        calls: list[ToolCall] = []

        for step in range(self.max_steps):
            last_step = step == self.max_steps - 1
            msg = self._complete(messages, tools=not last_step)  # last step must answer, not call tools
            if not msg.tool_calls:
                if not msg.content:
                    raise AgentError("Model returned neither text nor tool calls")
                return AgentResult(msg.content.strip(), calls)

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError
                except ValueError:
                    call = ToolCall(tc.function.name, {"raw": tc.function.arguments},
                                    {"error": "bad_arguments", "message": "Arguments were not a JSON object."})
                else:
                    call = run_tool(db, tc.function.name, args)
                calls.append(call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(call.result)[:MAX_TOOL_RESULT_CHARS],
                })
        raise AgentError("Agent exceeded max steps without answering")
