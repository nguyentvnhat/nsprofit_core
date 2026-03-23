"""Rule-derived insight records (narrative applied after evaluation)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.datetime_cols import CURRENT_TIMESTAMP, MYSQL_DATETIME

if TYPE_CHECKING:
    from app.models.upload import Upload


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = ()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    implication: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info", index=True)
    signal_event_ids: Mapped[list | None] = mapped_column(MySQLJSON, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(MySQLJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME, server_default=CURRENT_TIMESTAMP, nullable=False
    )

    upload: Mapped["Upload"] = relationship(back_populates="insights")
