"""
Second Entry (H2/L2) — M5 execution (compatibility shim).

The canonical execution module is now `second_entry_execution.py`, which defaults
to **M3** (the most profitable timeframe in the corrected study). This shim keeps
the M5 entry point working: it re-exports the same detection and pins the
timeframe to M5, a cost-robust middle ground (wider ~12-pip stops vs M3's ~11).

    from second_entry_m5_strategy import detect_signals, latest_signal, build_m5
"""
from __future__ import annotations

import pandas as pd

from second_entry_execution import (
    OrderPlan, detect_signals as _detect_signals,
    latest_signal as _latest_signal, build_bars,
)

TIMEFRAME = "M5"


def detect_signals(df: pd.DataFrame, symbol: str) -> list[OrderPlan]:
    return _detect_signals(df, symbol, tf=TIMEFRAME)


def latest_signal(df: pd.DataFrame, symbol: str, max_age_bars: int = 1):
    return _latest_signal(df, symbol, tf=TIMEFRAME, max_age_bars=max_age_bars)


def build_m5(symbol: str) -> pd.DataFrame:
    return build_bars(symbol, rule="5min")


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    df = build_m5(sym)
    sigs = detect_signals(df, sym)
    print(f"{sym} M5: {len(df):,} bars, {len(sigs)} valid H2/L2 signals")
    for s in sigs[-5:]:
        print(f"  {s.time}  {s.side:4}  entry={s.entry}  stop={s.stop}  "
              f"target={s.target}  risk={s.risk_pips}p")
