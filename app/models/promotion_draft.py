"""Persisted promotion drafts for discount/promo recommendations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.upload import Upload


class PromotionDraft(TimestampMixin, Base):
    __tablename__ = "promotion_drafts"
    __table_args__ = (
        Index("ix_promotion_drafts_upload", "upload_id"),
        Index("ix_promotion_drafts_entity", "entity_type", "entity_key"),
        Index("ix_promotion_drafts_status", "status"),
        Index("ix_promotion_drafts_level", "level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )

    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="sku")
    entity_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")

    draft_json: Mapped[dict] = mapped_column(MySQLJSON, nullable=False)

    upload: Mapped["Upload"] = relationship(back_populates="promotion_drafts")

