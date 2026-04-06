"""Canonical order loading for analytics (upload-scoped vs store-scoped)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.repositories.order_repository import OrderRepository


class OrderAnalysisRepository:
    """Thin facade over :class:`OrderRepository` for analysis pipelines."""

    def __init__(self, session: Session) -> None:
        self._orders = OrderRepository(session)

    def load_orders_for_upload(
        self,
        upload_id: int,
        *,
        limit: int | None = 5000,
        include_items: bool = True,
        include_customer: bool = False,
    ) -> list:
        return self._orders.list_orders_for_upload(
            int(upload_id),
            include_items=include_items,
            include_customer=include_customer,
            limit=limit,
        )

    def load_orders_for_store(
        self,
        store_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = 5000,
        include_items: bool = True,
        include_customer: bool = False,
    ) -> list:
        return self._orders.list_orders_for_store(
            int(store_id),
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            include_items=include_items,
            include_customer=include_customer,
        )
