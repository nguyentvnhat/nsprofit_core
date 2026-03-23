"""Signal event persistence."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.signal_event import SignalEvent


class SignalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_upload(self, upload_id: int, events: list[SignalEvent]) -> None:
        self._session.execute(delete(SignalEvent).where(SignalEvent.upload_id == upload_id))
        for e in events:
            self._session.add(e)
        self._session.flush()

    def list_for_upload(
        self, upload_id: int, entity_type: str | None = None
    ) -> list[SignalEvent]:
        stmt = select(SignalEvent).where(SignalEvent.upload_id == upload_id)
        if entity_type:
            stmt = stmt.where(SignalEvent.entity_type == entity_type)
        return list(self._session.scalars(stmt).all())
