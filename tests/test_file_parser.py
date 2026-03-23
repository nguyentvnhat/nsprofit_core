from io import BytesIO

import pytest

from app.services.file_parser import (
    ShopifyExportParseError,
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
