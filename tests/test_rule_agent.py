import pytest

from app.agent.rule_agent import RuleAgent, find_order_ids, policy_query
from scripts.eval_routing import EVAL_SET


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Where is order 1019?", ["1019"]),
        ("status of #1008", ["1008"]),
        ("track ORD-1022", ["1022"]),
        ("my order number is 1004", ["1004"]),
        ("1016", ["1016"]),
        ("orders 1001 and #1002", ["1002", "1001"]),
        ("I paid 2026 euros for 30 days", []),  # numbers that aren't order references
    ],
)
def test_find_order_ids(text, expected):
    assert sorted(find_order_ids(text)) == sorted(expected)


def test_policy_query_strips_order_references():
    assert policy_query("Order #1010 arrived damaged") == "arrived damaged"


@pytest.mark.parametrize(
    "question,route",
    [
        ("What is your return policy?", "policy_search"),
        ("Where is order 1019?", "order_status"),
        ("Order 1010 arrived damaged, what can I do?", "both"),
        ("Where is my order?", "none"),
        ("Hello!", "none"),
        ("Tell me a joke about cats", "none"),
    ],
)
def test_routes(db, question, route):
    assert RuleAgent().run(db, question, []).route == route


def test_order_answer_uses_tool_data(db):
    r = RuleAgent().run(db, "Where is order 1019?", [])
    assert "1019" in r.answer and "Swiss Post" in r.answer and "2 Oct 2026" in r.answer


def test_both_route_answers_both_parts(db):
    r = RuleAgent().run(db, "Order 1010 arrived damaged, what can I do?", [])
    assert "delivered" in r.answer
    assert "7 days" in r.answer and "[Damaged, defective or incorrect items]" in r.answer


def test_missing_order_number_asks_instead_of_guessing(db):
    r = RuleAgent().run(db, "Where is my order?", [])
    assert r.tool_calls == [] and "order number" in r.answer


def test_unknown_order_is_reported(db):
    r = RuleAgent().run(db, "Where is order 9999?", [])
    assert "No order found" in r.answer


def test_eval_set_accuracy(db):
    agent = RuleAgent()
    correct = sum(agent.run(db, q, []).route == expected for q, expected in EVAL_SET)
    # Keyword routing can't catch every paraphrase; the LLM agent is there for those.
    assert correct / len(EVAL_SET) >= 0.9
