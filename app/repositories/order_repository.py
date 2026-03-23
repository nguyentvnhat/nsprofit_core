"""Orders, line items, customers, raw rows."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, nulls_last, select
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
                RawOrder(
                    upload_id=upload_id,
                    row_number=start_index + i,
                    raw_payload_json=payload,
                )
            )
        self._session.flush()

    def upsert_customer_for_order(
        self,
        *,
        email: str | None,
        display_name: str | None,
        order_date: datetime | None,
        net_revenue: Decimal | None,
    ) -> Customer | None:
        if not email:
            return None
        existing = self._session.scalars(select(Customer).where(Customer.email == email).limit(1)).first()
        net = net_revenue or Decimal("0")
        if existing:
            if display_name and not existing.name:
                existing.name = display_name
            if order_date:
                if existing.first_order_date is None or order_date < existing.first_order_date:
                    existing.first_order_date = order_date
                if existing.last_order_date is None or order_date > existing.last_order_date:
                    existing.last_order_date = order_date
            existing.total_orders = int(existing.total_orders or 0) + 1
            existing.total_spent = Decimal(existing.total_spent or 0) + net
            self._session.flush()
            return existing
        c = Customer(
            email=email,
            name=display_name,
            first_order_date=order_date,
            last_order_date=order_date,
            total_orders=1,
            total_spent=net,
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
            .order_by(nulls_last(desc(Order.order_date)), Order.id)
        )
        return list(self._session.scalars(stmt).unique().all())

    def delete_normalized_for_upload(self, upload_id: int) -> None:
        orders = self._session.scalars(select(Order).where(Order.upload_id == upload_id)).all()
        for o in orders:
            self._session.delete(o)
        self._session.flush()
