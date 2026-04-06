"""Raw payload buffer for replay, debugging, and audit."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.data_source import DataSource
    from app.models.store import Store
    from app.models.sync_session import SyncSession


class RawPayload(TimestampMixin, Base):
    __tablename__ = "raw_payloads"
    __table_args__ = (
        Index("ix_raw_payloads_store_id", "store_id"),
        Index("ix_raw_payloads_entity_type", "entity_type"),
        Index("ix_raw_payloads_processed_status", "processed_status"),
        Index("ix_raw_payloads_payload_hash", "payload_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    data_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True
    )
    sync_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sync_sessions.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict | list] = mapped_column(MySQLJSON, nullable=False)
    processed_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    store: Mapped["Store"] = relationship()
    data_source: Mapped["DataSource | None"] = relationship()
    sync_session: Mapped["SyncSession | None"] = relationship()
