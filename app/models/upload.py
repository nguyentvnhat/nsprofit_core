"""Upload batch: source file tracking and processing lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.insight import Insight
    from app.models.metric_snapshot import MetricSnapshot
    from app.models.order import Order
    from app.models.raw_order import RawOrder
    from app.models.signal_event import SignalEvent

_CURRENT_TIMESTAMP = text("CURRENT_TIMESTAMP")


class Upload(TimestampMixin, Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False, default="csv")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="shopify_csv")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded", index=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=_CURRENT_TIMESTAMP,
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
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
