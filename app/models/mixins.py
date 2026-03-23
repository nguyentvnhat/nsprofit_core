"""Reusable column groups — MySQL-safe timestamps (no invalid DEFAULT expressions)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

# Explicit CURRENT_TIMESTAMP avoids driver/SQLAlchemy emitting invalid MySQL defaults.
_CURRENT_TIMESTAMP = text("CURRENT_TIMESTAMP")


class TimestampMixin:
    """created_at / updated_at with server-side insert default; ORM supplies updated_at on UPDATE."""

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=_CURRENT_TIMESTAMP,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=_CURRENT_TIMESTAMP,
        onupdate=func.now(),
        nullable=False,
    )
