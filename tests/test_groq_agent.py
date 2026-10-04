"""The Groq agent with the OpenAI client mocked: no key, no network."""
import json
from types import SimpleNamespace

import openai
import pytest

from app.agent.base import AgentError
from app.agent.groq_agent import GroqAgent
from app.config import get_settings


def tool_call(name, args, id_="call_1"):
    return SimpleNamespace(id=id_, type="function",
                           function=SimpleNamespace(name=name, arguments=args if isinstance(args, str) else json.dumps(args)))


def reply(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))])


class Script:
    """Returns queued responses and records every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


@pytest.fixture
def agent():
    return GroqAgent(get_settings().model_copy(update={"groq_api_key": "gsk_test", "max_agent_steps": 4}))


def test_uses_groq_endpoint_and_model(agent, db, monkeypatch):
    script = Script(reply("Hello!"))
    monkeypatch.setattr(agent.client.chat.completions, "create", script)
    agent.run(db, "hi", [])
    assert str(agent.client.base_url).startswith("https://api.groq.com/openai/v1")
    assert script.requests[0]["model"] == "openai/gpt-oss-120b"
    names = {t["function"]["name"] for t in script.requests[0]["tools"]}
    assert names == {"search_policy", "get_order_status"}


def test_order_tool_call_then_answer(agent, db, monkeypatch):
    script = Script(
        reply(tool_calls=[tool_call("get_order_status", {"order_id": "1019"})]),
        reply("Order 1019 is on its way with Swiss Post."),
    )
    monkeypatch.setattr(agent.client.chat.completions, "create", script)
    r = agent.run(db, "Where is order 1019?", [])
    assert r.route == "order_status"
    assert r.answer.startswith("Order 1019")
    tool_msg = script.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and json.loads(tool_msg["content"])["status"] == "shipped"


def test_parallel_tool_calls_make_route_both(agent, db, monkeypatch):
    script = Script(
        reply(tool_calls=[tool_call("get_order_status", {"order_id": "1010"}, "a"),
                          tool_call("search_policy", {"query": "damaged item"}, "b")]),
        reply("Report it within 7 days [Damaged, defective or incorrect items]."),
    )
    monkeypatch.setattr(agent.client.chat.completions, "create", script)
    r = agent.run(db, "Order 1010 arrived damaged", [])
    assert r.route == "both"
    assert r.sources and r.sources[0]["section"]


def test_no_tools_route_none(agent, db, monkeypatch):
    monkeypatch.setattr(agent.client.chat.completions, "create", Script(reply("What's your order number?")))
    assert agent.run(db, "Where is my order?", []).route == "none"


def test_bad_tool_arguments_are_reported_to_model(agent, db, monkeypatch):
    script = Script(reply(tool_calls=[tool_call("get_order_status", "{not json")]), reply("Sorry, which order?"))
    monkeypatch.setattr(agent.client.chat.completions, "create", script)
    r = agent.run(db, "order?", [])
    assert r.tool_calls[0].result["error"] == "bad_arguments"
    assert "bad_arguments" in script.requests[1]["messages"][-1]["content"]


def test_last_step_forces_an_answer(agent, db, monkeypatch):
    loop = reply(tool_calls=[tool_call("search_policy", {"query": "x"})])
    script = Script(loop, loop, loop, reply("Final answer."))
    monkeypatch.setattr(agent.client.chat.completions, "create", script)
    assert agent.run(db, "loop forever", []).answer == "Final answer."
    assert "tools" not in script.requests[-1]  # final step can't call tools


def test_api_errors_become_agent_error(agent, db, monkeypatch):
    def boom(**kwargs):
        raise openai.APIConnectionError(request=None)

    monkeypatch.setattr(agent.client.chat.completions, "create", boom)
    with pytest.raises(AgentError):
        agent.run(db, "hi", [])


def test_history_is_sent(agent, db, monkeypatch):
    from app.schemas import Turn

    script = Script(reply("ok"))
    monkeypatch.setattr(agent.client.chat.completions, "create", script)
    agent.run(db, "1019", [Turn(role="user", content="where is my order?"),
                           Turn(role="assistant", content="What's the number?")])
    roles = [m["role"] for m in script.requests[0]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
