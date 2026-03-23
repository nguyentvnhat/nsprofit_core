"""Normalized order header (one row per Shopify order)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.datetime_cols import CURRENT_TIMESTAMP, MYSQL_DATETIME, func

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.order_item import OrderItem
    from app.models.upload import Upload


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_upload_external", "upload_id", "external_name"),
        Index("ix_orders_upload_processed", "upload_id", "processed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_name: Mapped[str] = mapped_column(String(128), nullable=False)
    financial_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    subtotal_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    discount_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    shipping_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    refund_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    net_revenue: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        MYSQL_DATETIME, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME, server_default=CURRENT_TIMESTAMP, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        server_default=CURRENT_TIMESTAMP,
        onupdate=func.now(),
        nullable=False,
    )

    upload: Mapped["Upload"] = relationship(back_populates="orders")
    customer: Mapped["Customer | None"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
