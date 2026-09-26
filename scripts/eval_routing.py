"""Measure routing accuracy on labelled questions.

Runs whichever agent is configured (rule agent without GROQ_API_KEY, Groq agent with it)
against the seeded data and compares the route taken with the expected route.
Eval queries are not written to /logs.

Usage: python -m scripts.eval_routing [--verbose]
"""
import argparse
from collections import Counter

from app.agent import AgentError, get_agent
from app.db import SessionLocal
from scripts.seed import seed

# (question, expected route)
EVAL_SET: list[tuple[str, str]] = [
    # policy only
    ("What is your return policy?", "policy_search"),
    ("How long do I have to send something back?", "policy_search"),
    ("How much does express shipping cost?", "policy_search"),
    ("Is shipping free?", "policy_search"),
    ("Do you ship to Switzerland?", "policy_search"),
    ("Will I have to pay customs duties in the UK?", "policy_search"),
    ("How long does a refund take to show up on my card?", "policy_search"),
    ("Can I exchange boots for a bigger size?", "policy_search"),
    ("What does the warranty cover?", "policy_search"),
    ("Do you accept Klarna?", "policy_search"),
    ("What are your support hours?", "policy_search"),
    ("Can I cancel an order after placing it?", "policy_search"),
    ("The price dropped a week after I bought it, can I get the difference?", "policy_search"),
    # order only
    ("Where is order 1019?", "order_status"),
    ("What's the status of #1008?", "order_status"),
    ("Has order number 1004 been delivered?", "order_status"),
    ("Can you track ORD-1022 for me?", "order_status"),
    ("1016", "order_status"),
    ("When will my order 1025 arrive?", "order_status"),
    ("Order 9999 status please", "order_status"),
    # both
    ("Order 1010 arrived damaged, what can I do?", "both"),
    ("I want to return order 1006, how does that work?", "both"),
    ("Can I still cancel order 1021?", "both"),
    ("My order 1014 is late, is it lost? What are my options?", "both"),
    ("Order 1013 came with the wrong size, can I exchange it?", "both"),
    # none
    ("Hi there!", "none"),
    ("Thanks, that's all.", "none"),
    ("Where is my order?", "none"),  # no number: must ask for it, not guess
    ("What's the weather in Berlin tomorrow?", "none"),
    ("Can you write me a poem about tents?", "none"),
]


def evaluate(verbose: bool = False) -> float:
    seed(verbose=False)
    agent = get_agent()
    confusion: Counter[tuple[str, str]] = Counter()
    misses = []
    with SessionLocal() as db:
        for question, expected in EVAL_SET:
            try:
                route = agent.run(db, question, []).route
            except AgentError as exc:
                route = f"error: {exc}"[:40]
            confusion[(expected, route)] += 1
            if route != expected:
                misses.append((question, expected, route))
            elif verbose:
                print(f"  ok    {expected:<14} {question}")
    correct = len(EVAL_SET) - len(misses)
    acc = correct / len(EVAL_SET)
    print(f"\nAgent: {agent.name}   Routing accuracy: {correct}/{len(EVAL_SET)} = {acc:.0%}\n")
    for q, exp, got in misses:
        print(f"  MISS  expected {exp:<14} got {got:<14} {q}")
    return acc


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", action="store_true")
    evaluate(p.parse_args().verbose)
