"""Product concentration and catalog risk signals."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.services.signal_engine.types import SignalDraft

DEFAULT_TOP_SKU_SHARE_WARN = 0.55


def collect(
    session: Session,
    upload_id: int,
    metric_map: dict[str, float],
) -> Sequence[SignalDraft]:
    _ = session, upload_id
    share = float(metric_map.get("top_sku_quantity_share", 0.0))
    if share >= DEFAULT_TOP_SKU_SHARE_WARN:
        return [
            SignalDraft(
                domain="product",
                code="SKU_QUANTITY_CONCENTRATION",
                severity="info",
                payload={"top_sku_quantity_share": share, "threshold": DEFAULT_TOP_SKU_SHARE_WARN},
            )
        ]
    return []
