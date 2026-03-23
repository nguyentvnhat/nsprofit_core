"""End-to-end ingestion and analytics pipeline (UI and future API call this)."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models.insight import Insight
from app.models.metric_snapshot import MetricSnapshot
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
from app.services.shopify_normalizer import normalize_shopify_data
from app.services.signal_engine import run_all_signals, signal_codes
from app.services.signal_engine.types import SignalDraft


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
        orders_data, items_data, customers_data = normalize_shopify_data(parse_result.rows)
        cust_by_email = {c["email"]: c for c in customers_data if c.get("email")}

        order_name_to_id: dict[str, int] = {}
        for od in orders_data:
            ce = od.get("customer_email")
            cust = None
            if ce:
                meta = cust_by_email.get(ce, {})
                cust = order_repo.upsert_customer_for_order(
                    email=ce,
                    display_name=meta.get("name"),
                    order_date=od["order_date"],
                    net_revenue=od["net_revenue"],
                )
            order = Order(
                upload_id=upload.id,
                customer_id=cust.id if cust else None,
                external_order_id=od["external_order_id"],
                order_name=od["order_name"],
                order_date=od["order_date"],
                currency=od["currency"],
                financial_status=od["financial_status"],
                fulfillment_status=od["fulfillment_status"],
                source_name=od["source_name"],
                shipping_country=od["shipping_country"],
                subtotal_price=od["subtotal_price"],
                discount_amount=od["discount_amount"],
                shipping_amount=od["shipping_amount"],
                tax_amount=od["tax_amount"],
                refunded_amount=od["refunded_amount"],
                total_price=od["total_price"],
                net_revenue=od["net_revenue"],
                total_quantity=od["total_quantity"],
                is_cancelled=od["is_cancelled"],
                is_repeat_customer=od["is_repeat_customer"],
            )
            order_repo.add_order(order)
            order_name_to_id[od["order_name"]] = order.id

        line_rows: list[OrderItem] = []
        for it in items_data:
            oid = order_name_to_id.get(it["order_name"])
            if oid is None:
                continue
            line_rows.append(
                OrderItem(
                    order_id=oid,
                    sku=it["sku"],
                    product_name=it["product_name"],
                    variant_name=it["variant_name"],
                    vendor=it["vendor"],
                    quantity=it["quantity"],
                    unit_price=it["unit_price"],
                    line_discount_amount=it["line_discount_amount"],
                    line_total=it["line_total"],
                    net_line_revenue=it["net_line_revenue"],
                    requires_shipping=it["requires_shipping"],
                )
            )
        order_repo.add_order_items(line_rows)

        metrics = run_all_metrics(
            orders=orders_data,
            order_items=items_data,
            customers=customers_data,
        )
        snapshots: list[MetricSnapshot] = []
        for scope, values in metrics.items():
            for code, value in values.items():
                if isinstance(value, (int, float, Decimal)):
                    snapshots.append(
                        MetricSnapshot(
                            upload_id=upload.id,
                            metric_code=code,
                            metric_scope=scope,
                            dimension_1=None,
                            dimension_2=None,
                            period_type="all_time",
                            period_value=None,
                            metric_value=Decimal(str(value)),
                        )
                    )
        metric_repo.replace_for_upload(upload.id, snapshots)
        metric_map = metrics_as_flat_dict(metrics)

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
