"""Metric snapshot persistence."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot


class MetricRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_upload(self, upload_id: int, snapshots: list[MetricSnapshot]) -> None:
        self._session.execute(delete(MetricSnapshot).where(MetricSnapshot.upload_id == upload_id))
        for s in snapshots:
            self._session.add(s)
        self._session.flush()

    def list_for_upload(self, upload_id: int) -> list[MetricSnapshot]:
        stmt = select(MetricSnapshot).where(MetricSnapshot.upload_id == upload_id)
        return list(self._session.scalars(stmt).all())
