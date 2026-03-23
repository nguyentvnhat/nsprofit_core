"""Transform raw Shopify CSV rows into order / line-item / customer shapes."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.utils.dates import parse_shopify_datetime
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
    processed_at: object | None  # datetime | None — avoid circular imports
    customer: NormalizedCustomer | None
    lines: list[NormalizedLineItem] = field(default_factory=list)


def _first(row: dict) -> dict:
    return row


def _get(row: dict, *keys: str) -> object | None:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def normalize_shopify_rows(rows: list[dict]) -> list[NormalizedOrder]:
    """
    Group CSV rows by Shopify order `Name` and build normalized aggregates.

    Monetary fields are taken from the first row of each group (Shopify repeats them).
    Line items are collected from every row that carries line-level fields.
    """
    keyed = [r for r in rows if r.get("Name")]
    groups = group_by(keyed, key=lambda r: str(r["Name"]).strip())

    out: list[NormalizedOrder] = []
    for name, grp in groups.items():
        header = _first(grp[0])
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
