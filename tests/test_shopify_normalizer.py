"""Normalization: grouped orders, line items, customers."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.shopify_normalizer import normalize_shopify_data, normalize_shopify_rows


def test_normalize_shopify_data_shape() -> None:
    rows = [
        {
            "Name": "#A1",
            "Email": "u@example.com",
            "Total": "20",
            "Lineitem quantity": "2",
            "Lineitem name": "Hat",
            "Lineitem price": "10",
            "Billing First Name": "U",
            "Billing Last Name": "Ser",
        },
        {
            "Name": "#A1",
            "Email": "u@example.com",
            "Total": "20",
            "Lineitem quantity": "1",
            "Lineitem name": "Sock",
            "Lineitem price": "5",
        },
    ]
    orders, items, customers = normalize_shopify_data(rows)
    assert len(orders) == 1
    assert orders[0]["order_name"] == "#A1"
    assert orders[0]["customer_email"] == "u@example.com"
    assert orders[0]["net_revenue"] == Decimal("20")
    assert len(items) == 2
    assert all(it["order_name"] == "#A1" for it in items)
    assert len(customers) == 1
    assert customers[0]["email"] == "u@example.com"
    assert customers[0]["name"] == "U Ser"


def test_normalize_shopify_rows_backward_compat() -> None:
    rows = [{"Name": "#1", "Total": "5", "Lineitem quantity": "1", "Lineitem name": "X", "Lineitem price": "5"}]
    norm = normalize_shopify_rows(rows)
    assert len(norm) == 1
    assert norm[0].external_name == "#1"
    assert len(norm[0].lines) == 1
