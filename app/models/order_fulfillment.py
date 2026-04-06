"""Fulfillment rows for Shopify / OMS sync."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class OrderFulfillment(TimestampMixin, Base):
    __tablename__ = "order_fulfillments"
    __table_args__ = (Index("ix_order_fulfillments_order_id", "order_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    external_fulfillment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tracking_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    destination_json: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="fulfillments")
