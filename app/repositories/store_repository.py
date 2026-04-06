"""Store (canonical merchant) lookups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store import Store


class StoreRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, store_id: int) -> Store | None:
        return self._session.get(Store, int(store_id))

    def get_optional(self, store_id: int | None) -> Store | None:
        if store_id is None:
            return None
        return self.get(store_id)
