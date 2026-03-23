"""CLI entrypoints for bootstrap and batch processing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def cmd_init_db() -> None:
    from app.database import init_db

    init_db()
    print("Database tables created (MVP bootstrap). Use Alembic for production migrations.")


def cmd_run_csv(path: Path) -> None:
    from app.database import session_scope
    from app.services.pipeline import process_shopify_csv

    data = path.read_bytes()
    with session_scope() as session:
        uid = process_shopify_csv(session, file_bytes=data, filename=path.name)
    print(f"Processed upload_id={uid}")


def main() -> None:
    _ensure_path()
    parser = argparse.ArgumentParser(description="NosaProfit CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create tables via SQLAlchemy metadata (MVP).")

    p_run = sub.add_parser("run-csv", help="Ingest a Shopify orders export.")
    p_run.add_argument("csv_path", type=Path)

    args = parser.parse_args()
    if args.command == "init-db":
        cmd_init_db()
    elif args.command == "run-csv":
        cmd_run_csv(args.csv_path)
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
