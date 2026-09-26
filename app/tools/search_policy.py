from app.config import get_settings
from app.knowledge.vector_store import get_policy_store

SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_policy",
        "description": (
            "Search the store's customer policy (returns, refunds, exchanges, damaged items, shipping costs "
            "and times, international shipping, delays and lost parcels, cancellations, warranty, price "
            "adjustments, payment methods, support hours). Use for any question about rules or how things work."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to look up, in plain words"}},
            "required": ["query"],
        },
    },
}


def search_policy(query: str) -> dict:
    s = get_settings()
    hits = [h for h in get_policy_store().search(query, s.top_k) if h.score >= s.effective_min_score]
    return {
        "results": [
            {"section": h.title, "section_id": h.section_id, "text": h.text, "score": round(h.score, 4)}
            for h in hits
        ]
    }
