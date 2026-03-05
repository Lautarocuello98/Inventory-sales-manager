from pathlib import Path

import pytest
from conftest import set_admin_pin

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

    admin_pin = set_admin_pin(repo)
    admin = auth.login("admin", admin_pin)
    auth.create_user(admin, "seller1", "Seller123", "seller")
    auth.create_user(admin, "viewer1", "Viewer123", "viewer")

    users = auth.list_users()
    roles = {u.username: u.role for u in users}
    assert roles["seller1"] == "seller"
    assert roles["viewer1"] == "viewer"


def test_non_admin_cannot_create_user(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "ua.db")
    repo.init_db()
    auth = AuthService(repo)

    admin_pin = set_admin_pin(repo)
    admin = auth.login("admin", admin_pin)
    auth.create_user(admin, "seller2", "Seller123", "seller")
    seller = auth.login("seller2", "Seller123")

    with pytest.raises(AuthorizationError):
        auth.create_user(seller, "x", "Viewer123", "viewer")

def test_migration_failure_restores_db(tmp_path: Path):
    class BrokenMigrationRepo(SqliteRepository):
        def _migration_v3_auth_hardening(self, cur):
            raise RuntimeError("forced migration failure")

    db = tmp_path / "broken.db"
    repo = SqliteRepository(db)
    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM schema_migrations WHERE version = 3")
    conn.commit()
    cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
    before = int(cur.fetchone()[0])
    conn.close()

    broken = BrokenMigrationRepo(db)

    with pytest.raises(RuntimeError, match="Original database restored"):
        broken.run_migrations()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
    after = int(cur.fetchone()[0])
    conn.close()

    assert after == before


def test_migrations_repair_missing_versions_even_with_higher_version_present(tmp_path: Path):
    db = tmp_path / "missing_version.db"
    repo = SqliteRepository(db)
    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM schema_migrations WHERE version = 3")
    conn.commit()
    conn.close()

    repo.run_migrations()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations ORDER BY version")
    versions = [int(r[0]) for r in cur.fetchall()]
    conn.close()

    assert 3 in versions
    assert max(versions) >= 4


def test_migration_v4_creates_reporting_indexes(tmp_path: Path):
    db = tmp_path / "indexes.db"
    repo = SqliteRepository(db)
    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='index' AND name IN (
            'idx_sales_datetime',
            'idx_purchases_datetime',
            'idx_stock_ledger_product_datetime'
        )
        """
    )
    names = {str(r[0]) for r in cur.fetchall()}
    conn.close()

    assert "idx_sales_datetime" in names
    assert "idx_purchases_datetime" in names
    assert "idx_stock_ledger_product_datetime" in names
