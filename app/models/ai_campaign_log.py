"""AI campaign log: prompt/output + user decision for learning/analytics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Numeric

from app.models.base import Base
from app.models.mixins import TimestampMixin


class AiCampaignLog(TimestampMixin, Base):
    __tablename__ = "ai_campaign_logs"
    __table_args__ = (
        Index("ix_ai_campaign_logs_store", "store_id"),
        Index("ix_ai_campaign_logs_campaign", "campaign_id"),
        Index("ix_ai_campaign_logs_status", "status"),
        Index("ix_ai_campaign_logs_created_at", "created_at"),
        Index("ix_ai_campaign_logs_data_source_id", "data_source_id"),
        Index("ix_ai_campaign_logs_sync_session_id", "sync_session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Legacy external store identifier (e.g. Shopify shop id string); not FK to `stores`.
    store_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    data_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True
    )
    sync_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sync_sessions.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # INPUT (context)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    aov: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    inventory_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    margin_estimate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # AI OUTPUT
    ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    products_selected: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)

    expected_profit_impact: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    decision_payload_json: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)

    # USER ACTION
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    modification_detail: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    linked_order_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # TIMING
    decision_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
