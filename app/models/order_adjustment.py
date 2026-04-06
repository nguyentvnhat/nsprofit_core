"""Order-level adjustments (discounts, shipping, tax lines) for sync enrichment."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class OrderAdjustment(TimestampMixin, Base):
    __tablename__ = "order_adjustments"
    __table_args__ = (Index("ix_order_adjustments_order_id", "order_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    external_adjustment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    adjustment_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="adjustments")
