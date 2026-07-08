"""
Second Entry (H2/L2) backtest for XAUUSD (Gold) and BTCUSD, on M5 and M3.

The strategy was originally developed on Gold M5, so this checks it on Gold and
Bitcoin with the same engine used for the FX study.

Data:
  * M5 comes bundled (data/xau_btc/<SYM>_M5.csv), from the public
    No-Trade-No-Life/Yuan-Public-Data OHLC dataset (clean 5-minute candles).
  * M3 needs 1-minute data, which isn't freely available for these instruments.
    Drop a 1-minute CSV at data/xau_btc/<SYM>_M1.csv (columns: time/Time, open,
    high, low, close) — e.g. exported from your own MT5 via export_m1.py — and
    this script will build BOTH M3 and M5 from it. Without it, only bundled M5 runs.

Point sizes for Gold/BTC are handled in second_entry_backtest.point_size:
Gold point = $0.01 (300-pt EMA-touch = $3, matching the original Gold-M5 tuning);
BTC point = $1 (300-pt touch = $300, a sane fraction of price).

No spread/slippage/commission modelled (same methodology as the other studies).
"""
from __future__ import annotations

import os

import pandas as pd

import second_entry_backtest as se

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "xau_btc")
SYMBOLS = ["XAUUSD", "BTCUSD"]


def _load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = "time" if "time" in df.columns else df.columns[0]
    df["Time"] = pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    df = df[["Time", "Open", "High", "Low", "Close"]].dropna()
    df = df.drop_duplicates(subset="Time").sort_values("Time").reset_index(drop=True)
    return df


def _resample(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
    r = (m1.set_index("Time")
           .resample(rule)
           .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
           .dropna(subset=["Open"]).reset_index())
    return r


def frames_for(sym: str) -> dict:
    """Return {tf_label: dataframe} for whatever data is available."""
    out = {}
    m1p = os.path.join(DATA, f"{sym}_M1.csv")
    m5p = os.path.join(DATA, f"{sym}_M5.csv")
    if os.path.exists(m1p):
        m1 = _load_csv(m1p)
        out["M3"] = _resample(m1, "3min")
        out["M5"] = _resample(m1, "5min")          # from same M1 => consistent
    elif os.path.exists(m5p):
        out["M5"] = _load_csv(m5p)                 # bundled M5 only; M3 needs M1
    return out


def main() -> None:
    hdr = (f"{'Symbol':8} {'TF':4} {'Bars':>8} {'Trades':>7} {'Win':>4} {'Loss':>5} "
           f"{'Win%':>6} {'ExpR':>7} {'TotR':>8} {'PF':>5}  RejT/E/Q/F")
    print("=" * len(hdr))
    print(f"Second Entry (H2/L2) — XAUUSD & BTCUSD  |  RR={se.INP_RR}  |  "
          f"break-even {100/(1+se.INP_RR):.1f}%")
    print("=" * len(hdr))
    print(hdr); print("-" * len(hdr))

    missing_m3 = []
    for sym in SYMBOLS:
        frames = frames_for(sym)
        if not frames:
            print(f"{sym:8} (no data found in data/xau_btc/)")
            continue
        for tf in ("M3", "M5"):
            if tf not in frames:
                if tf == "M3":
                    missing_m3.append(sym)
                continue
            df = frames[tf]
            st = se.backtest(df.copy(), sym)
            print(f"{sym:8} {tf:4} {st.bars:8d} {st.valid:7d} {st.wins:4d} "
                  f"{st.losses:5d} {st.win_rate:5.1f}% {st.expectancy:+6.2f}R "
                  f"{st.r_sum:+7.1f}R {st.profit_factor:5.2f}  "
                  f"{st.rej_trend}/{st.rej_ema}/{st.rej_quality}/{st.rej_fvg}")
        print("-" * len(hdr))

    print(f"Window: XAUUSD ~2023-08→2024-04, BTCUSD ~2023-10→2024-04 (bundled M5).")
    if missing_m3:
        print(f"\nM3 not run for {', '.join(missing_m3)}: needs 1-minute data. "
              f"Add data/xau_btc/<SYM>_M1.csv (e.g. via export_m1.py on your MT5) "
              f"and re-run — it will build M3 (and broker-accurate M5) automatically.")
    print("No spread/slippage/commission modelled.")


if __name__ == "__main__":
    main()
