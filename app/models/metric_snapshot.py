"""Point-in-time metric values (per upload batch for MVP)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.datetime_cols import CURRENT_TIMESTAMP, MYSQL_DATETIME

if TYPE_CHECKING:
    from app.models.upload import Upload


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = ()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dimension_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    value_numeric: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    value_json: Mapped[dict | list | None] = mapped_column(MySQLJSON, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME, server_default=CURRENT_TIMESTAMP, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME, server_default=CURRENT_TIMESTAMP, nullable=False
    )

    upload: Mapped["Upload"] = relationship(back_populates="metric_snapshots")
