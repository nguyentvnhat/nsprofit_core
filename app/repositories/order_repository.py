"""Orders, line items, customers, raw rows."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from datetime import date, datetime, time

from sqlalchemy import desc, select
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
        _ = (order_date, net_revenue)  # not persisted in legacy customer schema
        if not email:
            return None
        existing = self._session.scalars(select(Customer).where(Customer.email == email).limit(1)).first()
        first_name: str | None = None
        last_name: str | None = None
        if display_name:
            parts = [p for p in display_name.strip().split(" ") if p]
            if parts:
                first_name = parts[0]
                last_name = " ".join(parts[1:]) or None
        if existing:
            if first_name and not existing.first_name:
                existing.first_name = first_name
            if last_name and not existing.last_name:
                existing.last_name = last_name
            self._session.flush()
            return existing
        c = Customer(
            email=email,
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

    def list_orders_for_upload(
        self,
        upload_id: int,
        *,
        limit: int | None = None,
        include_items: bool = True,
        include_customer: bool = True,
    ) -> list[Order]:
        stmt = select(Order).where(Order.upload_id == upload_id)

        # Only eager-load what we need for the current use case.
        if include_items:
            stmt = stmt.options(joinedload(Order.items))
        if include_customer:
            stmt = stmt.options(joinedload(Order.customer))

        # MySQL doesn't support `NULLS LAST` syntax.
        # We emulate "nulls last" by ordering by `order_date IS NULL` first:
        #   - False (0) comes before True (1) => nulls last.
        stmt = stmt.order_by(Order.order_date.is_(None), desc(Order.order_date), Order.id)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self._session.scalars(stmt).unique().all())

    def list_orders_for_store(
        self,
        store_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = 5000,
        include_items: bool = True,
        include_customer: bool = True,
    ) -> list[Order]:
        """Load canonical orders for a store (optional order_date range, inclusive dates)."""
        stmt = select(Order).where(Order.store_id == int(store_id))

        if start_date is not None:
            start_dt = datetime.combine(start_date, datetime.min.time())
            stmt = stmt.where(Order.order_date.is_not(None)).where(Order.order_date >= start_dt)
        if end_date is not None:
            end_dt = datetime.combine(end_date, time(23, 59, 59))
            stmt = stmt.where(Order.order_date.is_not(None)).where(Order.order_date <= end_dt)

        if include_items:
            stmt = stmt.options(joinedload(Order.items))
        if include_customer:
            stmt = stmt.options(joinedload(Order.customer))

        stmt = stmt.order_by(Order.order_date.is_(None), desc(Order.order_date), Order.id)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self._session.scalars(stmt).unique().all())

    def delete_normalized_for_upload(self, upload_id: int) -> None:
        orders = self._session.scalars(select(Order).where(Order.upload_id == upload_id)).all()
        for o in orders:
            self._session.delete(o)
        self._session.flush()
