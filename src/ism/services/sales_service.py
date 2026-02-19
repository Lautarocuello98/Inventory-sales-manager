from __future__ import annotations

from typing import Callable, Iterable, Optional

from collections import Counter
import logging
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

    def create_sale(self, notes: Optional[str], items: Iterable[dict], actor_user_id: int | None = None) -> int:
        """
        items: [{product_id, qty, unit_price_usd}]
        """
        items = list(items)
        if not items:
            raise ValidationError("Cart is empty.")

        # Validate items and aggregate qty by product to avoid overselling
        qty_by_product: Counter[int] = Counter()
        for it in items:
            qty = int(it["qty"])
            unit_price = float(it["unit_price_usd"])
            if qty <= 0:
                raise ValidationError("Qty must be >= 1.")
            if unit_price <= 0:
                raise ValidationError("Unit price must be > 0.")

            product_id = int(it["product_id"])
            qty_by_product[product_id] += qty

            prod = self.repo.get_product_by_id(product_id)
            if not prod:
                raise NotFoundError("Product not found.")
            if qty_by_product[product_id] > int(prod.stock):
                raise InsufficientStockError(f"Not enough stock for {prod.sku}. Available: {prod.stock}")

        try:
            fx = float(self.fx.get_today_rate())
        except FxUnavailableError:
            raise
        except (TypeError, ValueError) as e:
            raise FxUnavailableError(str(e)) from e

        with self.uow_factory() as uow:
            sale_id = uow.create_sale(fx, notes, items, actor_user_id=actor_user_id)
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
