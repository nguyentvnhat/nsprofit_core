"""Merchant identity for linking uploads to portal merchants."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class Merchant(TimestampMixin, Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    uploads = relationship("Upload", back_populates="merchant")

