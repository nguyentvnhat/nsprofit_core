"""SQLAlchemy 2.0 declarative base (single metadata registry for Alembic)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass
