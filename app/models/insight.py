"""Narrative insights produced from rules and metrics."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.upload import Upload


class Insight(TimestampMixin, Base):
    __tablename__ = "insights"
    __table_args__ = (
        Index("ix_insights_upload", "upload_id"),
        Index("ix_insights_category", "category"),
        Index("ix_insights_priority", "priority"),
        Index("ix_insights_store_id", "store_id"),
        Index("ix_insights_order_id", "order_id"),
        Index("ix_insights_sync_session_id", "sync_session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )
    order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sync_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sync_sessions.id", ondelete="SET NULL"), nullable=True
    )
    insight_code: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    implication_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_data_json: Mapped[dict | None] = mapped_column(MySQLJSON, nullable=True)
    decision_payload_json: Mapped[dict | None] = mapped_column(MySQLJSON, nullable=True)
    expected_impact_json: Mapped[dict | None] = mapped_column(MySQLJSON, nullable=True)
    surfaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    upload: Mapped["Upload"] = relationship(back_populates="insights")
    linked_order: Mapped["Order | None"] = relationship(foreign_keys=[order_id])
