"""Normalized order (canonical commerce row; upload + sync aware)."""

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
    from app.models.data_source import DataSource
    from app.models.order_adjustment import OrderAdjustment
    from app.models.order_fulfillment import OrderFulfillment
    from app.models.order_item import OrderItem
    from app.models.order_transaction import OrderTransaction
    from app.models.store import Store
    from app.models.sync_session import SyncSession
    from app.models.upload import Upload


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_upload_id", "upload_id"),
        Index("ix_orders_external_id", "external_order_id"),
        Index("ix_orders_order_date", "order_date"),
        Index("ix_orders_source_name", "source_name"),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_store_id", "store_id"),
        Index("ix_orders_data_source_id", "data_source_id"),
        Index("ix_orders_sync_session_id", "sync_session_id"),
        Index("ix_orders_canonical_key", "canonical_key"),
        Index("ix_orders_shopify_order_gid", "shopify_order_gid"),
        Index("ix_orders_store_platform_external", "store_id", "platform", "external_order_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )
    data_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True
    )
    sync_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sync_sessions.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    canonical_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    external_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shopify_order_gid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_name: Mapped[str] = mapped_column(String(128), nullable=False)
    order_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    financial_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    landing_site: Mapped[str | None] = mapped_column(Text, nullable=True)
    referring_site: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    shipping_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    billing_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    billing_region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shipping_region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subtotal_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    subtotal_before_discounts: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    order_level_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    item_level_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    shipping_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_discounts: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    shipping_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_shipping: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    refunded_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_refunds: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    gross_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    gross_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    total_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_repeat_customer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_from_upload_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    upload: Mapped["Upload"] = relationship(back_populates="orders")
    store: Mapped["Store | None"] = relationship()
    data_source: Mapped["DataSource | None"] = relationship()
    sync_session: Mapped["SyncSession | None"] = relationship()
    customer: Mapped["Customer | None"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    adjustments: Mapped[list["OrderAdjustment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["OrderTransaction"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    fulfillments: Mapped[list["OrderFulfillment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
