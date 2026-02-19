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

def test_admin_can_create_seller_and_viewer(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "u.db")
    repo.init_db()
    auth = AuthService(repo)

    admin = auth.login("admin", "admin123!")
    auth.create_user(admin, "seller1", "1234", "seller")
    auth.create_user(admin, "viewer1", "1234", "viewer")

    users = auth.list_users()
    roles = {u.username: u.role for u in users}
    assert roles["seller1"] == "seller"
    assert roles["viewer1"] == "viewer"


def test_non_admin_cannot_create_user(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "ua.db")
    repo.init_db()
    auth = AuthService(repo)

    admin = auth.login("admin", "admin123!")
    auth.create_user(admin, "seller2", "1234", "seller")
    seller = auth.login("seller2", "1234")

    with pytest.raises(AuthorizationError):
        auth.create_user(seller, "x", "1234", "viewer")