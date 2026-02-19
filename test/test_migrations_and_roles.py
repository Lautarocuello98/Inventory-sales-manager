from pathlib import Path

import pytest

from ism.domain.errors import AuthorizationError
from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.auth_service import AuthService
from ism.services.inventory_service import InventoryService


def test_migrations_create_users_and_default_admin(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "m.db")
    repo.init_db()

    auth = AuthService(repo)
    users = auth.list_users()
    assert any(u.username == "admin" and u.role == "admin" for u in users)


def test_constraints_reject_invalid_price(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "c.db")
    repo.init_db()
    inv = InventoryService(repo)

    with pytest.raises(Exception):
        inv.add_product("SKU-1", "bad", 1.0, 0.0, 1, 0)


def test_auth_rejects_wrong_pin(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "a.db")
    repo.init_db()
    auth = AuthService(repo)

    with pytest.raises(AuthorizationError):
        auth.login("admin", "wrong")