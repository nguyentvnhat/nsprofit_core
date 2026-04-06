"""Line items belonging to an order."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class OrderItem(TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_sku", "sku"),
        Index("ix_order_items_product_name", "product_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    external_line_item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_id_external: Mapped[str | None] = mapped_column(String(128), nullable=True)
    variant_id_external: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_handle: Mapped[str | None] = mapped_column(String(512), nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sku_normalized: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    variant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    line_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_line_revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    gross_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    gross_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    requires_shipping: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_from_upload_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
