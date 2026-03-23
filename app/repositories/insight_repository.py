"""Insight persistence."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.insight import Insight


class InsightRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_upload(self, upload_id: int, insights: list[Insight]) -> None:
        self._session.execute(delete(Insight).where(Insight.upload_id == upload_id))
        for ins in insights:
            self._session.add(ins)
        self._session.flush()

    def list_for_upload(self, upload_id: int) -> list[Insight]:
        stmt = select(Insight).where(Insight.upload_id == upload_id).order_by(Insight.id)
        return list(self._session.scalars(stmt).all())
