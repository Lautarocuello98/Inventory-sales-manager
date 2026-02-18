from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from ism.domain.errors import ValidationError, NotFoundError, InsufficientStockError, FxUnavailableError
from ism.domain.models import SaleHeader, SaleLine


class SalesService:
    def __init__(self, repo, fx_service):
        self.repo = repo
        self.fx = fx_service

    def create_sale(self, notes: Optional[str], items: Iterable[dict]) -> int:
        """
        items: [{product_id, qty, unit_price_usd}]
        """
        items = list(items)
        if not items:
            raise ValidationError("Cart is empty.")

        # Validate stock
        for it in items:
            qty = int(it["qty"])
            if qty <= 0:
                raise ValidationError("Qty must be >= 1.")
            prod = self.repo.get_product_by_id(int(it["product_id"]))
            if not prod:
                raise NotFoundError("Product not found.")
            if qty > int(prod.stock):
                raise InsufficientStockError(f"Not enough stock for {prod.sku}. Available: {prod.stock}")

        try:
            fx = float(self.fx.get_today_rate())
        except Exception as e:
            raise FxUnavailableError(str(e))

        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        return self.repo.create_sale(dt_iso, fx, notes, items)

    def list_sales_between(self, start_iso: str, end_iso: str) -> list[SaleHeader]:
        return self.repo.list_sales_between(start_iso, end_iso)

    def get_sale_header(self, sale_id: int) -> Optional[SaleHeader]:
        return self.repo.get_sale_header(sale_id)

    def sale_items_for_sale(self, sale_id: int) -> list[SaleLine]:
        return self.repo.sale_items_for_sale(sale_id)

    def sales_summary_between(self, start_iso: str, end_iso: str):
        return self.repo.sales_summary_between(start_iso, end_iso)
