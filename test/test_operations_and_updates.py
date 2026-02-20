from pathlib import Path

from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.backup_service import BackupService
from ism.services.inventory_service import InventoryService
from ism.services.operations_service import OperationsService
from ism.services.update_service import UpdateService
from ism.application.container import build_container


def test_operations_health_check_and_diagnostics_export(tmp_path: Path):
    db = tmp_path / "sales.db"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "app.log").write_text("ok", encoding="utf-8")

    repo = SqliteRepository(db)
    repo.init_db()

    ops = OperationsService(repo, db_path=db, logs_dir=logs, backup_dir=tmp_path / "backups")
    report = ops.run_health_check()

    assert report.sqlite_integrity == "ok"
    assert report.logs_count >= 1

    z = ops.export_diagnostics()
    assert z.exists()
    assert z.suffix == ".zip"


def test_operations_restore_latest_backup(tmp_path: Path):
    db = tmp_path / "sales.db"
    repo = SqliteRepository(db)
    repo.init_db()
    inv = InventoryService(repo)
    inv.add_product("SKU-REST", "Restore", 1.0, 2.0, 3, 1)

    backup = BackupService(db, tmp_path / "backups")
    backup.create_backup()

    conn = repo._conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products")
    conn.commit()
    conn.close()

    ops = OperationsService(repo, db_path=db, logs_dir=tmp_path / "logs", backup_dir=tmp_path / "backups")
    restored = ops.restore_latest_backup(backup)
    assert restored.exists()
    assert any(p.sku == "SKU-REST" for p in inv.list_products())


def test_update_service_reads_local_manifest(tmp_path: Path):
    manifest = tmp_path / "latest.json"
    manifest.write_text(
        '{"version":"1.2.0","download_url":"https://example.com/dl","notes":"Bugfix"}',
        encoding="utf-8",
    )

    svc = UpdateService(current_version="1.0.0", source=manifest)
    info = svc.check_for_update()

    assert info is not None
    assert info.latest_version == "1.2.0"


def test_update_service_supports_prefixed_and_partial_versions(tmp_path: Path):
    manifest = tmp_path / "latest.json"
    manifest.write_text(
        '{"version":"v1.1","download_url":"https://example.com/dl","notes":"Minor"}',
        encoding="utf-8",
    )

    svc = UpdateService(current_version="1.0.9", source=manifest)
    info = svc.check_for_update()

    assert info is not None
    assert info.latest_version == "v1.1"


def test_container_uses_pyproject_version_for_updates(tmp_path: Path):
    db = tmp_path / "version.db"
    container = build_container(db)

    assert container.updates.current_version == "1.1.3"