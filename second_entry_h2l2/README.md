# Second Entry (H2/L2) — FX Majors Backtest

Backtest of the **Second Entry (H2/L2)** pull-back strategy (from
`SecondEntry_Session_Notes.md`) across the major FX pairs. Self-contained —
everything for this study lives in this folder; run all commands from here
(`cd second_entry_h2l2`).

Two studies are included:
- **H4 majors**, 2010→2026 (`second_entry_report.html`).
- **Intraday timeframe comparison** M3 vs M5 vs M15, 2015→2025
  (`second_entry_timeframe_report.html`) — M3 most profitable on the raw edge
  (highest total R *and* expectancy), though it has the tightest stops so is the
  most cost-sensitive.

### Layout
```
second_entry_h2l2/
├── second_entry_backtest.py    # strategy engine + H4 backtest
├── second_entry_strategy.json  # portable strategy spec (rules + params + results)
├── timeframe_backtest.py       # M1→M3/M5/M15 resample + comparison
├── second_entry_execution.py   # live signal generator — DEFAULT TIMEFRAME M3
├── second_entry_m5_strategy.py # thin M5 shim over the execution module
├── mt5_live_bot.py             # MetaTrader 5 auto-trading bot (defaults to M3)
├── MT5_BOT_GUIDE.md            # setup / run / safety guide for the bot
├── build_report.py             # renders second_entry_report.html
├── build_tf_report.py          # renders second_entry_timeframe_report.html
├── fetch_data.py               # pulls H4 CSVs (not committed)
├── fetch_m1_data.py            # pulls M1 parquet (not committed)
├── backtest_results.json       # H4 results + equity curve
├── timeframe_results.json      # timeframe-study results
├── *.html                      # the two visual reports
└── data/                       # fetched OHLC (gitignored)
```

**Default execution timeframe is M3** (highest total R *and* expectancy in the
corrected study). The live bot trades M3 out of the box; set `EXEC_TF` in
`mt5_live_bot.py` to `"M5"`/`"M15"` for a more spread-robust run. See
`MT5_BOT_GUIDE.md`.

## Strategy (as implemented)

- **Trend:** close above EMA(20) = bull, below = bear.
- **Leg 1 → H1:** first break of the prior bar's high during a pull-back — recorded, not traded.
- **Leg 2 → H2:** after a *deeper* pull-back low than the one before H1, the next up-break is the signal, gated by:
  - **Bar quality** — closes with the break, in the upper/lower half of its range (`InpClosePosRatio = 0.50`).
  - **EMA touch** — the pull-back came within `InpEmaTouchPoints = 300` points of the EMA.
  - **Trend filter** — EMA slope over `InpTrendLookback = 5` bars + `ADX ≥ 15`.
  - **FVG** — the H2 candle, or the one right after it, is the impulse (middle) bar of a 3-candle Fair Value Gap.
- Bear side (L1/L2) is the mirror.
- **Entry** buy-stop at H2 high + buffer / sell-stop at L2 low − buffer.
- **SL** the FVG impulse candle's low/high ∓ buffer. **TP** fixed `InpRR = 2.0` (2R).

Pending orders expire after `InpExpiryBars = 12` bars. Win/loss is a forward
replay against real bar highs/lows (SL-first on ties). **No spread, slippage or
commission is modelled** — matching the indicator's on-chart methodology.

## Results (aggregate)

| Metric | Value |
|---|---|
| Tradeable signals | 1,265 (1,169 resolved, 96 cancelled) |
| Win rate @ 2R | **45.8%** (break-even 33.3%) |
| Expectancy | **+0.37R / trade** |
| Total return | **+436R** |
| Profit factor | 1.69 |
| Max drawdown | −14R |

Every pair posted positive expectancy (GBPUSD best at +0.50R, USDCAD weakest at
+0.27R). Full per-pair table and the equity curve are in the HTML report.

### Gold &amp; Bitcoin (`xau_btc_backtest.py`)

The strategy was born on Gold M5, so it's also tested on XAUUSD and BTCUSD
(bundled M5 & M15 data, ~2022–2024):

| Symbol | TF | Trades | Win% | Expectancy | Total R | PF |
|---|---|---|---|---|---|---|
| XAUUSD | M5 | 299 | 50.9% | +0.53R | +147R | 2.07 |
| XAUUSD | M15 | 112 | 45.3% | +0.36R | +38R | 1.66 |
| BTCUSD | M5 | 253 | 56.0% | +0.68R | +164R | 2.55 |
| BTCUSD | M15 | 104 | 55.2% | +0.66R | +63R | 2.47 |

**M3** for these two needs 1-minute data, which isn't freely available for
Gold/BTC. Export M1 from your own MT5 with `export_m1.py` (writes
`data/xau_btc/<SYM>_M1.csv`); `xau_btc_backtest.py` then builds **M3 and M5**
from it automatically. Gold/BTC point sizes are handled in `point_size()`
(Gold $0.01, BTC $1).

> **Methodology notes:** (1) trades are held to their real SL/TP (a pending order
> expires only if unfilled within 12 bars) — an earlier version time-capped every
> trade at 12 bars and understated the edge; these use the run-to-resolution engine.
> (2) **No look-ahead / no repaint:** the FVG is a fixed 3-candle pattern, and an
> order can only fill from **two bars after the signal** (after the gap-confirming
> bar closes). Removing an earlier 1-bar fill look-ahead moved results by <3% —
> and slightly *raised* the intraday numbers — confirming the edge isn't an
> artifact of it.

## Files

- `second_entry_backtest.py` — strategy engine + forward-replay backtester (prints the table, writes `backtest_results.json`).
- `build_report.py` — renders the self-contained `second_entry_report.html` from the JSON.
- `backtest_results.json` — machine-readable per-pair stats + equity curve.
- `second_entry_report.html` — visual report.
- `fetch_data.py` — pulls the H4 CSVs from the public source (data is not committed; see `data/README.md`).

## Run

```bash
pip install pandas numpy
python3 fetch_data.py              # pulls the six H4 CSVs (~18 MB, not committed)
python3 second_entry_backtest.py   # runs backtest, writes JSON
python3 build_report.py            # regenerates the HTML report
```

`second_entry_backtest.py` auto-fetches the data on first run if `data/forex/`
is empty, so the explicit `fetch_data.py` step is optional.

## Caveats

Frictionless results are an upper bound. Inputs were originally tuned on Gold M5;
here they are mapped to H4 FX. Validate on a demo / Strategy Tester with real
costs before risking capital.
