"""End-to-end ingestion and analytics pipeline (UI and future API call this)."""

from __future__ import annotations

import logging
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
from app.services.campaign_extractor import campaign_dims_to_notes_payload
from app.services.shopify_normalizer import normalize_shopify_data
from app.services.signal_engine import run_all_signals, signal_codes
from app.services.signal_engine.types import Signal

logger = logging.getLogger(__name__)


def _priority_for_severity(severity: str) -> str:
    s = (severity or "").strip().lower()
    if s in {"high", "critical", "warning"}:
        return "high"
    if s in {"medium", "moderate"}:
        return "medium"
    return "low"


def _signal_event_from_draft(upload_id: int, d: Signal) -> SignalEvent:
    p = dict(d.get("context", {}) or {})
    sig_val = Decimal(str(d.get("signal_value", 0)))
    thr = Decimal(str(d.get("threshold_value", 0)))
    return SignalEvent(
        upload_id=upload_id,
        signal_code=str(d["signal_code"]),
        severity=str(d["severity"]),
        entity_type=str(d["entity_type"]),
        entity_key=d.get("entity_key"),
        signal_value=sig_val,
        threshold_value=thr,
        signal_context_json=p or None,
    )


def process_shopify_csv(
    session: Session,
    *,
    file_bytes: bytes,
    filename: str,
    merchant_id: int | None = None,
) -> int:
    """
    Parse → raw rows → normalize → persist → metrics → signals → rules → narratives.
    Returns `upload_id`.

    :param merchant_id: Optional portal merchant FK (NosaProfit core) for upload attribution.
    """
    upload_repo = UploadRepository(session)
    order_repo = OrderRepository(session)
    metric_repo = MetricRepository(session)
    signal_repo = SignalRepository(session)
    insight_repo = InsightRepository(session)

    upload = upload_repo.create(
        file_name=filename,
        file_type="csv",
        source_type="shopify_csv",
        merchant_id=merchant_id,
    )
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
                notes=campaign_dims_to_notes_payload(od),
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
        logger.debug(
            "Metrics computed for upload_id=%s domains=%s",
            upload.id,
            sorted(metrics.keys()),
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

        drafts = run_all_signals(metrics)
        logger.debug("Signals computed for upload_id=%s count=%s", upload.id, len(drafts))
        events = [_signal_event_from_draft(upload.id, d) for d in drafts]
        signal_repo.replace_for_upload(upload.id, events)

        payloads = evaluate_rules(metric_map, drafts)
        narrated = narrate_all(payloads)
        logger.debug(
            "Rules/insights generated for upload_id=%s rules=%s insights=%s",
            upload.id,
            len(payloads),
            len(narrated),
        )
        insights = [
            Insight(
                upload_id=upload.id,
                insight_code=n.rule_code,
                category=n.category,
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

        try:
            sync_rule_definitions(session)
        except Exception:
            # Keep ingestion resilient for legacy DBs where rule_definitions schema differs.
            pass
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
