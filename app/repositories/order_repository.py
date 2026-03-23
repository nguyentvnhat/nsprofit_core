"""Orders, line items, customers, raw rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.raw_order import RawOrder


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_raw_rows(self, upload_id: int, rows: list[dict], *, start_index: int = 0) -> None:
        for i, payload in enumerate(rows):
            self._session.add(
                RawOrder(upload_id=upload_id, row_index=start_index + i, raw_payload=payload)
            )
        self._session.flush()

    def upsert_customer(
        self,
        *,
        email: str | None,
        external_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> Customer | None:
        if not email and not external_id:
            return None
        existing = None
        if email:
            existing = self._session.scalars(
                select(Customer).where(Customer.email == email).limit(1)
            ).first()
        if existing is None and external_id:
            existing = self._session.scalars(
                select(Customer).where(Customer.external_id == external_id).limit(1)
            ).first()
        if existing:
            if first_name and not existing.first_name:
                existing.first_name = first_name
            if last_name and not existing.last_name:
                existing.last_name = last_name
            if external_id and not existing.external_id:
                existing.external_id = external_id
            self._session.flush()
            return existing
        c = Customer(
            email=email,
            external_id=external_id,
            first_name=first_name,
            last_name=last_name,
        )
        self._session.add(c)
        self._session.flush()
        return c

    def add_order(self, order: Order) -> Order:
        self._session.add(order)
        self._session.flush()
        return order

    def add_order_items(self, items: list[OrderItem]) -> None:
        for it in items:
            self._session.add(it)
        self._session.flush()

    def list_orders_for_upload(self, upload_id: int) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.upload_id == upload_id)
            .options(joinedload(Order.items), joinedload(Order.customer))
            .order_by(Order.processed_at.desc(), Order.id)
        )
        return list(self._session.scalars(stmt).unique().all())

    def delete_normalized_for_upload(self, upload_id: int) -> None:
        """Remove orders (cascades to items) for reprocessing."""
        orders = self._session.scalars(select(Order).where(Order.upload_id == upload_id)).all()
        for o in orders:
            self._session.delete(o)
        self._session.flush()
