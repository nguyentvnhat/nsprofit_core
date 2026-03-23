"""End-to-end ingestion and analytics pipeline (UI and future API call this)."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
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
from app.services.signal_engine.types import SignalDraft
from app.utils.dates import to_naive_utc


def _dec(x: float | None) -> Decimal | None:
    if x is None:
        return None
    return Decimal(str(x))


def _priority_for_severity(severity: str) -> str:
    return "high" if severity == "warning" else "normal"


def _signal_event_from_draft(upload_id: int, d: SignalDraft) -> SignalEvent:
    p = dict(d.payload or {})
    sig_val: Decimal | None = None
    thr: Decimal | None = None
    for key in (
        "discount_to_gross_ratio",
        "refund_to_gross_ratio",
        "top_sku_quantity_share",
        "repeat_customer_ratio",
        "zero_shipping_order_share",
    ):
        if key in p:
            sig_val = Decimal(str(p[key]))
            break
    if "threshold" in p:
        thr = Decimal(str(p["threshold"]))
    return SignalEvent(
        upload_id=upload_id,
        signal_code=d.code,
        severity=d.severity,
        entity_type=d.domain,
        entity_key=None,
        signal_value=sig_val,
        threshold_value=thr,
        signal_context_json=p or None,
    )


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

    upload = upload_repo.create(file_name=filename, file_type="csv", source_type="shopify_csv")
    upload_repo.update_status(upload, "processing")

    try:
        parse_result = parse_shopify_orders_csv(BytesIO(file_bytes))
        order_repo.add_raw_rows(upload.id, parse_result.rows)
        normalized = normalize_shopify_rows(parse_result.rows)

        email_counts: Counter[str] = Counter()
        for n in normalized:
            if n.customer and n.customer.email:
                email_counts[n.customer.email] += 1

        for n in normalized:
            cust = None
            order_date = to_naive_utc(n.processed_at)
            net = _dec(n.net_revenue)
            if n.customer:
                parts = [n.customer.first_name, n.customer.last_name]
                display_name = " ".join(p for p in parts if p) or None
                cust = order_repo.upsert_customer_for_order(
                    email=n.customer.email,
                    display_name=display_name,
                    order_date=order_date,
                    net_revenue=net,
                )
            fin = (n.financial_status or "").lower()
            is_cancelled = "cancel" in fin or fin in ("voided", "refunded")
            is_repeat = bool(n.customer and n.customer.email and email_counts[n.customer.email] > 1)

            order = Order(
                upload_id=upload.id,
                external_order_id=n.shopify_order_id or None,
                order_name=n.external_name,
                order_date=order_date,
                currency=n.currency,
                financial_status=n.financial_status,
                fulfillment_status=n.fulfillment_status,
                source_name=n.source_name,
                customer_id=cust.id if cust else None,
                shipping_country=n.shipping_country,
                subtotal_price=_dec(n.subtotal_amount),
                discount_amount=_dec(n.discount_amount),
                shipping_amount=_dec(n.shipping_amount),
                tax_amount=_dec(n.tax_amount),
                refunded_amount=_dec(n.refund_amount),
                total_price=_dec(n.total_amount),
                net_revenue=net,
                total_quantity=n.total_quantity,
                is_cancelled=is_cancelled,
                is_repeat_customer=is_repeat,
            )
            order_repo.add_order(order)
            items = [
                OrderItem(
                    order_id=order.id,
                    sku=li.sku,
                    product_name=li.title,
                    variant_name=li.variant_title,
                    vendor=li.vendor,
                    quantity=li.quantity,
                    unit_price=_dec(li.unit_price),
                    line_discount_amount=None,
                    line_total=_dec(li.line_total),
                    net_line_revenue=_dec(li.line_total),
                    requires_shipping=True,
                )
                for li in n.lines
            ]
            order_repo.add_order_items(items)

        metric_result = run_all_metrics(session, upload.id)
        metric_repo.replace_for_upload(upload.id, list(metric_result.snapshots))
        metric_map = metrics_as_flat_dict(metric_result.snapshots)

        drafts = run_all_signals(session, upload.id, metric_map)
        events = [_signal_event_from_draft(upload.id, d) for d in drafts]
        signal_repo.replace_for_upload(upload.id, events)

        codes = signal_codes(drafts)
        payloads = evaluate_rules(metric_map, codes)
        narrated = narrate_all(payloads)
        insights = [
            Insight(
                upload_id=upload.id,
                insight_code=n.rule_id,
                category=n.domain,
                priority=_priority_for_severity(n.severity),
                title=n.title,
                summary=n.summary,
                implication_text=n.implication or None,
                recommended_action=n.action or None,
                supporting_data_json=n.payload_json,
            )
            for n in narrated
        ]
        insight_repo.replace_for_upload(upload.id, insights)

        sync_rule_definitions(session)
        upload_repo.update_status(upload, "processed", row_count=len(parse_result.rows))
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
