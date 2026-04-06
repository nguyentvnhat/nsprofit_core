"""Persistence helpers for ai_campaign_logs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_campaign_log import AiCampaignLog


class AiCampaignLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, log: AiCampaignLog) -> AiCampaignLog:
        self._session.add(log)
        self._session.flush()
        return log

    def log_discount_api_run(
        self,
        *,
        analysis_mode: str,
        upload_id: int | None,
        store_id: int | None,
        source_type: str | None,
        data_source_id: int | None,
        sync_session_id: int | None,
        linked_order_count: int,
        decision_payload_json: dict[str, Any] | None = None,
    ) -> AiCampaignLog | None:
        """
        Best-effort analytics row for /api/discount (does not replace Streamlit per-draft logs).

        ``ai_campaign_logs.store_id`` is legacy string storage; integer ``stores.id`` is stringified.
        """
        try:
            log = AiCampaignLog(
                store_id=str(store_id) if store_id is not None else None,
                campaign_id=f"discount_api_{analysis_mode}",
                source_type=source_type,
                data_source_id=data_source_id,
                sync_session_id=sync_session_id,
                status="success",
                linked_order_count=int(linked_order_count),
                decision_payload_json=decision_payload_json,
            )
            self._session.add(log)
            self._session.flush()
            return log
        except Exception:
            return None

    def list_for_campaign(self, campaign_id: str, *, limit: int = 200) -> list[AiCampaignLog]:
        stmt = (
            select(AiCampaignLog)
            .where(AiCampaignLog.campaign_id == campaign_id)
            .order_by(AiCampaignLog.id.desc())
            .limit(max(1, int(limit)))
        )
        return list(self._session.scalars(stmt).all())

