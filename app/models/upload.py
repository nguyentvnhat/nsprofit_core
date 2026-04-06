"""Upload batch tracking (compatible with current DB schema)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.data_source import DataSource
    from app.models.insight import Insight
    from app.models.merchant import Merchant
    from app.models.metric_snapshot import MetricSnapshot
    from app.models.order import Order
    from app.models.promotion_draft import PromotionDraft
    from app.models.raw_order import RawOrder
    from app.models.signal_event import SignalEvent
    from app.models.store import Store
    from app.models.sync_session import SyncSession


class Upload(TimestampMixin, Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("merchants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    store_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    data_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sync_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sync_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    import_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="demo")
    source_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    # Existing table uses `filename` (not `file_name`), keep Python attribute stable.
    file_name: Mapped[str] = mapped_column("filename", String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded", index=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    merchant: Mapped["Merchant | None"] = relationship(back_populates="uploads")
    store: Mapped["Store | None"] = relationship(back_populates="uploads")
    data_source: Mapped["DataSource | None"] = relationship()
    sync_session: Mapped["SyncSession | None"] = relationship()

    raw_orders: Mapped[list["RawOrder"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )
    metric_snapshots: Mapped[list["MetricSnapshot"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )
    signal_events: Mapped[list["SignalEvent"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )
    insights: Mapped[list["Insight"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )
    promotion_drafts: Mapped[list["PromotionDraft"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )
