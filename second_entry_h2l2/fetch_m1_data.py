"""Fetch M1 (1-minute) OHLCV parquet for the majors into data/m1_parquet/.

Used by timeframe_backtest.py to build M3/M5/M15 by resampling. Each file is
~78 MB and is NOT committed. Source: public `Kanyal-HarsH/forex-algo-trading`
dataset (2015-2025).

    python3 fetch_m1_data.py
"""
import os
import urllib.request

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"]
BASE = ("https://raw.githubusercontent.com/Kanyal-HarsH/forex-algo-trading"
        "/main/data/parquet")
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "data", "m1_parquet")


def fetch() -> None:
    os.makedirs(DEST, exist_ok=True)
    for sym in PAIRS:
        path = os.path.join(DEST, f"{sym}.parquet")
        if os.path.exists(path):
            continue
        url = f"{BASE}/{sym}_2015_2025.parquet"
        print(f"Downloading {sym} ...")
        urllib.request.urlretrieve(url, path)
        print(f"  {os.path.getsize(path)/1e6:.0f} MB")
    print("Done.")


if __name__ == "__main__":
    fetch()
