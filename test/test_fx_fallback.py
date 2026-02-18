from datetime import date
from pathlib import Path

import requests

from src.ism.repositories.sqlite_repo import SqliteRepository
from src.ism.services.fx_service import FxService


def test_fx_uses_latest_cached_rate_when_remote_fails(tmp_path: Path):
    db = tmp_path / "fx.db"
    repo = SqliteRepository(db)
    repo.init_db()
    repo.set_fx_rate("2024-01-01", 1234.5)

    fx = FxService(repo)

    def fail(_url: str):
        raise requests.RequestException("network down")

    fx._fetch_json = fail  # type: ignore[attr-defined]

    rate = fx.get_rate_for_date(date(2024, 1, 2))
    assert rate == 1234.5
    assert repo.get_fx_rate("2024-01-02") == 1234.5