# SecondEntry_H2L2_EA.mq5 — native MT5 Expert Advisor

A pure-MQL5 implementation of the Second Entry (H2/L2) strategy — the same rules
as the Python engine (`second_entry_backtest.py`), so it can run **inside MT5**
without Python, be **backtested in the Strategy Tester** with real tick data and
spread, and run on MT5's **built-in VPS**.

## Install & compile

1. In MetaTrader 5: **File → Open Data Folder** → `MQL5\Experts\`.
2. Copy `SecondEntry_H2L2_EA.mq5` there.
3. Open it in **MetaEditor** and press **F7** (Compile). Fix nothing — it should
   compile clean; if your build flags an API name, tell me the line.
4. In MT5, refresh the Navigator → drag the EA onto a chart. Tick **Allow
   Algo Trading**.

## Test before trusting (do this first)

- **Strategy Tester** (Ctrl+R): pick the symbol/timeframe (e.g. XAUUSD M5 — the
  strategy's origin, or a major on M3), model **"Every tick based on real ticks"**,
  and run. This is the honest test — it includes real spread.
- Compare its trade count/win-rate to the Python backtest on the same period.
  They won't match to the trade (tick vs bar fills, real spread) but should be in
  the same ballpark.

## Inputs (defaults = the backtested config)

| Input | Default | Meaning |
|---|---|---|
| `InpRiskPercent` | 1.0 | % of balance risked per trade |
| `InpRR` | 2.0 | reward:risk (fixed TP) |
| `InpEmaTouchPoints` | 300 | pull-back must reach within N **points** of the EMA |
| `InpBufferPoints` | 20 | entry/SL buffer in points |
| `InpAdxMin` | 15 | min ADX to trade |
| `InpExpiryBars` | 12 | pending order expires after N bars |
| `InpBreakEvenAtR` | 1.0 | move SL to entry at +1R |
| `InpMaxSpreadPts` | 25 | skip if spread wider than this |
| `InpOnePerSide` | true | one order/position per side |
| `InpMagic` | 250707 | isolates this EA's orders |

Point-based inputs use the symbol's own `_Point`, so they scale correctly across
FX, Gold and Crypto automatically.

## Notes / caveats

- **Not compiled or tested by its author** (no MetaEditor in the build
  environment). Compile it yourself and verify in the Strategy Tester + on demo.
- Detection mirrors the Python engine bar-for-bar (H1/H2, deeper pull-back, FVG,
  ADX/trend/quality/EMA-touch gates), but **fills differ**: live/tester fills are
  tick-based, the Python study is bar-based with no costs.
- Uses `ORDER_TIME_SPECIFIED` for pending expiry; if your broker only allows GTC
  pendings the order send will fail (logged) — tell me and I'll switch to a
  manual bar-count expiry.
- Python bot vs this EA: the **Python bot guarantees live logic == the backtest**;
  the **EA is more robust for 24/7** and Strategy-Tester-able. Use whichever fits;
  verify the EA reproduces the Python signals before trusting it.
