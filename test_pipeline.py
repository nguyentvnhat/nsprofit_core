"""Smoke-test parser + normalizer on `orders_export.csv` in this folder."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.file_parser import parse_shopify_orders_csv
from app.services.shopify_normalizer import normalize_shopify_data

file_path = _ROOT / "orders_export.csv"

if not file_path.is_file():
    print(f"Missing {file_path.name} — place a Shopify orders export next to this script.", file=sys.stderr)
    sys.exit(1)

with file_path.open("rb") as f:
    parsed = parse_shopify_orders_csv(f)

orders_d, items_d, customers_d = normalize_shopify_data(parsed.rows)

print(f"Rows: {len(parsed.rows)}")
if parsed.warnings:
    print("Parse warnings:", parsed.warnings)
print(f"Orders: {len(orders_d)}")
print(f"Line items: {len(items_d)}")
print(f"Customers (deduped): {len(customers_d)}")
