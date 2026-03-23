"""Smoke-test parser + normalizer on `orders_export.csv` in this folder."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.file_parser import parse_shopify_orders_csv
from app.services.shopify_normalizer import normalize_shopify_rows

file_path = _ROOT / "orders_export.csv"

if not file_path.is_file():
    print(f"Missing {file_path.name} — place a Shopify orders export next to this script.", file=sys.stderr)
    sys.exit(1)

with file_path.open("rb") as f:
    parsed = parse_shopify_orders_csv(f)

normalized = normalize_shopify_rows(parsed.rows)
item_count = sum(len(o.lines) for o in normalized)

print(f"Rows: {len(parsed.rows)}")
if parsed.warnings:
    print("Parse warnings:", parsed.warnings)
print(f"Orders: {len(normalized)}")
print(f"Line items: {item_count}")
