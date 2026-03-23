"""Smoke-test DB URL + create tables. Run from `nosaprofit/` with venv + deps."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text

from app.database import get_engine, init_db


def main() -> None:
    init_db()
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    print("DB connected & tables created (init_db)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — script boundary
        print(f"DB check failed: {exc}", file=sys.stderr)
        sys.exit(1)
