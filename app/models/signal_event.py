"""Detected business signals (inputs to rules and insights)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.upload import Upload


class SignalEvent(TimestampMixin, Base):
    __tablename__ = "signal_events"
    __table_args__ = (
        Index("ix_signal_events_upload", "upload_id"),
        Index("ix_signal_events_code", "signal_code"),
        Index("ix_signal_events_severity", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    signal_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    entity_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    signal_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    signal_context_json: Mapped[dict | None] = mapped_column(MySQLJSON, nullable=True)

    upload: Mapped["Upload"] = relationship(back_populates="signal_events")
