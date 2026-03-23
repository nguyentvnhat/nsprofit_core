"""End-to-end ingestion and analytics pipeline (UI and future API call this)."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models.insight import Insight
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.signal_event import SignalEvent
from app.repositories import (
    InsightRepository,
    MetricRepository,
    OrderRepository,
    SignalRepository,
    UploadRepository,
)
from app.services.file_parser import ShopifyExportParseError, parse_shopify_orders_csv
from app.services.metrics_engine import metrics_as_flat_dict, run_all_metrics
from app.services.narrative_engine import narrate_all
from app.services.rules_engine import evaluate_rules, sync_rule_definitions
from app.services.shopify_normalizer import normalize_shopify_rows
from app.services.signal_engine import run_all_signals, signal_codes
from app.utils.dates import to_naive_utc


def process_shopify_csv(
    session: Session,
    *,
    file_bytes: bytes,
    filename: str,
) -> int:
    """
    Parse → raw rows → normalize → persist → metrics → signals → rules → narratives.
    Returns `upload_id`.
    """
    upload_repo = UploadRepository(session)
    order_repo = OrderRepository(session)
    metric_repo = MetricRepository(session)
    signal_repo = SignalRepository(session)
    insight_repo = InsightRepository(session)

    digest = hashlib.sha256(file_bytes).hexdigest()
    upload = upload_repo.create(filename=filename, file_hash=digest)
    upload_repo.update_status(upload, "processing")

    try:
        parse_result = parse_shopify_orders_csv(BytesIO(file_bytes))
        order_repo.add_raw_rows(upload.id, parse_result.rows)
        upload.extra = {"parse_warnings": parse_result.warnings, "columns": parse_result.columns}
        normalized = normalize_shopify_rows(parse_result.rows)

        for n in normalized:
            cust = None
            if n.customer:
                cust = order_repo.upsert_customer(
                    email=n.customer.email,
                    external_id=n.customer.external_id,
                    first_name=n.customer.first_name,
                    last_name=n.customer.last_name,
                )
            order = Order(
                upload_id=upload.id,
                customer_id=cust.id if cust else None,
                external_name=n.external_name,
                financial_status=n.financial_status,
                fulfillment_status=n.fulfillment_status,
                currency=n.currency,
                subtotal_amount=n.subtotal_amount,
                discount_amount=n.discount_amount,
                shipping_amount=n.shipping_amount,
                tax_amount=n.tax_amount,
                refund_amount=n.refund_amount,
                total_amount=n.total_amount,
                net_revenue=n.net_revenue,
                total_quantity=n.total_quantity,
                source_name=n.source_name,
                processed_at=to_naive_utc(n.processed_at),  # type: ignore[arg-type]
            )
            order_repo.add_order(order)
            items = [
                OrderItem(
                    order_id=order.id,
                    sku=li.sku,
                    title=li.title,
                    quantity=li.quantity,
                    unit_price=li.unit_price,
                    line_total=li.line_total,
                    variant_title=li.variant_title,
                )
                for li in n.lines
            ]
            order_repo.add_order_items(items)

        metric_result = run_all_metrics(session, upload.id)
        metric_repo.replace_for_upload(upload.id, list(metric_result.snapshots))
        metric_map = metrics_as_flat_dict(metric_result.snapshots)

        drafts = run_all_signals(session, upload.id, metric_map)
        events = [
            SignalEvent(
                upload_id=upload.id,
                domain=d.domain,
                code=d.code,
                severity=d.severity,
                payload=d.payload,
            )
            for d in drafts
        ]
        signal_repo.replace_for_upload(upload.id, events)

        codes = signal_codes(drafts)
        payloads = evaluate_rules(metric_map, codes)
        narrated = narrate_all(payloads)
        insights = [
            Insight(
                upload_id=upload.id,
                rule_id=n.rule_id,
                title=n.title,
                summary=n.summary,
                implication=n.implication,
                action=n.action,
                severity=n.severity,
                payload_json=n.payload_json,
            )
            for n in narrated
        ]
        insight_repo.replace_for_upload(upload.id, insights)

        sync_rule_definitions(session)
        upload_repo.update_status(upload, "completed", row_count=len(parse_result.rows))
    except ShopifyExportParseError as exc:
        upload_repo.update_status(upload, "failed", error_message=str(exc))
        raise
    except Exception as exc:  # noqa: BLE001 — pipeline boundary
        upload_repo.update_status(upload, "failed", error_message=str(exc))
        raise

    return upload.id


def process_shopify_csv_stream(session: Session, file_obj: BinaryIO, filename: str) -> int:
    data = file_obj.read()
    return process_shopify_csv(session, file_bytes=data, filename=filename)
