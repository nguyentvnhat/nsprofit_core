"""Normalized order (one row per commercial order in an upload)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.order_item import OrderItem
    from app.models.upload import Upload


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_upload_id", "upload_id"),
        Index("ix_orders_external_id", "external_order_id"),
        Index("ix_orders_order_date", "order_date"),
        Index("ix_orders_source_name", "source_name"),
        Index("ix_orders_customer_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    external_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_name: Mapped[str] = mapped_column(String(128), nullable=False)
    order_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    financial_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    shipping_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subtotal_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    shipping_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    refunded_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_repeat_customer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    upload: Mapped["Upload"] = relationship(back_populates="orders")
    customer: Mapped["Customer | None"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
