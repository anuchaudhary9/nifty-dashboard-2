"""
Fetches free NSE data and stores it in SQLite:
1. Live option chain (NIFTY) -> PCR, OI by strike, support/resistance
2. Participant-wise Open Interest (FII/DII/Pro/Client) -> daily CSV, EOD, ~1 day lag

Uses nsepythonserver, which is built specifically to work from cloud
environments (GitHub Actions, AWS, Colab, etc.) where NSE often blocks
plain requests.

Run this once a day (e.g. via GitHub Actions cron, after market close ~4pm IST)
or manually whenever you want a fresh snapshot.
"""

import os
import sqlite3
import io
import time
import requests
import pandas as pd
from datetime import date

DB_PATH = "data/nifty.db"
os.makedirs("data", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/option-chain",
}


def fetch_option_chain(symbol="NIFTY"):
    """Uses nsepythonserver, built for cloud/server environments where
    NSE blocks plain requests."""
    from nsepythonserver import nse_optionchain_scrapper

    data = nse_optionchain_scrapper(symbol)
    if not data or "records" not in data:
        raise ValueError("nsepythonserver returned empty/invalid response")

    records = data["records"]["data"]
    spot = data["records"]["underlyingValue"]
    expiry = data["records"]["expiryDates"][0]

    rows = []
    for row in records:
        strike = row.get("strikePrice")
        ce = row.get("CE", {})
        pe = row.get("PE", {})
        if row.get("expiryDate") != expiry:
            continue
        rows.append({
            "date": str(date.today()),
            "symbol": symbol,
            "expiry": expiry,
            "strike": strike,
            "call_oi": ce.get("openInterest", 0),
            "call_oi_chg": ce.get("changeinOpenInterest", 0),
            "call_ltp": ce.get("lastPrice", 0),
            "put_oi": pe.get("openInterest", 0),
            "put_oi_chg": pe.get("changeinOpenInterest", 0),
            "put_ltp": pe.get("lastPrice", 0),
            "spot": spot,
        })
    return pd.DataFrame(rows)


def get_nse_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://www.nseindia.com", timeout=10)
    time.sleep(1)
    return s


def fetch_participant_oi():
    s = get_nse_session()
    url = "https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{}.csv"
    for days_back in range(0, 6):
        d = pd.Timestamp.today().normalize() - pd.Timedelta(days=days_back)
        if d.weekday() >= 5:
            continue
        fname = url.format(d.strftime("%d%m%Y"))
        r = s.get(fname, timeout=10)
        if r.status_code == 200 and len(r.content) > 500:
            df = pd.read_csv(io.StringIO(r.content.decode("utf-8")), skiprows=1)
            df["report_date"] = d.strftime("%Y-%m-%d")
            return df
    return pd.DataFrame()


def save(df, table):
    if df.empty:
        print(f"[skip] no data for {table}")
        return
    conn = sqlite3.connect(DB_PATH)
    df.to_sql(table, conn, if_exists="append", index=False)
    conn.close()
    print(f"[ok] saved {len(df)} rows to {table}")


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.close()

    try:
        oc = fetch_option_chain("NIFTY")
        save(oc, "option_chain")
    except Exception as e:
        print(f"[error] option chain fetch failed: {e}")

    try:
        poi = fetch_participant_oi()
        save(poi, "participant_oi")
    except Exception as e:
        print(f"[error] participant OI fetch failed: {e}")
