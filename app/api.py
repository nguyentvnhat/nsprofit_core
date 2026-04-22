"""
HTTP API for external clients (e.g. Laravel) to request discount recommendations.

Supports:
- **CSV upload** (legacy): multipart ``file`` → full ingestion + analytics (Streamlit parity).
- **upload_id**: existing demo import (no file).
- **store_id**: canonical store-scoped orders (optional date range).

Analytical layers (metrics → rules/signals/insights in DB → recommendations) stay separated in
service code; see :mod:`app.services.discount_recommendation_service`.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from datetime import date
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Path, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.dashboard_service import dashboard_data_to_jsonable, get_dashboard_data
from app.services.discount_recommendation_service import DiscountAnalysisError, run_discount_recommendation
from app.services.file_parser import ShopifyExportParseError
from app.services.pipeline import process_shopify_csv

from app.services.profit_configuration_service import (
    get_profit_configuration,
    create_profit_configuration,
    update_profit_configuration,
    delete_profit_configuration,
    set_default_configuration,
)

from app.models.profit_configuration import ProfitConfiguration

logger = logging.getLogger(__name__)

_FILE_LOG_CONFIGURED = False


def _configure_discount_file_log() -> None:
    """Optional file sink: set NOSAPROFIT_API_LOG_FILE to a writable path."""
    global _FILE_LOG_CONFIGURED
    if _FILE_LOG_CONFIGURED:
        return
    raw = (os.environ.get("NOSAPROFIT_API_LOG_FILE") or "").strip()
    if not raw:
        _FILE_LOG_CONFIGURED = True
        return
    path = pathlib.Path(raw).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            ),
        )
        logger.addHandler(fh)
        logger.setLevel(logging.DEBUG)
    except OSError as exc:
        logging.getLogger(__name__).warning("Could not open NOSAPROFIT_API_LOG_FILE %s: %s", path, exc)
    _FILE_LOG_CONFIGURED = True


_configure_discount_file_log()

app = FastAPI(title="NosaProfit API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard/{upload_id}")
def get_dashboard_json(
    upload_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    merchant_code: str | None = Query(None, description="Optional portal merchant code (for future ACL)"),
) -> dict[str, Any]:
    """
    Return serialized dashboard data for an existing upload (repair / lazy load for merchant portal).
    """
    _ = (merchant_code or "").strip()  # reserved for ownership checks
    try:
        dashboard = get_dashboard_data(db, upload_id=int(upload_id))
        return dashboard_data_to_jsonable(dashboard)
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_dashboard_json failed upload_id=%s", upload_id)
        raise HTTPException(
            status_code=404,
            detail=f"dashboard not available: {type(exc).__name__}: {exc}",
        ) from exc


@app.post("/api/discount")
async def discount_recommendations(
    db: Session = Depends(get_db),
    file: UploadFile | None = File(None, description="Shopify orders export CSV (optional if upload_id/store_id)"),
    merchant_code: str | None = Query(None, description="Portal merchant code (for linking CSV uploads)"),
    upload_id: int | None = Query(None, ge=1, description="Existing processed upload (demo / legacy)"),
    store_id: int | None = Query(None, ge=1, description="Canonical store id (store-centric analysis)"),
    start_date: date | None = Query(None, description="Filter orders by order_date (store mode)"),
    end_date: date | None = Query(None, description="Filter orders by order_date (store mode)"),
    level: int = Query(3, ge=2, le=3, description="Discount engine level (2 or 3)"),
    duration_days: int = Query(3, ge=1, le=14, description="Draft promo duration in days"),
    limit: int = Query(50, ge=1, le=200, description="Max drafts to return"),
    profit_config_json: str | None = Query(
        None,
        description="Optional JSON string: normalized profit_configuration (cogs, shipping_costs, …)",
    ),
) -> dict[str, Any]:
    """
    Discount drafts + overview + ``dashboard`` object.

    **Input precedence:** ``store_id`` > new CSV ``file`` > ``upload_id``.
    If both ``store_id`` and ``upload_id`` are set, ``store_id`` wins.
    Exactly one of ``store_id``, ``file`` (non-empty), or ``upload_id`` must be provided.

    **Optional** ``profit_config_json``: same structure as portal_merchant sends; omitted means basic analysis.
    """
    file_bytes: bytes | None = None
    filename: str | None = None
    if file is not None and (file.filename or "").strip():
        raw = await file.read()
        if raw:
            file_bytes = raw
            filename = str(file.filename)

    if store_id is None and upload_id is None and not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Provide store_id, upload_id, or a non-empty CSV file (field 'file').",
        )

    profit_configuration: Any | None = None
    raw_pc = (profit_config_json or "").strip()
    if raw_pc:
        try:
            profit_configuration = json.loads(raw_pc)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"invalid profit_config_json: {exc}",
            ) from exc
        if profit_configuration is not None and not isinstance(profit_configuration, dict):
            raise HTTPException(
                status_code=400,
                detail="profit_config_json must be a JSON object",
            )

    try:
        return run_discount_recommendation(
            db,
            file_bytes=file_bytes,
            filename=filename,
            merchant_code=merchant_code,
            upload_id=upload_id,
            store_id=store_id,
            start_date=start_date,
            end_date=end_date,
            level=int(level),
            duration_days=int(duration_days),
            limit=int(limit),
            profit_configuration=profit_configuration,
        )
    except DiscountAnalysisError as exc:
        logger.info("discount: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ShopifyExportParseError as exc:
        logger.info("discount: invalid shopify export: %s", exc)
        raise HTTPException(status_code=400, detail=f"invalid shopify export: {exc}") from exc
    except Exception as exc:
        logger.exception("discount: processing failed")
        raise HTTPException(
            status_code=500,
            detail=f"discount processing failed: {type(exc).__name__}: {exc}",
        ) from exc

@app.get("/api/stores/{store_id}/profit-configurations")
def get_profit_configurations(
    store_id: int,
    db: Session = Depends(get_db),
):
    """Get all profit configurations for a store."""
    configs = db.query(ProfitConfiguration).filter(
        ProfitConfiguration.store_id == store_id
    ).all()
    return {"configurations": [c.to_dict() for c in configs]}


@app.post("/api/stores/{store_id}/profit-configurations")
def create_profit_configuration_endpoint(
    store_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Create a new profit configuration."""
    config = create_profit_configuration(
        db,
        store_id=store_id,
        name=payload.get("name", "Default"),
        cogs_mode=payload.get("cogs", {}).get("mode"),
        cogs_value=payload.get("cogs", {}).get("value"),
        shipping_mode=payload.get("shipping_costs", {}).get("mode"),
        shipping_value=payload.get("shipping_costs", {}).get("value"),
        transaction_fee_mode=payload.get("transaction_fees", {}).get("mode"),
        transaction_fee_value=payload.get("transaction_fees", {}).get("value"),
        custom_costs=payload.get("custom_costs", []),
        is_default=payload.get("is_default", False),
    )
    return config.to_dict()


@app.put("/api/profit-configurations/{config_id}")
def update_profit_configuration_endpoint(
    config_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Update a profit configuration."""
    config = update_profit_configuration(db, config_id, **payload)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config.to_dict()


@app.delete("/api/profit-configurations/{config_id}")
def delete_profit_configuration_endpoint(
    config_id: int,
    db: Session = Depends(get_db),
):
    """Delete a profit configuration."""
    if not delete_profit_configuration(db, config_id):
        raise HTTPException(status_code=404, detail="Configuration not found")
    return {"success": True}


@app.post("/api/stores/{store_id}/profit-configurations/{config_id}/set-default")
def set_default_configuration_endpoint(
    store_id: int,
    config_id: int,
    db: Session = Depends(get_db),
):
    """Set a configuration as default for the store."""
    config = set_default_configuration(db, store_id, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config.to_dict()