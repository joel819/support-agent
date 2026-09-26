from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # the customer-facing order number
    customer_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320), index=True)
    # processing | shipped | out_for_delivery | delivered | delayed | cancelled | returned | refunded
    status: Mapped[str] = mapped_column(String(32))
    placed_at: Mapped[date] = mapped_column(Date)
    estimated_delivery: Mapped[date | None] = mapped_column(Date)
    delivered_at: Mapped[date | None] = mapped_column(Date)
    carrier: Mapped[str | None] = mapped_column(String(40))
    tracking_number: Mapped[str | None] = mapped_column(String(64))
    shipping_country: Mapped[str] = mapped_column(String(2))
    total: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    note: Mapped[str | None] = mapped_column(Text)  # e.g. reason for a delay

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)

    order: Mapped[Order] = relationship(back_populates="items")


class QueryLog(Base):
    """One row per /chat request: which path the agent took and what it called."""

    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    question: Mapped[str] = mapped_column(Text)
    route: Mapped[str] = mapped_column(String(20), index=True)  # policy_search | order_status | both | none
    mode: Mapped[str] = mapped_column(String(10))  # groq | demo | fallback
    tool_calls: Mapped[str] = mapped_column(Text)  # JSON list of {name, arguments, ok}
    latency_ms: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
