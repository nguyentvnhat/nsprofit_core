"""
Transform raw Shopify CSV rows (from ``parse_shopify_csv`` / ``parse_shopify_orders_csv``)
into structured entities for persistence.

- Each source row = one line item; rows are grouped by order ``Name``.
- Outputs ORM-aligned dicts: ``orders``, ``order_items`` (linked by ``order_name``),
  and deduplicated ``customers``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.utils.dates import parse_shopify_datetime, to_naive_utc
from app.utils.grouping import group_by
from app.utils.money import to_float
from app.utils.validators import is_plausible_email


@dataclass
class NormalizedCustomer:
    email: str | None = None
    external_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass
class NormalizedLineItem:
    sku: str | None
    title: str | None
    quantity: int
    unit_price: float | None
    line_total: float | None
    compare_at_price: float | None = None
    variant_title: str | None = None
    vendor: str | None = None


@dataclass
class NormalizedOrder:
    external_name: str
    shopify_order_id: str | None
    shipping_country: str | None
    financial_status: str | None
    fulfillment_status: str | None
    currency: str | None
    subtotal_amount: float | None
    discount_amount: float | None
    shipping_amount: float | None
    tax_amount: float | None
    refund_amount: float | None
    total_amount: float | None
    net_revenue: float | None
    total_quantity: int
    source_name: str | None
    processed_at: object | None
    customer: NormalizedCustomer | None
    lines: list[NormalizedLineItem] = field(default_factory=list)


def _get(row: dict[str, Any], *keys: str) -> object | None:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _to_decimal(x: float | None) -> Decimal | None:
    if x is None:
        return None
    return Decimal(str(x))


def _customer_display_name(c: NormalizedCustomer | None) -> str | None:
    if not c:
        return None
    parts = [p for p in (c.first_name, c.last_name) if p]
    return " ".join(parts) if parts else None


def normalize_shopify_rows(rows: list[dict[str, Any]]) -> list[NormalizedOrder]:
    """
    Group CSV rows by Shopify order ``Name`` and build in-memory aggregates.

    Monetary fields are taken from the first row of each group (Shopify repeats them).
    Line items are collected from every row that carries line-level fields.
    """
    keyed = [r for r in rows if r.get("Name")]
    groups = group_by(keyed, key=lambda r: str(r["Name"]).strip())

    out: list[NormalizedOrder] = []
    for name, grp in groups.items():
        header = grp[0]
        subtotal = to_float(_get(header, "Subtotal"))
        discount = to_float(_get(header, "Discount Amount", "Discount Amount "))
        shipping = to_float(_get(header, "Shipping", "Shipping Charged"))
        tax = to_float(_get(header, "Taxes", "Tax 1 Value"))
        total = to_float(_get(header, "Total"))
        refund = to_float(
            _get(
                header,
                "Refunded Amount",
                "Refund Amount",
                "Total Refunded",
            )
        )
        total_qty = 0
        lines: list[NormalizedLineItem] = []
        for r in grp:
            qty_raw = _get(r, "Lineitem quantity", "LineItem quantity")
            try:
                qty = int(float(str(qty_raw))) if qty_raw not in (None, "") else 0
            except (ValueError, TypeError):
                qty = 0
            title = _get(r, "Lineitem name", "LineItem name")
            sku = _get(r, "Lineitem sku", "LineItem sku")
            unit_price = to_float(_get(r, "Lineitem price", "LineItem price"))
            compare_at = to_float(
                _get(
                    r,
                    "Lineitem compare at price",
                    "Line item compare at price",
                    "Compare at price",
                )
            )
            variant = _get(r, "Lineitem variant", "LineItem variant")
            vend = _get(r, "Lineitem vendor", "LineItem vendor")
            if qty == 0 and not title and not sku:
                continue
            line_total = None
            if unit_price is not None:
                line_total = unit_price * max(qty, 0)
            total_qty += max(qty, 0)
            lines.append(
                NormalizedLineItem(
                    sku=str(sku).strip() if sku else None,
                    title=str(title).strip() if title else None,
                    quantity=max(qty, 0),
                    unit_price=unit_price,
                    compare_at_price=compare_at,
                    line_total=line_total,
                    variant_title=str(variant).strip() if variant else None,
                    vendor=str(vend).strip() if vend else None,
                )
            )

        if total_qty == 0 and lines:
            total_qty = sum(li.quantity for li in lines)

        net = None
        if total is not None:
            net = total - (refund or 0.0)

        email = _get(header, "Email")
        email_str = str(email).strip() if email else None
        if email_str and not is_plausible_email(email_str):
            email_str = None

        cust = None
        cid = _get(header, "Customer ID", "Id")
        if email_str or cid:
            ext = str(cid).strip() if cid not in (None, "") else None
            cust = NormalizedCustomer(
                email=email_str,
                external_id=ext,
                first_name=str(_get(header, "Billing First Name")).strip()
                if _get(header, "Billing First Name")
                else None,
                last_name=str(_get(header, "Billing Last Name")).strip()
                if _get(header, "Billing Last Name")
                else None,
            )

        processed_at = parse_shopify_datetime(_get(header, "Created at", "Paid at"))
        oid = _get(header, "Id")
        shopify_order_id = str(oid).strip() if oid not in (None, "") else None
        ship_ctry = _get(header, "Shipping Country", "Billing Country")
        shipping_country = str(ship_ctry).strip() if ship_ctry else None

        out.append(
            NormalizedOrder(
                external_name=name,
                shopify_order_id=shopify_order_id,
                shipping_country=shipping_country,
                financial_status=str(_get(header, "Financial Status") or "").strip()
                or None,
                fulfillment_status=str(_get(header, "Fulfillment Status") or "").strip()
                or None,
                currency=str(_get(header, "Currency") or "").strip() or None,
                subtotal_amount=subtotal,
                discount_amount=discount,
                shipping_amount=shipping,
                tax_amount=tax,
                refund_amount=refund,
                total_amount=total,
                net_revenue=net,
                total_quantity=total_qty,
                source_name=str(_get(header, "Source") or "").strip() or None,
                processed_at=processed_at,
                customer=cust,
                lines=lines,
            )
        )

    return sorted(out, key=lambda o: (o.processed_at or o.external_name))


def _dedupe_customers(normalized: list[NormalizedOrder]) -> list[dict[str, Any]]:
    """One record per email (first non-empty name / external id wins when merging)."""
    seen: dict[str, dict[str, Any]] = {}
    for n in normalized:
        if not n.customer or not n.customer.email:
            continue
        e = n.customer.email
        name = _customer_display_name(n.customer)
        ext = n.customer.external_id
        if e not in seen:
            seen[e] = {
                "email": e,
                "name": name,
                "shopify_customer_id": ext,
            }
        else:
            if not seen[e].get("name") and name:
                seen[e]["name"] = name
            if not seen[e].get("shopify_customer_id") and ext:
                seen[e]["shopify_customer_id"] = ext
    return list(seen.values())


def _order_to_dict(
    n: NormalizedOrder,
    *,
    email_counts: Counter[str],
) -> dict[str, Any]:
    fin = (n.financial_status or "").lower()
    is_cancelled = "cancel" in fin or fin in ("voided", "refunded")
    email = n.customer.email if n.customer and n.customer.email else None
    is_repeat = bool(email and email_counts[email] > 1)
    pt = n.processed_at
    order_date: datetime | None = to_naive_utc(pt) if isinstance(pt, datetime) else None

    return {
        "order_name": n.external_name,
        "external_order_id": n.shopify_order_id,
        "order_date": order_date,
        "currency": n.currency,
        "financial_status": n.financial_status,
        "fulfillment_status": n.fulfillment_status,
        "source_name": n.source_name,
        "shipping_country": n.shipping_country,
        "subtotal_price": _to_decimal(n.subtotal_amount),
        "discount_amount": _to_decimal(n.discount_amount),
        "shipping_amount": _to_decimal(n.shipping_amount),
        "tax_amount": _to_decimal(n.tax_amount),
        "refunded_amount": _to_decimal(n.refund_amount),
        "total_price": _to_decimal(n.total_amount),
        "net_revenue": _to_decimal(n.net_revenue),
        "total_quantity": n.total_quantity,
        "is_cancelled": is_cancelled,
        "is_repeat_customer": is_repeat,
        "customer_email": email,
    }


def _line_to_dict(order_name: str, li: NormalizedLineItem) -> dict[str, Any]:
    lt = _to_decimal(li.line_total)
    return {
        "order_name": order_name,
        "sku": li.sku,
        "product_name": li.title,
        "variant_name": li.variant_title,
        "vendor": li.vendor,
        "quantity": li.quantity,
        "unit_price": _to_decimal(li.unit_price),
        "compare_at_price": _to_decimal(li.compare_at_price),
        "line_discount_amount": None,
        "line_total": lt,
        "net_line_revenue": lt,
        "requires_shipping": True,
    }


def normalize_shopify_data(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Build three structures ready for database insertion (excluding surrogate FKs).

    Returns
    -------
    orders
        One dict per order; keys match :class:`~app.models.order.Order` fields
        (except ``id``, ``upload_id``, ``customer_id``). Includes ``customer_email``
        for resolving the customer row at insert time.
    order_items
        One dict per line item; keys match :class:`~app.models.order_item.OrderItem`
        except ``id`` / ``order_id``. Each row has ``order_name`` equal to the parent
        order's ``order_name``.
    customers
        Deduplicated by ``email``; keys ``email``, ``name``, ``shopify_customer_id``
        (optional). Use with repository upsert before attaching orders.
    """
    normalized = normalize_shopify_rows(rows)
    email_counts: Counter[str] = Counter()
    for n in normalized:
        if n.customer and n.customer.email:
            email_counts[n.customer.email] += 1

    order_dicts = [_order_to_dict(n, email_counts=email_counts) for n in normalized]
    item_dicts: list[dict[str, Any]] = []
    for n in normalized:
        for li in n.lines:
            item_dicts.append(_line_to_dict(n.external_name, li))
    customer_dicts = _dedupe_customers(normalized)

    return order_dicts, item_dicts, customer_dicts
