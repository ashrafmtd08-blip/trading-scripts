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
├── build_report.py             # renders second_entry_report.html
├── build_tf_report.py          # renders second_entry_timeframe_report.html
├── fetch_data.py               # pulls H4 CSVs (not committed)
├── fetch_m1_data.py            # pulls M1 parquet (not committed)
├── backtest_results.json       # H4 results + equity curve
├── timeframe_results.json      # timeframe-study results
├── *.html                      # the two visual reports
└── data/                       # fetched OHLC (gitignored)
```

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
| Tradeable signals | 1,265 (1,196 resolved, 69 cancelled) |
| Win rate @ 2R | **45.8%** (break-even 33.3%) |
| Expectancy | **+0.37R / trade** |
| Total return | **+448R** |
| Profit factor | 1.69 |
| Max drawdown | −17R |

Every pair posted positive expectancy (GBPUSD best at +0.53R, USDCAD weakest at
+0.26R). Full per-pair table and the equity curve are in the HTML report.

> **Methodology note:** trades are held to their real SL/TP (a pending order
> expires only if unfilled within 12 bars). An earlier version time-capped every
> trade at 12 bars, which systematically discarded winners-in-progress (the 2R
> target is further than the 1R stop, so it takes longer to reach) and understated
> the edge. These numbers use the corrected run-to-resolution engine.

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
