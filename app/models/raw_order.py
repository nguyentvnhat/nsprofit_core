"""Raw CSV rows for audit and reprocessing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Index
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.upload import Upload


class RawOrder(TimestampMixin, Base):
    __tablename__ = "raw_orders"
    __table_args__ = (Index("ix_raw_orders_upload_row", "upload_id", "row_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Legacy schema uses `row_index` and `raw_payload` column names.
    row_number: Mapped[int] = mapped_column("row_index", Integer, nullable=False)
    raw_payload_json: Mapped[dict] = mapped_column("raw_payload", MySQLJSON, nullable=False)

    upload: Mapped["Upload"] = relationship(back_populates="raw_orders")
