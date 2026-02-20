from pathlib import Path

import pytest

from conftest import set_admin_pin

from ism.domain.errors import AuthorizationError, ValidationError
from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.auth_service import AuthService
from ism.services.inventory_service import InventoryService
from ism.services.sales_service import SalesService
from ism.ui.views.reports_view import ReportsView


class FixedFxService:
    def get_today_rate(self):
        return 1000.0


def test_default_admin_pin_is_hashed_and_login_works(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "sec.db")
    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("SELECT pin FROM users WHERE username='admin'")
    stored = str(cur.fetchone()[0])
    conn.close()

    assert stored.startswith("pbkdf2_sha256$")

    auth = AuthService(repo)
    admin_pin = set_admin_pin(repo)
    user = auth.login("admin", admin_pin)
    assert user.username == "admin"


def test_legacy_plain_pin_is_upgraded_to_hash_on_successful_login(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "legacy.db")
    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET pin='1234' WHERE username='admin'")
    conn.commit()
    conn.close()

    auth = AuthService(repo)
    auth.login("admin", "1234")

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("SELECT pin FROM users WHERE username='admin'")
    upgraded = str(cur.fetchone()[0])
    conn.close()

    assert upgraded.startswith("pbkdf2_sha256$")


def test_inventory_rejects_zero_price_before_hitting_db(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "inv.db")
    repo.init_db()
    inv = InventoryService(repo)

    with pytest.raises(ValidationError, match="Price must be > 0"):
        inv.add_product("SKU-1", "bad", 1.0, 0.0, 1, 0)


def test_sales_rejects_zero_unit_price_before_hitting_db(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "sales.db")
    repo.init_db()
    inv = InventoryService(repo)
    pid = inv.add_product("SKU-1", "Producto", 2.0, 10.0, 10, 1)
    sales = SalesService(repo, FixedFxService())

    with pytest.raises(ValidationError, match="Unit price must be > 0"):
        sales.create_sale(notes=None, items=[{"product_id": pid, "qty": 1, "unit_price_usd": 0.0}])


def test_reports_import_denied_for_viewer_role():
    calls = []

    class App:
        def can_action(self, _action):
            return False

        def handle_error(self, title, err, toast_text):
            calls.append((title, str(err), toast_text))

    view = ReportsView.__new__(ReportsView)
    view.app = App()

    view.import_excel()

    assert calls and calls[0][0] == "Import error"
    assert "can not import" in calls[0][1]


def test_reports_export_denied_for_unknown_role():
    calls = []

    class App:
        def can_action(self, _action):
            return False

        def handle_error(self, title, err, toast_text):
            calls.append((title, str(err), toast_text))

    view = ReportsView.__new__(ReportsView)
    view.app = App()

    view.export_report()

    assert calls and calls[0][0] == "Export error"
    assert "can not import" in calls[0][1]

def test_admin_cannot_create_user_with_weak_pin(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "weak_pin.db")
    repo.init_db()
    auth = AuthService(repo)

    admin_pin = set_admin_pin(repo)
    admin = auth.login("admin", admin_pin)

    with pytest.raises(AuthorizationError, match="at least"):
        auth.create_user(admin, "sellerw", "1234", "seller")

    with pytest.raises(AuthorizationError, match="letter"):
        auth.create_user(admin, "sellerw", "12345678", "seller")

    with pytest.raises(AuthorizationError, match="number"):
        auth.create_user(admin, "sellerw", "OnlyLetters", "seller")

def test_admin_can_change_own_password(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "change_pin.db")
    repo.init_db()
    auth = AuthService(repo)

    admin_pin = set_admin_pin(repo)
    admin = auth.login("admin", admin_pin)
    auth.change_my_pin(admin, admin_pin, "NewPass123", "NewPass123")

    with pytest.raises(AuthorizationError):
        auth.login("admin", admin_pin)

    updated = auth.login("admin", "NewPass123")
    assert updated.username == "admin"


def test_admin_cannot_change_password_with_wrong_current_pin(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "change_pin_fail.db")
    repo.init_db()
    auth = AuthService(repo)

    admin_pin = set_admin_pin(repo)
    admin = auth.login("admin", admin_pin)
    with pytest.raises(AuthorizationError):
        auth.change_my_pin(admin, "bad-current", "NewPass123", "NewPass123")


def test_change_password_clears_must_change_flag(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "must_change_pin.db")
    repo.init_db()
    auth = AuthService(repo)

    admin_pin = set_admin_pin(repo)
    admin = auth.login("admin", admin_pin)
    auth.change_my_pin(admin, admin_pin, "NewPass123", "NewPass123")

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("SELECT must_change_pin FROM users WHERE id=?", (admin.id,))
    must_change = int(cur.fetchone()[0])
    conn.close()

    assert must_change == 0

def test_admin_can_delete_product_with_zero_stock(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "delete_ok.db")
    repo.init_db()
    inv = InventoryService(repo)

    pid = inv.add_product("SKU-DEL-1", "To delete", 1.0, 2.0, 0, 0)
    inv.delete_product(pid)

    assert repo.get_product_by_id(pid) is None


def test_cannot_delete_product_with_stock(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "delete_fail.db")
    repo.init_db()
    inv = InventoryService(repo)

    pid = inv.add_product("SKU-DEL-2", "Cannot delete", 1.0, 2.0, 3, 0)

    with pytest.raises(ValidationError, match="stock > 0"):
        inv.delete_product(pid)

def test_bootstrap_admin_pin_is_written_to_restricted_file(tmp_path: Path):
    db = tmp_path / "bootstrap.db"
    repo = SqliteRepository(db)
    repo.init_db()

    pin_file = tmp_path / ".admin_bootstrap_pin"
    assert pin_file.exists()
    assert pin_file.read_text(encoding="utf-8").strip()

def test_bootstrap_admin_is_recreated_if_missing_even_with_other_users(tmp_path: Path):
    db = tmp_path / "bootstrap_missing_admin.db"
    repo = SqliteRepository(db)
    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username='admin'")
    cur.execute(
        """
        INSERT INTO users (username, pin, role, active, must_change_pin)
        VALUES ('seller1', ?, 'seller', 1, 0)
        """,
        (SqliteRepository._hash_pin("Seller123"),),
    )
    conn.commit()
    conn.close()

    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("SELECT active, must_change_pin, pin FROM users WHERE username='admin'")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert int(row[0]) == 1
    assert int(row[1]) == 1
    assert str(row[2]).startswith("pbkdf2_sha256$")


def test_bootstrap_admin_is_reactivated_with_new_provisional_pin(tmp_path: Path):
    db = tmp_path / "bootstrap_inactive_admin.db"
    repo = SqliteRepository(db)
    repo.init_db()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET active=0, must_change_pin=0 WHERE username='admin'")
    conn.commit()
    conn.close()

    pin_file = tmp_path / ".admin_bootstrap_pin"
    before = pin_file.read_text(encoding="utf-8").strip()

    repo.init_db()

    after = pin_file.read_text(encoding="utf-8").strip()
    assert after
    assert after != before

    auth = AuthService(repo)
    admin = auth.login("admin", after)
    assert admin.username == "admin"
    assert int(admin.must_change_pin) == 1