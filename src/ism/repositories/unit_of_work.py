from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Protocol


class UnitOfWork(Protocol):
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def create_sale(self, fx_usd_ars: float, notes: Optional[str], items: Iterable[dict], actor_user_id: int | None = None) -> int: ...
    def create_purchase(self, vendor: Optional[str], notes: Optional[str], items: Iterable[dict], actor_user_id: int | None = None) -> int: ...


@dataclass
class RepositoryUnitOfWork:
    """Unit of Work adapter for transactional write use-cases.

    The current repository methods already encapsulate SQL transactions.
    This class centralizes write orchestration so services stay persistence-agnostic.
    """

    repo: object

    def __enter__(self) -> "RepositoryUnitOfWork":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def create_sale(self, fx_usd_ars: float, notes: Optional[str], items: Iterable[dict], actor_user_id: int | None = None) -> int:
        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        return int(self.repo.create_sale(dt_iso, fx_usd_ars, notes, items, actor_user_id=actor_user_id))

    def create_purchase(self, vendor: Optional[str], notes: Optional[str], items: Iterable[dict], actor_user_id: int | None = None) -> int:
        items = list(items)
        total_usd = sum(float(it["unit_cost_usd"]) * int(it["qty"]) for it in items)
        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        return int(
            self.repo.create_purchase_with_items(
                datetime_iso=dt_iso,
                vendor=vendor,
                total_usd=total_usd,
                notes=notes,
                items=items,
                actor_user_id=actor_user_id,
            )
        )