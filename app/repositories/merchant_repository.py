"""Persistence for merchant identities (core-side)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.merchant import Merchant


class MerchantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_code(self, merchant_code: str) -> Merchant | None:
        code = (merchant_code or "").strip()
        if not code:
            return None
        return self._session.execute(
            select(Merchant).where(Merchant.merchant_code == code)
        ).scalar_one_or_none()

    def get_or_create_by_code(self, merchant_code: str) -> Merchant:
        code = (merchant_code or "").strip()
        if not code:
            raise ValueError("merchant_code is required")

        existing = self.get_by_code(code)
        if existing is not None:
            return existing

        row = Merchant(merchant_code=code)
        self._session.add(row)
        self._session.flush()
        return row

