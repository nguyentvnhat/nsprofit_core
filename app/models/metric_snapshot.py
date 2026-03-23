"""Materialized metrics for dashboards and historical comparison."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.upload import Upload


class MetricSnapshot(TimestampMixin, Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index("ix_metric_snapshots_upload", "upload_id"),
        Index("ix_metric_snapshots_code", "metric_code"),
        Index("ix_metric_snapshots_scope", "metric_scope"),
        Index("ix_metric_snapshots_upload_code", "upload_id", "metric_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="overall")
    dimension_1: Mapped[str | None] = mapped_column(String(256), nullable=True)
    dimension_2: Mapped[str | None] = mapped_column(String(256), nullable=True)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False, default="all_time")
    period_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)

    upload: Mapped["Upload"] = relationship(back_populates="metric_snapshots")
