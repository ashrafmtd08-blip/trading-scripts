"""
Export 1-minute history from YOUR MetaTrader 5 terminal to CSV.

Run this on Windows (with MT5 open + logged in) to pull M1 bars for the symbols
you want. It writes data/xau_btc/<LABEL>_M1.csv in the format xau_btc_backtest.py
expects — which then builds BOTH M3 and M5 from it (so you can finally run the
M3 study for Gold/BTC on your broker's own data).

    python export_m1.py

Edit SYMBOL_MAP so the values match your broker's EXACT symbol names (they vary,
e.g. "XAUUSD", "GOLD", "BTCUSD", "BTCUSD.a"). The key is the file label used by
the backtest; the value is what your broker calls it.
"""
from __future__ import annotations

import os

# file label  ->  your broker's exact symbol name
SYMBOL_MAP = {
    "XAUUSD": "XAUUSD",
    "BTCUSD": "BTCUSD",
}
M1_BARS = 200_000          # ~5 months of 1-minute bars per symbol

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "xau_btc")


def main() -> int:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 not installed (Windows only): pip install MetaTrader5")
        return 1
    import pandas as pd

    if not mt5.initialize():
        print("initialize() failed:", mt5.last_error())
        return 1
    os.makedirs(OUT, exist_ok=True)

    for label, broker_sym in SYMBOL_MAP.items():
        if not mt5.symbol_select(broker_sym, True):
            print(f"  ✗ {label}: broker symbol '{broker_sym}' not found — fix SYMBOL_MAP.")
            continue
        rates = mt5.copy_rates_from_pos(broker_sym, mt5.TIMEFRAME_M1, 0, M1_BARS)
        if rates is None or len(rates) == 0:
            print(f"  ✗ {label}: no M1 data returned ({mt5.last_error()}).")
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df[["time", "open", "high", "low", "close"]]
        path = os.path.join(OUT, f"{label}_M1.csv")
        df.to_csv(path, index=False)
        print(f"  ✓ {label}: wrote {len(df):,} M1 bars "
              f"({df['time'].iloc[0]} → {df['time'].iloc[-1]}) -> {os.path.basename(path)}")

    mt5.shutdown()
    print("\nDone. Now run:  python xau_btc_backtest.py   (it will include M3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
