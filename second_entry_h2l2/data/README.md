# FX historical data

H4 OHLC candles for six major pairs, used by `second_entry_backtest.py`.

- **Format:** `Asset,TimeFrame,Time,Open,High,Low,Close,Year,Quarter,Month,Week`
- **Source:** public dataset [`tohaitrieu/market-history`](https://github.com/tohaitrieu/market-history)
  (`data/forex/<PAIR>/<PAIR>-H4.csv`).
- **Coverage:** each file runs to 2026-02. Rows before ~2004 are flat synthetic
  backfill (OHLC all equal) and are dropped at load time; the backtest window
  starts 2010-01-01.
- **Pairs:** EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD.

This is broker-agnostic reference data with no spread/commission attached, which
is why the backtest models none. Validate against your own broker's feed before
trusting fills.
