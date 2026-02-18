import datetime
import requests
from db import get_connection

API_URL = "https://open.er-api.com/v6/latest/USD"

def get_today_rate() -> float:
    today = datetime.date.today().isoformat()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT usd_ars FROM fx_rates WHERE date=?", (today,))
    row = cur.fetchone()
    if row:
        conn.close()
        return float(row[0])

    res = requests.get(API_URL, timeout=10)
    res.raise_for_status()
    data = res.json()

    usd_ars = float(data["rates"]["ARS"])
    cur.execute("INSERT INTO fx_rates (date, usd_ars) VALUES (?, ?)", (today, usd_ars))

    conn.commit()
    conn.close()
    return usd_ars
