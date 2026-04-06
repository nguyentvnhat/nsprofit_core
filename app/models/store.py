"""Canonical store (merchant storefront) analyzed by the core engine."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.data_source import DataSource
    from app.models.sync_session import SyncSession
    from app.models.upload import Upload


class Store(TimestampMixin, Base):
    __tablename__ = "stores"
    __table_args__ = (
        Index("ux_stores_uuid", "uuid", unique=True),
        Index("ix_stores_platform", "platform"),
        Index("ux_stores_shop_domain", "shop_domain", unique=True),
        Index("ix_stores_platform_store_id", "platform_store_id"),
        Index("ix_stores_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    platform_store_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shop_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    first_data_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_data_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    data_sources: Mapped[list["DataSource"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )
    sync_sessions: Mapped[list["SyncSession"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )
    uploads: Mapped[list["Upload"]] = relationship(back_populates="store")
