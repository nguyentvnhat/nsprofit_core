"""
HTTP API for external clients (e.g. Laravel) to request discount recommendations.

Reads an uploaded Shopify CSV and returns JSON. May persist merchant/upload rows when DB is configured.
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.upload_repository import UploadRepository
from app.services.discount_recommendation import build_discount_recommendation_rows_from_normalized
from app.services.file_parser import ShopifyExportParseError, parse_shopify_orders_csv
from app.services.promotion_draft import promotion_drafts_from_discount_rows, promotion_drafts_to_jsonable
from app.services.shopify_normalizer import normalize_shopify_data

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
    path = Path(raw).expanduser()
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


def _default_guardrails(*, level: int, duration_days: int) -> dict[str, Any]:
    lvl = int(level or 3)
    dur = int(duration_days or 3)
    items = [
        {
            "code": "cap_extra_discount",
            "label": "Cap extra discount: ≤15% (simple steps: 5/8/10/12/15).",
        },
        {
            "code": "heavy_discount_new_customers",
            "label": "If already discounted ≥25%, prefer new customers only or skip.",
        },
        {
            "code": "low_confidence_shorter",
            "label": "Low confidence → run shorter (e.g. 3 days) or skip.",
        },
        {
            "code": "scope_per_product",
            "label": "Keep discounts scoped per product (avoid site-wide blanket promos).",
        },
    ]
    if lvl < 3:
        items.insert(
            0,
            {
                "code": "engine_level_note",
                "label": "Level 2 returns discount-only suggestions (no mix). Use Level 3 for promotion mix.",
            },
        )
    return {
        "title": "Guardrails (default)",
        "duration_days": dur,
        "engine_level": lvl,
        "items": items,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/discount")
async def discount_recommendations(
    db: Session = Depends(get_db),
    file: UploadFile = File(..., description="Shopify orders export CSV"),
    merchant_code: str | None = Query(None, description="Portal merchant code (for linking uploads)"),
    level: int = Query(3, ge=2, le=3, description="Discount engine level (2 or 3)"),
    duration_days: int = Query(3, ge=1, le=14, description="Draft promo duration in days"),
    limit: int = Query(50, ge=1, le=200, description="Max drafts to return"),
) -> dict[str, Any]:
    """
    Accept a Shopify orders CSV and return discount drafts + overview for UI rendering.
    """
    upload: Any | None = None

    try:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="file must be a .csv")

        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="empty file")

        merchant_id: int | None = None
        mc = (merchant_code or "").strip()
        try:
            if mc:
                merchant = MerchantRepository(db).get_or_create_by_code(mc)
                merchant_id = int(merchant.id)
            upload = UploadRepository(db).create(file_name=str(file.filename), merchant_id=merchant_id)
        except Exception as exc:
            logger.exception("discount: merchant/upload persistence failed (merchant_code=%r)", mc)
            raise HTTPException(
                status_code=500,
                detail=f"database error while starting upload: {type(exc).__name__}: {exc}",
            ) from exc

        try:
            parse_result = parse_shopify_orders_csv(BytesIO(raw))
            orders_data, items_data, _customers = normalize_shopify_data(parse_result.rows)
        except ShopifyExportParseError as exc:
            logger.info("discount: invalid shopify export: %s", exc)
            raise HTTPException(status_code=400, detail=f"invalid shopify export: {exc}") from exc
        except Exception as exc:
            logger.exception("discount: parse/normalize failed upload_id=%s", getattr(upload, "id", None))
            try:
                UploadRepository(db).update_status(upload, "failed", error_message=str(exc))
            except Exception:
                logger.exception("discount: could not mark upload failed after parse error")
            raise HTTPException(status_code=500, detail=f"failed to parse file: {exc}") from exc

        try:
            rows = build_discount_recommendation_rows_from_normalized(orders_data, items_data)
            drafts = promotion_drafts_from_discount_rows(
                rows,
                upload_id=int(upload.id),
                duration_days=int(duration_days),
                level=int(level),
                limit=int(limit),
            )
            drafts_json = promotion_drafts_to_jsonable(drafts)

            total = len(drafts)
            high_conf = sum(1 for d in drafts if str(getattr(d, "confidence", "") or "").lower().strip() == "high")
            heavy = sum(1 for d in drafts if float(getattr(d, "current_discount_pct", 0.0) or 0.0) >= 25.0)
            net_rev_total = sum(float(getattr(d, "net_revenue", 0.0) or 0.0) for d in drafts)

            mix: dict[str, int] = {"discount": 0, "bundle": 0, "flash_sale": 0}
            for d in drafts:
                ct = str(getattr(d, "campaign_type", "discount") or "discount")
                if ct not in mix:
                    continue
                mix[ct] += 1

            return {
                "meta": {
                    "engine_level": int(level),
                    "duration_days": int(duration_days),
                    "limit": int(limit),
                    "filename": str(file.filename),
                    "upload_id": int(upload.id),
                    "merchant_code": mc or None,
                },
                "overview": {
                    "products_with_recs": int(total),
                    "high_confidence_items": int(high_conf),
                    "already_ge_25pct_off": int(heavy),
                    "net_revenue_covered": float(round(net_rev_total, 2)),
                    "strategy_mix": mix,
                },
                "guardrails": _default_guardrails(level=int(level), duration_days=int(duration_days)),
                "drafts": drafts_json,
                "rows": rows[: min(len(rows), int(limit))],
            }
        except Exception as exc:
            logger.exception(
                "discount: pipeline failed upload_id=%s level=%s limit=%s",
                getattr(upload, "id", None),
                level,
                limit,
            )
            raise HTTPException(
                status_code=500,
                detail=f"discount processing failed: {type(exc).__name__}: {exc}",
            ) from exc

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("discount: unexpected failure before/during handler")
        raise HTTPException(
            status_code=500,
            detail=f"internal error: {type(exc).__name__}: {exc}",
        ) from exc
