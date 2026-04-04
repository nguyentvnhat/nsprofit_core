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


def cmd_seed() -> None:
    """
    Seed database-managed configuration.

    Today:
    - sync YAML rule definitions into `rule_definitions` (audit + discoverability)

    Intentionally does NOT create uploads/orders/signals/insights.
    """
    from app.database import session_scope
    from app.services.rules_engine import sync_rule_definitions

    with session_scope() as session:
        sync_rule_definitions(session)
    print("Seed complete: rule definitions synced.")


def cmd_provision_db() -> None:
    """One command for production: migrate (Alembic) then seed."""
    import configparser

    from alembic import command
    from alembic.config import Config

    from app.config import get_settings

    settings = get_settings()
    # Build Config with interpolation disabled (DB URLs often contain `%xx` encoding).
    cfg = Config()
    cfg.file_config = configparser.ConfigParser(interpolation=None)
    cfg.config_ini_section = "alembic"
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    cmd_seed()


def main() -> None:
    _ensure_path()
    parser = argparse.ArgumentParser(description="NosaProfit CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create tables via SQLAlchemy metadata (MVP).")
    sub.add_parser("seed", help="Seed config (sync rule definitions).")
    sub.add_parser("provision-db", help="Run migrations then seed (production-safe).")

    p_run = sub.add_parser("run-csv", help="Ingest a Shopify orders export.")
    p_run.add_argument("csv_path", type=Path)

    args = parser.parse_args()
    if args.command == "init-db":
        cmd_init_db()
    elif args.command == "seed":
        cmd_seed()
    elif args.command == "provision-db":
        cmd_provision_db()
    elif args.command == "run-csv":
        cmd_run_csv(args.csv_path)
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
