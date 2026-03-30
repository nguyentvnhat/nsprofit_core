"""Persistence helpers for ai_campaign_logs."""

from __future__ import annotations

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

    def list_for_campaign(self, campaign_id: str, *, limit: int = 200) -> list[AiCampaignLog]:
        stmt = (
            select(AiCampaignLog)
            .where(AiCampaignLog.campaign_id == campaign_id)
            .order_by(AiCampaignLog.id.desc())
            .limit(max(1, int(limit)))
        )
        return list(self._session.scalars(stmt).all())

