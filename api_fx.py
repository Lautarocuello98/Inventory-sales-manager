import requests


def _fetch_json(url: str) -> dict:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def _extract_usd_ars(data: dict) -> float:
    """
    Currency API formats are usually:
      {"date":"YYYY-MM-DD","usd":{"ars":1450.12, ...}}
    We'll parse defensively.
    """
    # common structure: data["usd"]["ars"]
    if "usd" in data and isinstance(data["usd"], dict):
        v = data["usd"].get("ars")
        if v is not None:
            return float(v)

    # fallback: search any nested dict for ars
    for k, v in data.items():
        if isinstance(v, dict) and "ars" in v:
            return float(v["ars"])

    raise RuntimeError(f"FX API response missing ARS rate. Raw: {data}")


def get_today_rate() -> float:
    """
    USD -> ARS FX using fawazahmed0 currency-api.
    Primary: jsdelivr CDN
    Fallback: Cloudflare Pages
    """
    primary = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
    fallback = "https://latest.currency-api.pages.dev/v1/currencies/usd.json"

    last_err = None
    for url in (primary, fallback):
        try:
            data = _fetch_json(url)
            return _extract_usd_ars(data)
        except Exception as e:
            last_err = e

    raise RuntimeError(f"FX fetch failed (both providers). Last error: {last_err}")
