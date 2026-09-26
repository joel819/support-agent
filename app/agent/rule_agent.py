"""Demo-mode agent: no API key needed.

Routing is deterministic: order numbers are detected with patterns, policy intent
with keyword sets, and the answer is assembled from the tool results (order fields
and quoted policy sentences). It never invents facts, but it is less flexible than
the LLM agent, e.g. it can't handle a follow-up that refers to an earlier turn.
"""
import math
import re
from datetime import date

from sqlalchemy.orm import Session

from app.agent.base import AgentResult
from app.knowledge.text import terms
from app.schemas import Turn
from app.tools import ToolCall, run_tool

_ORDER_PATTERNS = [
    re.compile(r"#\s?(\d{4,8})\b"),
    re.compile(r"\bORD-?(\d{4,8})\b", re.I),
    re.compile(r"\borders?(?:\s+(?:number|no\.?|num|id))?\s*(?:is|was|:|-)?\s*#?\s*(\d{4,8})\b", re.I),
    re.compile(r"^\s*#?(\d{4,8})\s*[.!?]?\s*$"),  # the whole message is just a number
]

# Words that mean "I need a rule/policy" even when an order number is present.
POLICY_ACTION = {
    "return", "refund", "exchange", "warranty", "damage", "damaged", "broken", "defective", "faulty",
    "wrong", "incorrect", "cancel", "cancelled", "change", "lost", "missing", "price", "adjustment",
    "policy", "custom", "duty", "duties", "compensation", "replace", "replacement", "swap", "size",
}
# Words that point at the policy when no order number is given.
POLICY_GENERAL = POLICY_ACTION | {
    "shipping", "ship", "cost", "free", "international", "express", "standard", "delivery", "deliver",
    "payment", "pay", "paypal", "klarna", "card", "visa", "hour", "open", "contact", "support",
    "email", "country", "countrie", "europe", "uk", "switzerland", "norway", "gift", "fee", "charge",
    "abroad", "worldwide", "usa", "outside", "time", "fast", "quickly", "day",
}
ORDER_WORDS = {"order", "package", "parcel", "status", "track", "tracking", "arrive", "arrived", "shipped", "where"}
GREETINGS = {"hi", "hello", "hey", "thanks", "thank", "cheers", "morning", "evening", "bye"}

_SENT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z]+")


def find_order_ids(message: str) -> list[str]:
    ids: list[str] = []
    for pat in _ORDER_PATTERNS:
        for m in pat.finditer(message):
            if m.group(1) not in ids:
                ids.append(m.group(1))
    return ids[:3]


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "unknown"
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def describe_order(r: dict) -> str:
    if "error" in r:
        return f"{r['message']} Please check the order number; it's in your confirmation email."
    oid, status = r["order_id"], r["status"]
    tracking = f" with {r['carrier']} (tracking {r['tracking_number']})" if r.get("tracking_number") else ""
    eta = _fmt_date(r.get("estimated_delivery"))
    note = f" {r['note']}" if r.get("note") else ""
    text = {
        "processing": f"Order {oid} is being prepared at our warehouse and hasn't shipped yet. Estimated delivery: {eta}.",
        "shipped": f"Order {oid} is on its way{tracking}. Estimated delivery: {eta}.",
        "out_for_delivery": f"Order {oid} is out for delivery today{tracking}.",
        "delivered": f"Order {oid} was delivered on {_fmt_date(r.get('delivered_at'))}.",
        "delayed": f"Order {oid} is delayed.{note} It was expected on {eta}{', tracking ' + r['tracking_number'] if r.get('tracking_number') else ''}.",
        "cancelled": f"Order {oid} was cancelled.{note}",
        "returned": f"Order {oid} was returned to us.{note}",
        "refunded": f"Order {oid} has been refunded.{note}",
    }.get(status, f"Order {oid} has status '{status}'.")
    items = ", ".join(f"{i['quantity']} × {i['name']}" if i["quantity"] > 1 else i["name"] for i in r["items"])
    return f"{text} Items: {items}."


_ORDER_REF = re.compile(r"(#\s?\d+|\bORD-?\d+|\b\d{4,8}\b|\border(?:s)?\b|\bnumber\b)", re.I)


def policy_query(message: str) -> str:
    """Strip order numbers and the word 'order' so they don't skew the policy search."""
    return re.sub(r"\s+", " ", _ORDER_REF.sub(" ", message)).strip() or message


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text.replace("\n", " ")) if len(s.strip()) >= 25]


def quote_policy(question: str, results: list[dict], max_sentences: int = 3) -> str | None:
    """Quote the policy sentences that best match the question, citing their section.

    The best-matching section's opening sentence is always included: policy sections
    lead with the core rule, which matched sentences often only qualify.
    """
    q = terms(question)
    scored: list[tuple[int, float, int, int, str, str]] = []
    for rank, r in enumerate(results):
        for pos, sent in enumerate(_sentences(r["text"])):
            overlap = len(q & (terms(sent) | terms(r["section"])))
            if overlap:
                scored.append((overlap, r["score"], rank, pos, sent, r["section"]))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], -t[1]))
    floor = max(1, math.ceil(scored[0][0] * 0.6))
    picked = [t for t in scored if t[0] >= floor][: max_sentences - 1]
    top_rank = scored[0][2]
    lead = _sentences(results[top_rank]["text"])[0]
    if all(t[4] != lead for t in picked):
        picked.append((0, 0.0, top_rank, 0, lead, results[top_rank]["section"]))
    picked.sort(key=lambda t: (t[2], t[3]))
    return " ".join(f"{s.rstrip('.')}. [{sec}]" for *_, s, sec in picked)


class RuleAgent:
    name = "rule"

    def run(self, db: Session, message: str, history: list[Turn]) -> AgentResult:
        words = terms(message)
        raw_words = set(_WORD.findall(message.lower()))
        ids = find_order_ids(message)
        calls: list[ToolCall] = []

        if ids:
            calls += [run_tool(db, "get_order_status", {"order_id": i}) for i in ids]
            if words & POLICY_ACTION:
                calls.append(run_tool(db, "search_policy", {"query": policy_query(message)}))
        elif words & POLICY_GENERAL:
            calls.append(run_tool(db, "search_policy", {"query": policy_query(message)}))
        elif words & ORDER_WORDS:
            return AgentResult(
                "I can check that for you. What's your order number? You'll find it in your order "
                "confirmation email (for example 1042)."
            )
        elif raw_words & GREETINGS or not words:
            return AgentResult("Hi! I can check an order's status or answer questions about returns, "
                               "shipping, refunds and our other policies. How can I help?")
        else:
            return AgentResult("I can only help with Kestrel orders and store policies, like returns, "
                               "shipping and refunds. Is there something along those lines I can help with?")

        parts = [describe_order(c.result) for c in calls if c.name == "get_order_status"]
        for c in calls:
            if c.name == "search_policy":
                quoted = quote_policy(c.arguments["query"], c.result.get("results", []))
                parts.append(quoted or "I couldn't find anything about that in our policy. Our support "
                             "team can help: support@kestrel.example.")
        return AgentResult(" ".join(parts), calls)
