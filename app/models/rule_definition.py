"""Optional persisted rule metadata (YAML remains primary in MVP)."""

from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin


class RuleDefinition(TimestampMixin, Base):
    __tablename__ = "rule_definitions"
    __table_args__ = (Index("ix_rule_definitions_category", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    condition_json: Mapped[dict | None] = mapped_column(MySQLJSON, nullable=True)
    title_template: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    implication_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_template: Mapped[str | None] = mapped_column(Text, nullable=True)
