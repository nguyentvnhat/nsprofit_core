"""Shopify order CSV ingestion and structural validation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

import pandas as pd


# Shopify "Orders" export — core columns (names vary slightly by locale; extend mappings later).
REQUIRED_COLUMNS = ("Name",)

LINE_ITEM_MARKERS = (
    "Lineitem quantity",
    "Lineitem name",
    "Lineitem price",
    "Lineitem sku",
)


@dataclass
class ParseResult:
    rows: list[dict[str, str | float | int | None]]
    columns: list[str]
    warnings: list[str]


class ShopifyExportParseError(Exception):
    """Raised when CSV structure is not compatible with the Shopify orders export."""


def _normalize_column_name(name: str) -> str:
    return str(name).strip()


def parse_shopify_orders_csv(
    file_obj: BinaryIO,
    *,
    encoding: str = "utf-8",
) -> ParseResult:
    """
    Read a Shopify orders CSV into row dicts (JSON-serializable friendly).
    Validates presence of minimum columns; warns if line item columns missing.
    """
    raw = file_obj.read()
    buffer = BytesIO(raw)
    try:
        df = pd.read_csv(buffer, dtype=str, encoding=encoding, keep_default_na=False)
    except Exception as exc:  # noqa: BLE001 — surface as parse error
        raise ShopifyExportParseError(f"Could not read CSV: {exc}") from exc

    df.columns = [_normalize_column_name(c) for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ShopifyExportParseError(f"Missing required column(s): {missing}")

    warnings: list[str] = []
    if not any(m in df.columns for m in LINE_ITEM_MARKERS):
        warnings.append(
            "No line item columns detected; normalization will produce empty line items."
        )

    # Replace empty strings with None for cleaner downstream handling
    def clean_cell(v: object) -> str | float | int | None:
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v  # type: ignore[return-value]

    rows: list[dict[str, str | float | int | None]] = []
    for record in df.to_dict(orient="records"):
        rows.append({str(k): clean_cell(v) for k, v in record.items()})

    return ParseResult(rows=rows, columns=list(df.columns), warnings=warnings)
