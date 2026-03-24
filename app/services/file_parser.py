"""
Shopify order export CSV ingestion.

- One row per line item; order-level fields repeat across rows.
- Headers are canonicalized for `shopify_normalizer` (spacing/casing/alias variants).
- Path parsing uses chunked reads for large files; uploads use in-memory parse.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from io import BytesIO
from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ShopifyExportParseError(Exception):
    """File missing, unreadable, or not a compatible Shopify orders export."""


@dataclass
class ParseResult:
    rows: list[dict[str, Any]]
    columns: list[str]
    warnings: list[str] = field(default_factory=list)


REQUIRED_CANONICAL_COLUMNS: tuple[str, ...] = ("Name",)

LINE_ITEM_MARKERS: tuple[str, ...] = (
    "Lineitem quantity",
    "Lineitem name",
    "Lineitem price",
    "Lineitem sku",
)

_DEFAULT_CHUNKSIZE = 100_000
_SNIFF_BYTES = 256_000


# ---------------------------------------------------------------------------
# Header aliases → canonical names (used by shopify_normalizer._get)
# ---------------------------------------------------------------------------


def _norm_key(name: str) -> str:
    s = str(name).strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", s)


HEADER_ALIASES: dict[str, str] = {
    "name": "Name",
    "order name": "Name",
    "order": "Name",
    "lineitem quantity": "Lineitem quantity",
    "line item quantity": "Lineitem quantity",
    "lineitem name": "Lineitem name",
    "line item name": "Lineitem name",
    "lineitem price": "Lineitem price",
    "line item price": "Lineitem price",
    "lineitem sku": "Lineitem sku",
    "line item sku": "Lineitem sku",
    "lineitem variant": "Lineitem variant",
    "line item variant": "Lineitem variant",
    "lineitem vendor": "Lineitem vendor",
    "line item vendor": "Lineitem vendor",
    "lineitem compare at price": "Lineitem compare at price",
    "line item compare at price": "Lineitem compare at price",
    "compare at price": "Lineitem compare at price",
    "subtotal": "Subtotal",
    "discount amount": "Discount Amount",
    "discount": "Discount Amount",
    "shipping": "Shipping",
    "shipping charged": "Shipping Charged",
    "taxes": "Taxes",
    "tax 1 value": "Tax 1 Value",
    "total": "Total",
    "refunded amount": "Refunded Amount",
    "refund amount": "Refund Amount",
    "total refunded": "Total Refunded",
    "financial status": "Financial Status",
    "fulfillment status": "Fulfillment Status",
    "currency": "Currency",
    "email": "Email",
    "customer email": "Email",
    "created at": "Created at",
    "paid at": "Paid at",
    "source": "Source",
    "utm campaign": "UTM Campaign",
    "utm medium": "UTM Medium",
    "utm source": "UTM Source",
    "landing site": "Landing Site",
    "landing page": "Landing Site",
    "referring site": "Referring Site",
    "referrer": "Referring Site",
    "discount code": "Discount Code",
    "discount codes": "Discount Codes",
    "id": "Id",
    "customer id": "Customer ID",
    "billing first name": "Billing First Name",
    "billing last name": "Billing Last Name",
    "shipping country": "Shipping Country",
    "billing country": "Billing Country",
}


def _strip_header(name: str) -> str:
    return str(name).strip()


def _dedupe_raw_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if df.columns.duplicated().any():
        n = int(df.columns.duplicated().sum())
        warnings.append(f"Source had {n} duplicate column label(s); kept first occurrence of each.")
        df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df, warnings


def _apply_canonical_headers(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Rename each column to its canonical Shopify header; drop columns that would duplicate
    a canonical name already taken (first wins).
    """
    warnings: list[str] = []
    df, w = _dedupe_raw_columns(df)
    warnings.extend(w)

    keep_cols: list[str] = []
    new_names: list[str] = []
    seen_canonical: set[str] = set()

    for col in df.columns:
        raw = _strip_header(str(col))
        canonical = HEADER_ALIASES.get(_norm_key(raw), raw)
        if canonical in seen_canonical:
            warnings.append(
                f"Dropped column {raw!r}: maps to {canonical!r} which is already present (first wins)."
            )
            continue
        seen_canonical.add(canonical)
        keep_cols.append(str(col))
        new_names.append(canonical)

    df = df[keep_cols].copy()
    df.columns = new_names
    return df, warnings


def _clean_cell(v: object) -> str | float | int | None:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        return None if s == "" else s
    return v  # type: ignore[return-value]


def _dataframe_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): _clean_cell(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _validate_required(columns: list[str]) -> None:
    missing = [c for c in REQUIRED_CANONICAL_COLUMNS if c not in columns]
    if missing:
        raise ShopifyExportParseError(
            f"Missing required column(s): {missing}. "
            f"Sample columns: {columns[:30]}{'...' if len(columns) > 30 else ''}"
        )


def _line_item_warning(columns: list[str]) -> str | None:
    if not any(m in columns for m in LINE_ITEM_MARKERS):
        return (
            "No line item columns detected after canonicalization; "
            "normalization will produce empty line items."
        )
    return None


def _sniff_bytes_encoding(sample: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            sample.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _detect_file_encoding(path: Path) -> str:
    try:
        raw = path.read_bytes()[:_SNIFF_BYTES]
    except OSError as exc:
        raise ShopifyExportParseError(f"Cannot read file: {path}") from exc
    return _sniff_bytes_encoding(raw)


def _pandas_read_csv_kwargs(encoding: str) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "dtype": str,
        "encoding": encoding,
        "keep_default_na": False,
        "low_memory": False,
    }
    if "on_bad_lines" in inspect.signature(pd.read_csv).parameters:
        kw["on_bad_lines"] = "warn"
    return kw


def _parse_dataframe(df: pd.DataFrame) -> ParseResult:
    if df.empty:
        raise ShopifyExportParseError("CSV contains no data rows.")

    df, warnings = _apply_canonical_headers(df)
    cols = list(df.columns)
    _validate_required(cols)
    li = _line_item_warning(cols)
    if li:
        warnings.append(li)

    return ParseResult(rows=_dataframe_to_rows(df), columns=cols, warnings=warnings)


def _read_csv_buffer(buffer: BinaryIO, *, encoding: str) -> pd.DataFrame:
    kw = _pandas_read_csv_kwargs(encoding)
    try:
        return pd.read_csv(buffer, **kw)
    except pd.errors.EmptyDataError as exc:
        raise ShopifyExportParseError("CSV is empty or has no parseable rows.") from exc
    except Exception as exc:
        raise ShopifyExportParseError(f"Could not read CSV: {exc}") from exc


def _read_csv_path(
    path: Path, *, encoding: str, chunksize: int | None
) -> pd.DataFrame | Iterable[pd.DataFrame]:
    kw = _pandas_read_csv_kwargs(encoding)
    try:
        if chunksize and chunksize > 0:
            return pd.read_csv(path, chunksize=chunksize, **kw)
        return pd.read_csv(path, **kw)
    except pd.errors.EmptyDataError as exc:
        raise ShopifyExportParseError("CSV is empty or has no parseable rows.") from exc
    except Exception as exc:
        raise ShopifyExportParseError(f"Could not read CSV: {exc}") from exc


def _parse_chunked(reader: Iterable[pd.DataFrame]) -> ParseResult:
    all_rows: list[dict[str, Any]] = []
    columns_ref: list[str] | None = None
    warnings: list[str] = []
    first = True

    for chunk in reader:
        if chunk.empty:
            continue
        if first:
            parsed = _parse_dataframe(chunk)
            columns_ref = parsed.columns
            warnings = list(parsed.warnings)
            all_rows.extend(parsed.rows)
            first = False
            continue

        df, chunk_warnings = _apply_canonical_headers(chunk)
        if list(df.columns) != columns_ref:
            raise ShopifyExportParseError(
                "Column layout changed mid-file; refuse to merge chunks. "
                f"Expected {columns_ref!r}, got {list(df.columns)!r}."
            )
        if chunk_warnings:
            warnings.extend(chunk_warnings)
        all_rows.extend(_dataframe_to_rows(df))

    if first:
        raise ShopifyExportParseError("CSV contains no data rows.")

    assert columns_ref is not None
    return ParseResult(rows=all_rows, columns=columns_ref, warnings=warnings)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def parse_shopify_csv(
    file_path: str | Path,
    *,
    chunksize: int = _DEFAULT_CHUNKSIZE,
    encoding: str | None = None,
) -> list[dict[str, Any]]:
    """
    Parse a Shopify orders export from disk.

    Returns row dicts with canonical headers for ``normalize_shopify_rows``.
    Uses chunked reads (default 100k rows) to bound memory on large exports.
    """
    path = Path(file_path)
    if not path.is_file():
        raise ShopifyExportParseError(f"File not found: {path}")

    enc = encoding or _detect_file_encoding(path)
    data = _read_csv_path(path, encoding=enc, chunksize=chunksize)

    if isinstance(data, pd.DataFrame):
        result = _parse_dataframe(data)
    else:
        result = _parse_chunked(data)

    return result.rows


def parse_shopify_csv_with_result(
    file_path: str | Path,
    *,
    chunksize: int = _DEFAULT_CHUNKSIZE,
    encoding: str | None = None,
) -> ParseResult:
    """Like ``parse_shopify_csv`` but returns columns and warnings."""
    path = Path(file_path)
    if not path.is_file():
        raise ShopifyExportParseError(f"File not found: {path}")
    enc = encoding or _detect_file_encoding(path)
    data = _read_csv_path(path, encoding=enc, chunksize=chunksize)
    if isinstance(data, pd.DataFrame):
        return _parse_dataframe(data)
    return _parse_chunked(data)


def parse_shopify_orders_csv(
    file_obj: BinaryIO,
    *,
    encoding: str | None = None,
) -> ParseResult:
    """
    Parse from a binary stream (e.g. uploaded file bytes).

    Whole buffer is read once (pipeline already holds bytes in memory).
    Encoding: explicit ``encoding``, else sniffed from a prefix of the buffer.
    """
    raw = file_obj.read()
    if not raw:
        raise ShopifyExportParseError("Empty file.")

    enc = encoding or _sniff_bytes_encoding(raw[:_SNIFF_BYTES])
    df = _read_csv_buffer(BytesIO(raw), encoding=enc)
    return _parse_dataframe(df)
