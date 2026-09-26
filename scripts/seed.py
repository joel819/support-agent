"""Load sample orders into SQLite and index the policy into ChromaDB.
Idempotent: orders that already exist are skipped; the policy index is rebuilt.

Usage: python -m scripts.seed
"""
import json
from datetime import date
from pathlib import Path

from app.db import SessionLocal, init_db
from app.knowledge.loader import load_policy
from app.knowledge.vector_store import get_policy_store
from app.models import Order, OrderItem

ORDERS_PATH = Path(__file__).resolve().parent.parent / "data_seed" / "orders.json"
DATE_FIELDS = ("placed_at", "estimated_delivery", "delivered_at")


def seed(verbose: bool = True) -> dict:
    init_db()
    added = 0
    with SessionLocal() as db:
        for raw in json.loads(ORDERS_PATH.read_text(encoding="utf-8")):
            if db.get(Order, raw["id"]):
                continue
            data = {k: (date.fromisoformat(v) if k in DATE_FIELDS and v else v)
                    for k, v in raw.items() if k != "items"}
            order = Order(**data)
            order.items = [OrderItem(**i) for i in raw["items"]]
            db.add(order)
            added += 1
        db.commit()
    sections = get_policy_store().index(load_policy())
    if verbose:
        print(f"Orders added: {added}. Policy sections indexed: {sections}.")
    return {"orders_added": added, "policy_sections": sections}


if __name__ == "__main__":
    seed()
