"""Ingestion source (CSV import, Shopify API, webhooks, etc.) for a store."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.sync_session import SyncSession


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        Index("ix_data_sources_store_id", "store_id"),
        Index("ix_data_sources_source_type", "source_type"),
        Index(
            "ux_data_sources_store_type_extid",
            "store_id",
            "source_type",
            "external_source_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_json: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    store: Mapped["Store"] = relationship(back_populates="data_sources")
    sync_sessions: Mapped[list["SyncSession"]] = relationship(back_populates="data_source")
