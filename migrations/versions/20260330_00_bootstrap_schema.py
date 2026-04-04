"""bootstrap core schema (create missing tables)

Revision ID: 20260330_00
Revises:
Create Date: 2026-03-30

Goal:
- Allow `alembic upgrade head` to run on a **fresh empty DB**.
- Never drop existing tables (additive-only philosophy).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql


revision = "20260330_00"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return insp.has_table(name)


def upgrade() -> None:
    # uploads (core anchor for FKs)
    if not _table_exists("uploads"):
        op.create_table(
            "uploads",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("filename", sa.String(length=512), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
            sa.Column("row_count", sa.Integer(), nullable=True),
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
        op.create_index("ix_uploads_status", "uploads", ["status"])

    # customers
    if not _table_exists("customers"):
        op.create_table(
            "customers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("external_id", sa.String(length=64), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=True),
            sa.Column("first_name", sa.String(length=255), nullable=True),
            sa.Column("last_name", sa.String(length=255), nullable=True),
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
        op.create_index("ix_customers_email", "customers", ["email"])

    # orders
    if not _table_exists("orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "upload_id",
                sa.Integer(),
                sa.ForeignKey("uploads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_order_id", sa.String(length=64), nullable=True),
            sa.Column("order_name", sa.String(length=128), nullable=False),
            sa.Column("order_date", sa.DateTime(timezone=False), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("financial_status", sa.String(length=64), nullable=True),
            sa.Column("fulfillment_status", sa.String(length=64), nullable=True),
            sa.Column("source_name", sa.String(length=128), nullable=True),
            sa.Column(
                "customer_id",
                sa.Integer(),
                sa.ForeignKey("customers.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("shipping_country", sa.String(length=128), nullable=True),
            sa.Column("subtotal_price", sa.Numeric(18, 2), nullable=True),
            sa.Column("discount_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("shipping_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("tax_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("refunded_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("total_price", sa.Numeric(18, 2), nullable=True),
            sa.Column("net_revenue", sa.Numeric(18, 2), nullable=True),
            sa.Column("total_quantity", sa.Integer(), nullable=True),
            sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_repeat_customer", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("notes", sa.Text(), nullable=True),
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
        op.create_index("ix_orders_upload_id", "orders", ["upload_id"])
        op.create_index("ix_orders_external_id", "orders", ["external_order_id"])
        op.create_index("ix_orders_order_date", "orders", ["order_date"])
        op.create_index("ix_orders_source_name", "orders", ["source_name"])
        op.create_index("ix_orders_customer_id", "orders", ["customer_id"])

    # order_items
    if not _table_exists("order_items"):
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "order_id",
                sa.Integer(),
                sa.ForeignKey("orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sku", sa.String(length=128), nullable=True),
            sa.Column("product_name", sa.String(length=512), nullable=True),
            sa.Column("variant_name", sa.String(length=255), nullable=True),
            sa.Column("vendor", sa.String(length=255), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(18, 2), nullable=True),
            sa.Column("line_discount_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("line_total", sa.Numeric(18, 2), nullable=True),
            sa.Column("net_line_revenue", sa.Numeric(18, 2), nullable=True),
            sa.Column("requires_shipping", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("raw_notes", sa.Text(), nullable=True),
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
        op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
        op.create_index("ix_order_items_sku", "order_items", ["sku"])
        op.create_index("ix_order_items_product_name", "order_items", ["product_name"])

    # raw_orders (audit)
    if not _table_exists("raw_orders"):
        op.create_table(
            "raw_orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "upload_id",
                sa.Integer(),
                sa.ForeignKey("uploads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("row_index", sa.Integer(), nullable=False),
            sa.Column("raw_payload", mysql.JSON(), nullable=False),
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
        op.create_index("ix_raw_orders_upload_row", "raw_orders", ["upload_id", "row_index"])

    # metric_snapshots
    if not _table_exists("metric_snapshots"):
        op.create_table(
            "metric_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "upload_id",
                sa.Integer(),
                sa.ForeignKey("uploads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("metric_code", sa.String(length=128), nullable=False),
            sa.Column("metric_scope", sa.String(length=64), nullable=False, server_default="overall"),
            sa.Column("dimension_1", sa.String(length=256), nullable=True),
            sa.Column("dimension_2", sa.String(length=256), nullable=True),
            sa.Column("period_type", sa.String(length=32), nullable=False, server_default="all_time"),
            sa.Column("period_value", sa.String(length=64), nullable=True),
            sa.Column("metric_value", sa.Numeric(24, 8), nullable=False),
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
        op.create_index("ix_metric_snapshots_upload", "metric_snapshots", ["upload_id"])
        op.create_index("ix_metric_snapshots_code", "metric_snapshots", ["metric_code"])
        op.create_index("ix_metric_snapshots_scope", "metric_snapshots", ["metric_scope"])
        op.create_index(
            "ix_metric_snapshots_upload_code", "metric_snapshots", ["upload_id", "metric_code"]
        )

    # signal_events
    if not _table_exists("signal_events"):
        op.create_table(
            "signal_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "upload_id",
                sa.Integer(),
                sa.ForeignKey("uploads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("signal_code", sa.String(length=64), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
            sa.Column("entity_type", sa.String(length=32), nullable=False, server_default="unknown"),
            sa.Column("entity_key", sa.String(length=256), nullable=True),
            sa.Column("signal_value", sa.Numeric(24, 8), nullable=True),
            sa.Column("threshold_value", sa.Numeric(24, 8), nullable=True),
            sa.Column("signal_context_json", mysql.JSON(), nullable=True),
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
        op.create_index("ix_signal_events_upload", "signal_events", ["upload_id"])
        op.create_index("ix_signal_events_code", "signal_events", ["signal_code"])
        op.create_index("ix_signal_events_severity", "signal_events", ["severity"])

    # insights
    if not _table_exists("insights"):
        op.create_table(
            "insights",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "upload_id",
                sa.Integer(),
                sa.ForeignKey("uploads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("insight_code", sa.String(length=128), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False, server_default="general"),
            sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
            sa.Column("title", sa.String(length=512), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("implication_text", sa.Text(), nullable=True),
            sa.Column("recommended_action", sa.Text(), nullable=True),
            sa.Column("supporting_data_json", mysql.JSON(), nullable=True),
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
        op.create_index("ix_insights_upload", "insights", ["upload_id"])
        op.create_index("ix_insights_category", "insights", ["category"])
        op.create_index("ix_insights_priority", "insights", ["priority"])

    # rule_definitions (legacy-first, then extended by later migrations)
    if not _table_exists("rule_definitions"):
        op.create_table(
            "rule_definitions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("rule_id", sa.String(length=128), nullable=False),
            sa.Column("domain", sa.String(length=32), nullable=False),
            sa.Column("yaml_source_path", sa.String(length=512), nullable=False),
            sa.Column("definition_hash", sa.String(length=64), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("last_synced_at", sa.DateTime(timezone=False), nullable=True),
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
        op.create_index("ix_rule_definitions_rule_id", "rule_definitions", ["rule_id"], unique=True)
        op.create_index("ix_rule_definitions_domain", "rule_definitions", ["domain"])


def downgrade() -> None:
    # Additive-only policy: do not attempt to drop baseline tables automatically.
    pass

