from pathlib import Path

import pytest

from ism.domain.models import User
from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.inventory_service import InventoryService
from ism.services.auth_service import AuthService, LoginPolicy
from ism.services.backup_service import BackupService


def test_backup_service_creates_db_copy(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    repo = SqliteRepository(db_path)
    repo.init_db()

    backup = BackupService(db_path, tmp_path / "backups")
    backup_path = backup.create_backup()

    assert backup_path.exists()
    assert backup_path.stat().st_size > 0


def test_auth_service_locks_after_failed_attempts(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "sec_lock.db")
    repo.init_db()
    auth = AuthService(repo, policy=LoginPolicy(max_failed_attempts=2, lockout_seconds=30, min_pin_length=8))

    with pytest.raises(Exception):
        auth.login("admin", "bad")
    with pytest.raises(Exception, match="locked"):
        auth.login("admin", "bad")

def test_auth_lockout_persists_between_service_instances(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "sec_lock_persist.db")
    repo.init_db()
    auth = AuthService(repo, policy=LoginPolicy(max_failed_attempts=1, lockout_seconds=30, min_pin_length=8))

    with pytest.raises(Exception, match="locked"):
        auth.login("admin", "bad")

    auth2 = AuthService(repo, policy=LoginPolicy(max_failed_attempts=1, lockout_seconds=30, min_pin_length=8))
    with pytest.raises(Exception, match="locked"):
        auth2.login("admin", "bad")


def test_backup_is_encrypted_and_restore_works(tmp_path: Path):
    db_path = tmp_path / "sales_restore.db"
    repo = SqliteRepository(db_path)
    repo.init_db()
    inv = InventoryService(repo)
    inv.add_product("SKU-R-1", "Restore test", 1.0, 2.0, 3, 1)

    backup = BackupService(db_path, tmp_path / "backups")
    backup_path = backup.create_backup()
    assert backup_path.suffixes[-2:] == [".db", ".enc"]

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products")
    conn.commit()
    conn.close()

    backup.restore_backup(backup_path)

    products = inv.list_products()
    assert any(p.sku == "SKU-R-1" for p in products)


def test_restore_backup_requires_existing_key(tmp_path: Path):
    db_path = tmp_path / "sales_restore_key.db"
    repo = SqliteRepository(db_path)
    repo.init_db()
    inv = InventoryService(repo)
    inv.add_product("SKU-K-1", "Restore key", 1.0, 2.0, 1, 0)

    backup = BackupService(db_path, tmp_path / "backups")
    backup_path = backup.create_backup()

    key_path = tmp_path / "backups" / ".backup.key"
    key_path.unlink()

    with pytest.raises(FileNotFoundError, match="Backup key not found"):
        backup.restore_backup(backup_path)


def test_restore_backup_rejects_non_encrypted_extension(tmp_path: Path):
    db_path = tmp_path / "sales_restore_ext.db"
    repo = SqliteRepository(db_path)
    repo.init_db()

    backup = BackupService(db_path, tmp_path / "backups")
    bad_file = tmp_path / "invalid_backup.db"
    bad_file.write_bytes(b"not-encrypted")

    with pytest.raises(ValueError, match=".db.enc"):
        backup.restore_backup(bad_file)


def test_backup_service_reports_missing_openssl(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "sales_no_openssl.db"
    repo = SqliteRepository(db_path)
    repo.init_db()

    backup = BackupService(db_path, tmp_path / "backups")

    def _raise_not_found(*_args, **_kwargs):
        raise FileNotFoundError("openssl")

    monkeypatch.setattr("ism.services.backup_service.subprocess.run", _raise_not_found)

    with pytest.raises(ValueError, match="OpenSSL executable not found"):
        backup.create_backup()


def test_permission_matrix_allows_admin_manage_users():
    auth = AuthService(repo=None)
    admin = User(id=1, username="admin", role="admin")
    viewer = User(id=2, username="viewer", role="viewer")

    assert auth.can(admin, "manage_users") is True
    assert auth.can(viewer, "manage_users") is False
    assert auth.can(admin, "create_backup") is True
    assert auth.can(viewer, "create_backup") is False
    assert auth.can(admin, "restore_backup") is True
    assert auth.can(viewer, "restore_backup") is False
    assert auth.can(admin, "export_diagnostics") is True
    assert auth.can(viewer, "export_diagnostics") is False
    assert auth.can(admin, "run_health_check") is True
    assert auth.can(viewer, "run_health_check") is False
