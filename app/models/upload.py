"""Upload batch tracking (compatible with current DB schema)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.insight import Insight
    from app.models.metric_snapshot import MetricSnapshot
    from app.models.order import Order
    from app.models.raw_order import RawOrder
    from app.models.signal_event import SignalEvent
    from app.models.promotion_draft import PromotionDraft

class Upload(TimestampMixin, Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Existing table uses `filename` (not `file_name`), keep Python attribute stable.
    file_name: Mapped[str] = mapped_column("filename", String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded", index=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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
