from __future__ import annotations

from typing import Callable, Iterable, Optional

import logging
import sqlite3
from ism.domain.errors import (
    FxUnavailableError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from ism.domain.models import SaleHeader, SaleLine
from ism.repositories.contracts import ProductRepository
from ism.repositories.unit_of_work import RepositoryUnitOfWork, UnitOfWork

log = logging.getLogger("ism.sales")


class SalesService:
    def __init__(
        self,
        repo: ProductRepository,
        fx_service,
        uow_factory: Callable[[], UnitOfWork] | None = None,
    ):
        self.repo = repo
        self.fx = fx_service
        self.uow_factory = uow_factory or (lambda: RepositoryUnitOfWork(repo))

    def _normalize_items(self, items: list[dict]) -> list[dict]:
        grouped: dict[int, dict[str, float | int]] = {}

        for it in items:
            qty = int(it["qty"])
            unit_price = float(it["unit_price_usd"])
            if qty <= 0:
                raise ValidationError("Qty must be >= 1.")
            if unit_price <= 0:
                raise ValidationError("Unit price must be > 0.")

            product_id = int(it["product_id"])
            if product_id not in grouped:
                grouped[product_id] = {"qty": qty, "gross_usd": qty * unit_price}
            else:
                grouped[product_id]["qty"] = int(grouped[product_id]["qty"]) + qty
                grouped[product_id]["gross_usd"] = float(grouped[product_id]["gross_usd"]) + (qty * unit_price)

        normalized: list[dict] = []
        for product_id, bucket in grouped.items():
            qty = int(bucket["qty"])
            gross_usd = float(bucket["gross_usd"])
            normalized.append(
                {
                    "product_id": product_id,
                    "qty": qty,
                    "unit_price_usd": (gross_usd / qty),
                }
            )
        return normalized

    def create_sale(self, notes: Optional[str], items: Iterable[dict], actor_user_id: int | None = None) -> int:
        """
        items: [{product_id, qty, unit_price_usd}]
        """
        items = list(items)
        if not items:
            raise ValidationError("Cart is empty.")
        items = self._normalize_items(items)

        # Validate normalized items.
        for it in items:
            product_id = int(it["product_id"])
            prod = self.repo.get_product_by_id(product_id)
            if not prod:
                raise NotFoundError("Product not found.")
            if int(it["qty"]) > int(prod.stock):
                raise InsufficientStockError(f"Not enough stock for {prod.sku}. Available: {prod.stock}")

        try:
            fx = float(self.fx.get_today_rate())
        except FxUnavailableError:
            raise
        except (TypeError, ValueError) as e:
            raise FxUnavailableError(str(e)) from e

        try:
            with self.uow_factory() as uow:
                sale_id = uow.create_sale(fx, notes, items, actor_user_id=actor_user_id)
        except sqlite3.IntegrityError as e:
            raise ValidationError("Sale has invalid or duplicated lines.") from e
        except ValueError as e:
            msg = str(e)
            if "Not enough stock" in msg:
                raise InsufficientStockError(msg) from e
            if "Product not found" in msg:
                raise NotFoundError("Product not found.") from e
            raise ValidationError(msg) from e
        log.info("sale_created sale_id=%s items=%s fx=%.4f actor=%s", sale_id, len(items), fx, actor_user_id)
        return sale_id

    def list_sales_between(self, start_iso: str, end_iso: str) -> list[SaleHeader]:
        return self.repo.list_sales_between(start_iso, end_iso)

    def get_sale_header(self, sale_id: int) -> Optional[SaleHeader]:
        return self.repo.get_sale_header(sale_id)

    def sale_items_for_sale(self, sale_id: int) -> list[SaleLine]:
        return self.repo.sale_items_for_sale(sale_id)

    def sales_summary_between(self, start_iso: str, end_iso: str):
        return self.repo.sales_summary_between(start_iso, end_iso)
