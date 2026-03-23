"""Upload batch metadata (ingestion unit; future: tenant-scoped)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.datetime_cols import CURRENT_TIMESTAMP, MYSQL_DATETIME, func

if TYPE_CHECKING:
    from app.models.insight import Insight
    from app.models.metric_snapshot import MetricSnapshot
    from app.models.order import Order
    from app.models.raw_order import RawOrder
    from app.models.signal_event import SignalEvent


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        # Future SaaS: composite index (tenant_id, created_at)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column("meta", MySQLJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME, server_default=CURRENT_TIMESTAMP, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        server_default=CURRENT_TIMESTAMP,
        onupdate=func.now(),
        nullable=False,
    )

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
