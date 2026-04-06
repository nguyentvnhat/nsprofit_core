"""Typed context for /api/discount — avoids passing loose dicts through the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.profit_configuration_normalizer import NormalizedProfitConfiguration


@dataclass(frozen=True)
class DiscountAnalysisContext:
    analysis_mode: str
    upload_id: int | None
    store_id: int | None
    start_date: date | None
    end_date: date | None
    level: int
    duration_days: int
    limit: int
    profit_configuration: NormalizedProfitConfiguration
    profit_warnings: tuple[str, ...] = ()

    def to_meta_subset(self) -> dict[str, Any]:
        return {
            "analysis_mode": self.analysis_mode,
            "upload_id": self.upload_id,
            "store_id": self.store_id,
            "date_range_used": {
                "start_date": self.start_date.isoformat() if self.start_date else None,
                "end_date": self.end_date.isoformat() if self.end_date else None,
            },
            "level": self.level,
            "duration_days": self.duration_days,
            "limit": self.limit,
            "config_completeness": self.profit_configuration.completeness,
        }
