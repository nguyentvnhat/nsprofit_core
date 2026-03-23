"""Run with: ``python -m pytest tests/test_file_parser.py`` from ``nosaprofit/``."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

# Allow ``python3 tests/test_file_parser.py`` (script dir is on path, not project root).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from app.services.file_parser import (
    ShopifyExportParseError,
    parse_shopify_csv,
    parse_shopify_csv_with_result,
    parse_shopify_orders_csv,
)


def test_parse_minimal_csv() -> None:
    csv = "Name,Email,Total\n#1001,a@b.com,10.00\n"
    res = parse_shopify_orders_csv(BytesIO(csv.encode()))
    assert len(res.rows) == 1
    assert res.rows[0]["Name"] == "#1001"


def test_parse_missing_name_column() -> None:
    csv = "Email,Total\na@b.com,10\n"
    with pytest.raises(ShopifyExportParseError):
        parse_shopify_orders_csv(BytesIO(csv.encode()))


def test_header_aliases_canonicalize() -> None:
    csv = (
        "name,email,line item quantity,line item name,total\n"
        "#1001,a@b.com,1,Widget,10.00\n"
    )
    res = parse_shopify_orders_csv(BytesIO(csv.encode()))
    assert "Lineitem quantity" in res.columns
    assert "Lineitem name" in res.columns
    assert res.rows[0]["Lineitem quantity"] == "1"
    assert res.rows[0]["Lineitem name"] == "Widget"


def test_empty_strings_become_none() -> None:
    csv = "Name,Email,Total\n#1001,,10\n"
    res = parse_shopify_orders_csv(BytesIO(csv.encode()))
    assert res.rows[0]["Email"] is None


def test_parse_shopify_csv_from_path(tmp_path: Path) -> None:
    p = tmp_path / "orders.csv"
    p.write_text("Name,Total\n#1,5.00\n", encoding="utf-8")
    rows = parse_shopify_csv(p, chunksize=10_000)
    assert len(rows) == 1
    assert rows[0]["Name"] == "#1"
    out = parse_shopify_csv_with_result(p, chunksize=0)
    assert out.columns == ["Name", "Total"]
    assert isinstance(out.warnings, list)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
