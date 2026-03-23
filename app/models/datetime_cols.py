"""MySQL-safe datetime defaults (avoid 1067 Invalid default value for 'created_at')."""

from sqlalchemy import DateTime, func
from sqlalchemy.sql import text

# Store naive UTC; app layer should use timezone-aware parsing then normalize before save.
MYSQL_DATETIME = DateTime(timezone=False)
CURRENT_TIMESTAMP = text("CURRENT_TIMESTAMP")

__all__ = ["MYSQL_DATETIME", "CURRENT_TIMESTAMP", "func"]
