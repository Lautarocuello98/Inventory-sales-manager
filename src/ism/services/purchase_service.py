from __future__ import annotations

from typing import Callable, Iterable, Optional
import logging

from ism.domain.errors import ValidationError, NotFoundError
from ism.domain.models import PurchaseHeader, PurchaseLine
from ism.repositories.contracts import ProductRepository
from ism.repositories.unit_of_work import RepositoryUnitOfWork, UnitOfWork


log = logging.getLogger("ism.purchase")


class PurchaseService:
    def __init__(
        self,
        repo: ProductRepository,
        uow_factory: Callable[[], UnitOfWork] | None = None,
    ):
        self.repo = repo
        self.uow_factory = uow_factory or (lambda: RepositoryUnitOfWork(repo))

    def create_purchase(self, vendor: Optional[str], notes: Optional[str], items: Iterable[dict], actor_user_id: int | None = None) -> int:
        """
        items: [{product_id, qty, unit_cost_usd}]

        Updates stock and cost using weighted average:
          new_cost = (old_stock*old_cost + qty*unit_cost) / (old_stock+qty)
        """
        items = list(items)
        if not items:
            raise ValidationError("Restock cart is empty.")

        # Validate items
        for it in items:
            qty = int(it["qty"])
            unit_cost = float(it["unit_cost_usd"])
            if qty <= 0:
                raise ValidationError("Qty must be >= 1.")
            if unit_cost < 0:
                raise ValidationError("Unit cost must be >= 0.")
            prod = self.repo.get_product_by_id(int(it["product_id"]))
            if not prod:
                raise NotFoundError("Product not found/active.")

        try:
            with self.uow_factory() as uow:
                purchase_id = uow.create_purchase(
                    vendor=vendor,
                    notes=notes,
                    items=items,
                    actor_user_id=actor_user_id,
                )
                
        except ValueError as e:
            raise NotFoundError(str(e))

        log.info("purchase_created purchase_id=%s items=%s actor=%s", purchase_id, len(items), actor_user_id)
        return int(purchase_id)

    def list_purchases_between(self, start_iso: str, end_iso: str) -> list[PurchaseHeader]:
        return self.repo.list_purchases_between(start_iso, end_iso)

    def purchase_items_for_purchase(self, purchase_id: int) -> list[PurchaseLine]:
        return self.repo.purchase_items_for_purchase(purchase_id)
