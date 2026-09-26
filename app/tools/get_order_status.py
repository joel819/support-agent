import re

from sqlalchemy.orm import Session

from app.models import Order

SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_order_status",
        "description": (
            "Look up a specific order by its order number. Returns status, dates, carrier, tracking number "
            "and items. Only call this when the customer has given an order number."
        ),
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "The order number, e.g. 1042"}},
            "required": ["order_id"],
        },
    },
}

STATUS_TEXT = {
    "processing": "being prepared at our warehouse and has not shipped yet",
    "shipped": "on its way",
    "out_for_delivery": "out for delivery today",
    "delivered": "delivered",
    "delayed": "delayed",
    "cancelled": "cancelled",
    "returned": "returned to us",
    "refunded": "refunded",
}

_DIGITS = re.compile(r"\d{3,8}")


def normalise_order_id(raw: object) -> int | None:
    """Accepts 1042, "1042", "#1042", "ORD-1042"."""
    m = _DIGITS.search(str(raw))
    return int(m.group()) if m else None


def get_order_status(db: Session, order_id: object) -> dict:
    oid = normalise_order_id(order_id)
    if oid is None:
        return {"error": "invalid_order_id", "message": f"'{order_id}' is not a valid order number."}
    order = db.get(Order, oid)
    if order is None:
        return {"error": "order_not_found", "message": f"No order found with number {oid}."}
    # Deliberately no name, email or address: the chat is not authenticated.
    return {
        "order_id": order.id,
        "status": order.status,
        "status_description": STATUS_TEXT.get(order.status, order.status),
        "placed_at": order.placed_at.isoformat(),
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "carrier": order.carrier,
        "tracking_number": order.tracking_number,
        "shipping_country": order.shipping_country,
        "note": order.note,
        "items": [{"name": i.name, "quantity": i.quantity} for i in order.items],
        "total": f"{order.total:.2f} {order.currency}",
    }
