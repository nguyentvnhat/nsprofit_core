"""Promotion draft persistence."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.promotion_draft import PromotionDraft


class PromotionDraftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_upload(self, upload_id: int, drafts: list[PromotionDraft]) -> None:
        self._session.execute(delete(PromotionDraft).where(PromotionDraft.upload_id == upload_id))
        for d in drafts:
            self._session.add(d)
        self._session.flush()

    def list_for_upload(self, upload_id: int) -> list[PromotionDraft]:
        stmt = (
            select(PromotionDraft)
            .where(PromotionDraft.upload_id == upload_id)
            .order_by(PromotionDraft.id)
        )
        return list(self._session.scalars(stmt).all())

