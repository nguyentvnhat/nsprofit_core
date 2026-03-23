"""Registry of loaded YAML rules (audit, versioning, future UI)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.datetime_cols import CURRENT_TIMESTAMP, MYSQL_DATETIME, func


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    __table_args__ = ()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    yaml_source_path: Mapped[str] = mapped_column(String(512), nullable=False)
    definition_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(MYSQL_DATETIME, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME, server_default=CURRENT_TIMESTAMP, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        server_default=CURRENT_TIMESTAMP,
        onupdate=func.now(),
        nullable=False,
    )
