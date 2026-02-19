from __future__ import annotations

import logging
from datetime import date

import requests

from ism.domain.errors import FxUnavailableError

log = logging.getLogger("ism.fx")


class FxService:
    def __init__(self, repo):
        self.repo = repo

    def _fetch_json(self, url: str) -> dict:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()

    def _extract_usd_ars(self, data: dict) -> float:
        # common structure: {"date":"YYYY-MM-DD","usd":{"ars":1450.12, ...}}
        if "usd" in data and isinstance(data["usd"], dict):
            v = data["usd"].get("ars")
            if v is not None:
                return self._validate_rate(v)

        for _k, v in data.items():
            if isinstance(v, dict) and "ars" in v:
                return self._validate_rate(v["ars"])

        raise FxUnavailableError(f"FX API response missing ARS rate. Raw: {data}")

    def _validate_rate(self, value: object) -> float:
        rate = float(value)
        if rate <= 0:
            raise FxUnavailableError(f"FX rate must be > 0. Received: {rate}")
        return rate

    def get_rate_for_date(self, d: date) -> float:
        d_iso = d.isoformat()
        cached = self.repo.get_fx_rate(d_iso)
        if cached is not None:
            return float(cached)

        primary = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        fallback = "https://latest.currency-api.pages.dev/v1/currencies/usd.json"

        last_err = None
        for url in (primary, fallback):
            try:
                data = self._fetch_json(url)
                rate = self._extract_usd_ars(data)
                self.repo.set_fx_rate(d_iso, rate)
                return float(rate)
            except (requests.RequestException, ValueError, FxUnavailableError) as e:
                last_err = e
                log.warning("fx_source_failed url=%s error=%s", url, e)

        latest = self.repo.get_latest_fx_rate()
        if latest is not None:
            log.warning("fx_fallback_cached rate=%.4f", float(latest))
            self.repo.set_fx_rate(d_iso, float(latest))
            return float(latest)

        raise FxUnavailableError(f"FX fetch failed and no cached rate available. Last error: {last_err}")

    def get_today_rate(self) -> float:
        return self.get_rate_for_date(date.today())
