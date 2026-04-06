"""Hybrid store-centric schema: ingestion sources, sync sessions, canonical orders.

Revision ID: 20260406_00
Revises: 20260331_00

================================================================================
ARCHITECTURE NOTE (concise)
================================================================================
NosaProfit CORE evolves from upload-only analysis to a store-centric model:
- **stores** = one analyzed merchant/store (manual demo, Shopify, etc.).
- **data_sources** = ingestion channels (csv_import, shopify_api, shopify_webhook).
- **sync_sessions** = jobs (initial sync, incremental, import, webhook rebuild).
- **raw_payloads** = audit/replay buffer for API/webhook/import rows.
- **orders / order_items / customers** gain nullable store/source/sync links; legacy
  **upload_id** remains required on orders for existing demo pipelines until services
  backfill **store_id** and optionally relax constraints in a later phase.

**Deduping Shopify vs import:** use **canonical_key** and/or
**(store_id, platform, external_order_id)** in application logic; unique constraint
on that tuple is deferred (see TODO in migration) until data is backfilled.

**Backward compatibility:** all new columns are nullable or have safe defaults;
existing CSV/demo flows continue without code changes.

================================================================================
MIGRATION PLAN (order of operations)
================================================================================
1. Create `stores`, `data_sources`, `sync_sessions`, `raw_payloads`.
2. Create `order_adjustments`, `order_transactions`, `order_fulfillments`.
3. ALTER `customers`, `orders`, `order_items`, `uploads`.
4. ALTER `insights`, `metric_snapshots`, `ai_campaign_logs` (+ `updated_at` on
   `ai_campaign_logs` if missing, for ORM TimestampMixin parity).

================================================================================
ERD SUMMARY (plain text)
================================================================================
stores 1--* data_sources
stores 1--* sync_sessions
data_sources 1--* sync_sessions (nullable on session for ad-hoc jobs)
stores 1--* raw_payloads; data_sources 1--* raw_payloads; sync_sessions 1--* raw_payloads

stores 1--* customers; stores 1--* orders; stores 1--* uploads; stores 1--* insights;
          stores 1--* metric_snapshots

data_sources 1--* orders; sync_sessions 1--* orders
uploads *--1 stores (nullable); uploads *--1 data_sources; uploads *--1 sync_sessions

orders 1--* order_items | 1--* order_adjustments | 1--* order_transactions | 1--* order_fulfillments
insights *--1 orders (nullable)

**Note:** `ai_campaign_logs.store_id` remains legacy string (e.g. external id); use
`stores` / FK columns on other tables for analytics joins.

================================================================================
TODO (future cleanup — not executed here)
================================================================================
- Backfill `stores` + `orders.store_id` for historical uploads; then consider
  UNIQUE(store_id, platform, external_order_id) and/or NOT NULL store_id.
- Optionally link `merchants` ↔ `stores` for portal alignment.

================================================================================
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql


revision = "20260406_00"
down_revision = "20260331_00"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = inspect(bind).get_columns(table)
    return any(c.get("name") == column for c in cols)


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    idx = {i["name"] for i in inspect(bind).get_indexes(table)}
    return name in idx


def _fk_safe(name: str, src_table: str, ref_table: str, cols: list, ref_cols: list) -> None:
    try:
        op.create_foreign_key(
            name,
            src_table,
            ref_table,
            cols,
            ref_cols,
            ondelete="SET NULL",
        )
    except Exception:
        pass


def upgrade() -> None:
    # ------------------------------------------------------------------ stores
    if not _table_exists("stores"):
        op.create_table(
            "stores",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("uuid", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=512), nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=True),
            sa.Column("platform", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("platform_store_id", sa.String(length=128), nullable=True),
            sa.Column("shop_domain", sa.String(length=255), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("timezone", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("connected_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("first_data_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_data_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ux_stores_uuid", "stores", ["uuid"], unique=True)
        op.create_index("ix_stores_platform", "stores", ["platform"])
        op.create_index("ux_stores_shop_domain", "stores", ["shop_domain"], unique=True)
        op.create_index("ix_stores_platform_store_id", "stores", ["platform_store_id"])
        op.create_index("ix_stores_status", "stores", ["status"])

    # -------------------------------------------------------------- data_sources
    if not _table_exists("data_sources"):
        op.create_table(
            "data_sources",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "store_id",
                sa.Integer(),
                sa.ForeignKey("stores.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source_type", sa.String(length=64), nullable=False),
            sa.Column("source_name", sa.String(length=255), nullable=True),
            sa.Column("external_source_id", sa.String(length=128), nullable=True),
            sa.Column("priority_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("config_json", mysql.JSON(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_data_sources_store_id", "data_sources", ["store_id"])
        op.create_index("ix_data_sources_source_type", "data_sources", ["source_type"])
        op.create_index(
            "ux_data_sources_store_type_extid",
            "data_sources",
            ["store_id", "source_type", "external_source_id"],
            unique=True,
        )

    # -------------------------------------------------------------- sync_sessions
    if not _table_exists("sync_sessions"):
        op.create_table(
            "sync_sessions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "store_id",
                sa.Integer(),
                sa.ForeignKey("stores.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "data_source_id",
                sa.Integer(),
                sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("sync_type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("cursor_value", sa.Text(), nullable=True),
            sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("meta_json", mysql.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_sync_sessions_store_id", "sync_sessions", ["store_id"])
        op.create_index("ix_sync_sessions_data_source_id", "sync_sessions", ["data_source_id"])
        op.create_index("ix_sync_sessions_sync_type", "sync_sessions", ["sync_type"])
        op.create_index("ix_sync_sessions_status", "sync_sessions", ["status"])

    # --------------------------------------------------------------- raw_payloads
    if not _table_exists("raw_payloads"):
        op.create_table(
            "raw_payloads",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "store_id",
                sa.Integer(),
                sa.ForeignKey("stores.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "data_source_id",
                sa.Integer(),
                sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "sync_session_id",
                sa.Integer(),
                sa.ForeignKey("sync_sessions.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_external_id", sa.String(length=128), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=True),
            sa.Column("payload_json", mysql.JSON(), nullable=False),
            sa.Column(
                "processed_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("processed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_raw_payloads_store_id", "raw_payloads", ["store_id"])
        op.create_index("ix_raw_payloads_entity_type", "raw_payloads", ["entity_type"])
        op.create_index("ix_raw_payloads_processed_status", "raw_payloads", ["processed_status"])
        op.create_index("ix_raw_payloads_payload_hash", "raw_payloads", ["payload_hash"])

    # ---------------------------------------------------------- order_adjustments
    if not _table_exists("order_adjustments"):
        op.create_table(
            "order_adjustments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "order_id",
                sa.Integer(),
                sa.ForeignKey("orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_adjustment_id", sa.String(length=128), nullable=True),
            sa.Column("adjustment_kind", sa.String(length=64), nullable=True),
            sa.Column("label", sa.String(length=255), nullable=True),
            sa.Column("amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("reason", sa.String(length=512), nullable=True),
            sa.Column("metadata_json", mysql.JSON(), nullable=True),
            sa.Column("source_type", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_order_adjustments_order_id", "order_adjustments", ["order_id"])

    # --------------------------------------------------------- order_transactions
    if not _table_exists("order_transactions"):
        op.create_table(
            "order_transactions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "order_id",
                sa.Integer(),
                sa.ForeignKey("orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_transaction_id", sa.String(length=128), nullable=True),
            sa.Column("transaction_kind", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=64), nullable=True),
            sa.Column("amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("gateway", sa.String(length=128), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("metadata_json", mysql.JSON(), nullable=True),
            sa.Column("source_type", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_order_transactions_order_id", "order_transactions", ["order_id"])

    # -------------------------------------------------------- order_fulfillments
    if not _table_exists("order_fulfillments"):
        op.create_table(
            "order_fulfillments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "order_id",
                sa.Integer(),
                sa.ForeignKey("orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_fulfillment_id", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=64), nullable=True),
            sa.Column("tracking_company", sa.String(length=255), nullable=True),
            sa.Column("tracking_number", sa.String(length=255), nullable=True),
            sa.Column("shipped_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("destination_json", mysql.JSON(), nullable=True),
            sa.Column("metadata_json", mysql.JSON(), nullable=True),
            sa.Column("source_type", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_order_fulfillments_order_id", "order_fulfillments", ["order_id"])

    # ------------------------------------------------------------------ customers
    if _table_exists("customers"):
        if not _column_exists("customers", "store_id"):
            op.add_column("customers", sa.Column("store_id", sa.Integer(), nullable=True))
            op.create_index("ix_customers_store_id", "customers", ["store_id"])
            _fk_safe(
                "fk_customers_store_id_stores",
                "customers",
                "stores",
                ["store_id"],
                ["id"],
            )
        if not _column_exists("customers", "source_type"):
            op.add_column("customers", sa.Column("source_type", sa.String(length=64), nullable=True))
        if not _column_exists("customers", "external_customer_id"):
            op.add_column(
                "customers",
                sa.Column("external_customer_id", sa.String(length=128), nullable=True),
            )
            op.create_index("ix_customers_external_customer_id", "customers", ["external_customer_id"])
        if not _column_exists("customers", "phone"):
            op.add_column("customers", sa.Column("phone", sa.String(length=64), nullable=True))
        if not _column_exists("customers", "customer_status"):
            op.add_column(
                "customers",
                sa.Column("customer_status", sa.String(length=64), nullable=True),
            )
        if not _column_exists("customers", "first_order_at"):
            op.add_column(
                "customers",
                sa.Column("first_order_at", sa.DateTime(timezone=False), nullable=True),
            )
        if not _column_exists("customers", "last_order_at"):
            op.add_column(
                "customers",
                sa.Column("last_order_at", sa.DateTime(timezone=False), nullable=True),
            )
        if not _column_exists("customers", "total_orders"):
            op.add_column(
                "customers",
                sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
            )
        if not _column_exists("customers", "total_spent"):
            op.add_column("customers", sa.Column("total_spent", sa.Numeric(18, 2), nullable=True))
        if not _column_exists("customers", "notes"):
            op.add_column("customers", sa.Column("notes", sa.Text(), nullable=True))

    # ---------------------------------------------------------------------- orders
    if _table_exists("orders"):
        ocols = [
            ("store_id", sa.Column("store_id", sa.Integer(), nullable=True)),
            ("data_source_id", sa.Column("data_source_id", sa.Integer(), nullable=True)),
            ("sync_session_id", sa.Column("sync_session_id", sa.Integer(), nullable=True)),
            ("source_type", sa.Column("source_type", sa.String(length=64), nullable=True)),
            (
                "source_priority",
                sa.Column("source_priority", sa.Integer(), nullable=False, server_default="0"),
            ),
            ("canonical_key", sa.Column("canonical_key", sa.String(length=256), nullable=True)),
            (
                "platform",
                sa.Column("platform", sa.String(length=64), nullable=False, server_default="manual"),
            ),
            (
                "external_customer_id",
                sa.Column("external_customer_id", sa.String(length=128), nullable=True),
            ),
            ("shopify_order_gid", sa.Column("shopify_order_gid", sa.String(length=255), nullable=True)),
            ("order_number", sa.Column("order_number", sa.String(length=64), nullable=True)),
            ("order_status", sa.Column("order_status", sa.String(length=64), nullable=True)),
            ("closed_at", sa.Column("closed_at", sa.DateTime(timezone=False), nullable=True)),
            ("cancelled_at", sa.Column("cancelled_at", sa.DateTime(timezone=False), nullable=True)),
            ("cancel_reason", sa.Column("cancel_reason", sa.String(length=512), nullable=True)),
            ("processed_at", sa.Column("processed_at", sa.DateTime(timezone=False), nullable=True)),
            ("tags", sa.Column("tags", sa.Text(), nullable=True)),
            ("landing_site", sa.Column("landing_site", sa.Text(), nullable=True)),
            ("referring_site", sa.Column("referring_site", sa.Text(), nullable=True)),
            ("billing_country", sa.Column("billing_country", sa.String(length=128), nullable=True)),
            ("billing_region", sa.Column("billing_region", sa.String(length=128), nullable=True)),
            ("shipping_region", sa.Column("shipping_region", sa.String(length=128), nullable=True)),
            (
                "subtotal_before_discounts",
                sa.Column("subtotal_before_discounts", sa.Numeric(18, 2), nullable=True),
            ),
            (
                "order_level_discount_amount",
                sa.Column("order_level_discount_amount", sa.Numeric(18, 2), nullable=True),
            ),
            (
                "item_level_discount_amount",
                sa.Column("item_level_discount_amount", sa.Numeric(18, 2), nullable=True),
            ),
            (
                "shipping_discount_amount",
                sa.Column("shipping_discount_amount", sa.Numeric(18, 2), nullable=True),
            ),
            ("total_discounts", sa.Column("total_discounts", sa.Numeric(18, 2), nullable=True)),
            ("total_tax", sa.Column("total_tax", sa.Numeric(18, 2), nullable=True)),
            ("total_shipping", sa.Column("total_shipping", sa.Numeric(18, 2), nullable=True)),
            ("total_refunds", sa.Column("total_refunds", sa.Numeric(18, 2), nullable=True)),
            ("total_cost", sa.Column("total_cost", sa.Numeric(18, 2), nullable=True)),
            ("gross_profit", sa.Column("gross_profit", sa.Numeric(18, 2), nullable=True)),
            ("gross_margin_pct", sa.Column("gross_margin_pct", sa.Numeric(18, 6), nullable=True)),
            (
                "imported_from_upload_id",
                sa.Column("imported_from_upload_id", sa.Integer(), nullable=True),
            ),
            ("last_payload_hash", sa.Column("last_payload_hash", sa.String(length=64), nullable=True)),
            ("last_synced_at", sa.Column("last_synced_at", sa.DateTime(timezone=False), nullable=True)),
        ]
        for name, col in ocols:
            if not _column_exists("orders", name):
                op.add_column("orders", col)

        if _column_exists("orders", "store_id") and not _index_exists("orders", "ix_orders_store_id"):
            op.create_index("ix_orders_store_id", "orders", ["store_id"])
            _fk_safe("fk_orders_store_id_stores", "orders", "stores", ["store_id"], ["id"])
        if _column_exists("orders", "data_source_id") and not _index_exists(
            "orders", "ix_orders_data_source_id"
        ):
            op.create_index("ix_orders_data_source_id", "orders", ["data_source_id"])
            _fk_safe(
                "fk_orders_data_source_id_data_sources",
                "orders",
                "data_sources",
                ["data_source_id"],
                ["id"],
            )
        if _column_exists("orders", "sync_session_id") and not _index_exists(
            "orders", "ix_orders_sync_session_id"
        ):
            op.create_index("ix_orders_sync_session_id", "orders", ["sync_session_id"])
            _fk_safe(
                "fk_orders_sync_session_id_sync_sessions",
                "orders",
                "sync_sessions",
                ["sync_session_id"],
                ["id"],
            )
        if _column_exists("orders", "canonical_key") and not _index_exists(
            "orders", "ix_orders_canonical_key"
        ):
            op.create_index("ix_orders_canonical_key", "orders", ["canonical_key"])
        if _column_exists("orders", "shopify_order_gid") and not _index_exists(
            "orders", "ix_orders_shopify_order_gid"
        ):
            op.create_index("ix_orders_shopify_order_gid", "orders", ["shopify_order_gid"])
        # Non-unique: duplicates may exist until backfill — see architecture note.
        if _column_exists("orders", "store_id") and not _index_exists(
            "orders", "ix_orders_store_platform_external"
        ):
            op.create_index(
                "ix_orders_store_platform_external",
                "orders",
                ["store_id", "platform", "external_order_id"],
            )

    # ------------------------------------------------------------------ order_items
    if _table_exists("order_items"):
        icols = [
            (
                "external_line_item_id",
                sa.Column("external_line_item_id", sa.String(length=128), nullable=True),
            ),
            (
                "product_id_external",
                sa.Column("product_id_external", sa.String(length=128), nullable=True),
            ),
            (
                "variant_id_external",
                sa.Column("variant_id_external", sa.String(length=128), nullable=True),
            ),
            ("product_handle", sa.Column("product_handle", sa.String(length=512), nullable=True)),
            ("product_type", sa.Column("product_type", sa.String(length=255), nullable=True)),
            ("product_vendor", sa.Column("product_vendor", sa.String(length=255), nullable=True)),
            ("sku_normalized", sa.Column("sku_normalized", sa.String(length=128), nullable=True)),
            ("compare_at_price", sa.Column("compare_at_price", sa.Numeric(18, 2), nullable=True)),
            ("cost_amount", sa.Column("cost_amount", sa.Numeric(18, 2), nullable=True)),
            ("gross_profit", sa.Column("gross_profit", sa.Numeric(18, 2), nullable=True)),
            ("gross_margin_pct", sa.Column("gross_margin_pct", sa.Numeric(18, 6), nullable=True)),
            (
                "total_discount_amount",
                sa.Column("total_discount_amount", sa.Numeric(18, 2), nullable=True),
            ),
            ("tax_amount", sa.Column("tax_amount", sa.Numeric(18, 2), nullable=True)),
            (
                "fulfillment_status",
                sa.Column("fulfillment_status", sa.String(length=64), nullable=True),
            ),
            ("source_type", sa.Column("source_type", sa.String(length=64), nullable=True)),
            (
                "imported_from_upload_id",
                sa.Column("imported_from_upload_id", sa.Integer(), nullable=True),
            ),
            ("last_synced_at", sa.Column("last_synced_at", sa.DateTime(timezone=False), nullable=True)),
        ]
        for name, col in icols:
            if not _column_exists("order_items", name):
                op.add_column("order_items", col)

    # ---------------------------------------------------------------------- uploads
    if _table_exists("uploads"):
        ucols = [
            ("store_id", sa.Column("store_id", sa.Integer(), nullable=True)),
            ("data_source_id", sa.Column("data_source_id", sa.Integer(), nullable=True)),
            ("sync_session_id", sa.Column("sync_session_id", sa.Integer(), nullable=True)),
            (
                "import_mode",
                sa.Column("import_mode", sa.String(length=32), nullable=False, server_default="demo"),
            ),
            ("source_file_name", sa.Column("source_file_name", sa.String(length=512), nullable=True)),
            ("source_file_hash", sa.Column("source_file_hash", sa.String(length=64), nullable=True)),
            ("imported_at", sa.Column("imported_at", sa.DateTime(timezone=False), nullable=True)),
        ]
        for name, col in ucols:
            if not _column_exists("uploads", name):
                op.add_column("uploads", col)

        if _column_exists("uploads", "store_id") and not _index_exists("uploads", "ix_uploads_store_id"):
            op.create_index("ix_uploads_store_id", "uploads", ["store_id"])
            _fk_safe("fk_uploads_store_id_stores", "uploads", "stores", ["store_id"], ["id"])
        if _column_exists("uploads", "data_source_id") and not _index_exists(
            "uploads", "ix_uploads_data_source_id"
        ):
            op.create_index("ix_uploads_data_source_id", "uploads", ["data_source_id"])
            _fk_safe(
                "fk_uploads_data_source_id_data_sources",
                "uploads",
                "data_sources",
                ["data_source_id"],
                ["id"],
            )
        if _column_exists("uploads", "sync_session_id") and not _index_exists(
            "uploads", "ix_uploads_sync_session_id"
        ):
            op.create_index("ix_uploads_sync_session_id", "uploads", ["sync_session_id"])
            _fk_safe(
                "fk_uploads_sync_session_id_sync_sessions",
                "uploads",
                "sync_sessions",
                ["sync_session_id"],
                ["id"],
            )

    # -------------------------------------------------------------------- insights
    if _table_exists("insights"):
        incols = [
            ("store_id", sa.Column("store_id", sa.Integer(), nullable=True)),
            ("order_id", sa.Column("order_id", sa.Integer(), nullable=True)),
            ("source_type", sa.Column("source_type", sa.String(length=64), nullable=True)),
            ("sync_session_id", sa.Column("sync_session_id", sa.Integer(), nullable=True)),
            ("surfaced_at", sa.Column("surfaced_at", sa.DateTime(timezone=False), nullable=True)),
        ]
        for name, col in incols:
            if not _column_exists("insights", name):
                op.add_column("insights", col)
        for json_name in ("decision_payload_json", "expected_impact_json"):
            if not _column_exists("insights", json_name):
                op.add_column("insights", sa.Column(json_name, mysql.JSON(), nullable=True))

        if _column_exists("insights", "store_id") and not _index_exists("insights", "ix_insights_store_id"):
            op.create_index("ix_insights_store_id", "insights", ["store_id"])
            _fk_safe("fk_insights_store_id_stores", "insights", "stores", ["store_id"], ["id"])
        if _column_exists("insights", "order_id") and not _index_exists("insights", "ix_insights_order_id"):
            op.create_index("ix_insights_order_id", "insights", ["order_id"])
            _fk_safe("fk_insights_order_id_orders", "insights", "orders", ["order_id"], ["id"])
        if _column_exists("insights", "sync_session_id") and not _index_exists(
            "insights", "ix_insights_sync_session_id"
        ):
            op.create_index("ix_insights_sync_session_id", "insights", ["sync_session_id"])
            _fk_safe(
                "fk_insights_sync_session_id_sync_sessions",
                "insights",
                "sync_sessions",
                ["sync_session_id"],
                ["id"],
            )

    # ---------------------------------------------------------- metric_snapshots
    if _table_exists("metric_snapshots"):
        if not _column_exists("metric_snapshots", "store_id"):
            op.add_column("metric_snapshots", sa.Column("store_id", sa.Integer(), nullable=True))
        if not _column_exists("metric_snapshots", "snapshot_date"):
            op.add_column("metric_snapshots", sa.Column("snapshot_date", sa.Date(), nullable=True))
        if not _column_exists("metric_snapshots", "snapshot_type"):
            op.add_column(
                "metric_snapshots",
                sa.Column(
                    "snapshot_type",
                    sa.String(length=64),
                    nullable=False,
                    server_default="analysis",
                ),
            )
        if not _column_exists("metric_snapshots", "sync_session_id"):
            op.add_column(
                "metric_snapshots",
                sa.Column("sync_session_id", sa.Integer(), nullable=True),
            )

        if _column_exists("metric_snapshots", "store_id") and not _index_exists(
            "metric_snapshots", "ix_metric_snapshots_store_id"
        ):
            op.create_index("ix_metric_snapshots_store_id", "metric_snapshots", ["store_id"])
            _fk_safe(
                "fk_metric_snapshots_store_id_stores",
                "metric_snapshots",
                "stores",
                ["store_id"],
                ["id"],
            )
        if _column_exists("metric_snapshots", "sync_session_id") and not _index_exists(
            "metric_snapshots", "ix_metric_snapshots_sync_session_id"
        ):
            op.create_index(
                "ix_metric_snapshots_sync_session_id",
                "metric_snapshots",
                ["sync_session_id"],
            )
            _fk_safe(
                "fk_metric_snapshots_sync_session_id_sync_sessions",
                "metric_snapshots",
                "sync_sessions",
                ["sync_session_id"],
                ["id"],
            )
        if _column_exists("metric_snapshots", "snapshot_date") and not _index_exists(
            "metric_snapshots", "ix_metric_snapshots_snapshot_date"
        ):
            op.create_index(
                "ix_metric_snapshots_snapshot_date",
                "metric_snapshots",
                ["snapshot_date"],
            )

    # ---------------------------------------------------------- ai_campaign_logs
    if _table_exists("ai_campaign_logs"):
        if not _column_exists("ai_campaign_logs", "data_source_id"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column("data_source_id", sa.Integer(), nullable=True),
            )
        if not _column_exists("ai_campaign_logs", "sync_session_id"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column("sync_session_id", sa.Integer(), nullable=True),
            )
        if not _column_exists("ai_campaign_logs", "source_type"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column("source_type", sa.String(length=64), nullable=True),
            )
        if not _column_exists("ai_campaign_logs", "expected_profit_impact"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column("expected_profit_impact", sa.Numeric(18, 2), nullable=True),
            )
        if not _column_exists("ai_campaign_logs", "confidence_score"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column("confidence_score", sa.Numeric(9, 6), nullable=True),
            )
        if not _column_exists("ai_campaign_logs", "decision_payload_json"):
            op.add_column("ai_campaign_logs", sa.Column("decision_payload_json", mysql.JSON(), nullable=True))
        if not _column_exists("ai_campaign_logs", "executed_at"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column("executed_at", sa.DateTime(timezone=False), nullable=True),
            )
        if not _column_exists("ai_campaign_logs", "linked_order_count"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column("linked_order_count", sa.Integer(), nullable=True),
            )
        if not _column_exists("ai_campaign_logs", "updated_at"):
            op.add_column(
                "ai_campaign_logs",
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=False),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                ),
            )

        if _column_exists("ai_campaign_logs", "data_source_id") and not _index_exists(
            "ai_campaign_logs", "ix_ai_campaign_logs_data_source_id"
        ):
            op.create_index(
                "ix_ai_campaign_logs_data_source_id",
                "ai_campaign_logs",
                ["data_source_id"],
            )
            _fk_safe(
                "fk_ai_campaign_logs_data_source_id_data_sources",
                "ai_campaign_logs",
                "data_sources",
                ["data_source_id"],
                ["id"],
            )
        if _column_exists("ai_campaign_logs", "sync_session_id") and not _index_exists(
            "ai_campaign_logs", "ix_ai_campaign_logs_sync_session_id"
        ):
            op.create_index(
                "ix_ai_campaign_logs_sync_session_id",
                "ai_campaign_logs",
                ["sync_session_id"],
            )
            _fk_safe(
                "fk_ai_campaign_logs_sync_session_id_sync_sessions",
                "ai_campaign_logs",
                "sync_sessions",
                ["sync_session_id"],
                ["id"],
            )


def downgrade() -> None:
    # Additive-only policy: do not drop schema automatically.
    pass
