"""Fetch H4 OHLC for the FX majors into data/forex/.

The raw CSVs (~18 MB) are not committed. This pulls them from the public
`tohaitrieu/market-history` dataset via a shallow git clone, then copies just
the six H4 files the backtest needs. Run once before second_entry_backtest.py:

    python3 fetch_data.py
"""
import os
import shutil
import subprocess
import tempfile

MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD"]
SOURCE = "https://github.com/tohaitrieu/market-history.git"
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "data", "forex")


def have_all() -> bool:
    return all(
        os.path.exists(os.path.join(DEST, s, f"{s}-H4.csv")) for s in MAJORS
    )


def fetch() -> None:
    if have_all():
        print("Data already present in data/forex/ — nothing to do.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Cloning {SOURCE} (shallow) ...")
        subprocess.run(
            ["git", "clone", "--depth", "1", SOURCE, tmp],
            check=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        src_root = os.path.join(tmp, "data", "forex")
        for sym in MAJORS:
            src = os.path.join(src_root, sym, f"{sym}-H4.csv")
            dst_dir = os.path.join(DEST, sym)
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, os.path.join(dst_dir, f"{sym}-H4.csv"))
            print(f"  {sym}-H4.csv")
    print("Done.")


if __name__ == "__main__":
    fetch()
