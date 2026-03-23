"""Validate DB URL, import all models, and create tables."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from app import models  # noqa: F401 — register mappers
    from app.database import get_engine
    from app.models import (
        Base,
        Customer,
        Insight,
        MetricSnapshot,
        Order,
        OrderItem,
        RawOrder,
        RuleDefinition,
        SignalEvent,
        Upload,
    )

    _ = (
        Upload,
        RawOrder,
        Customer,
        Order,
        OrderItem,
        MetricSnapshot,
        SignalEvent,
        Insight,
        RuleDefinition,
    )

    from sqlalchemy import text

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    print("Success: connected to MySQL and created all tables (Base.metadata.create_all).")
except Exception as exc:  # noqa: BLE001
    print("Database setup failed:", exc, file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)
