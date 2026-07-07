# Second Entry (H2/L2) — FX Majors Backtest

Backtest of the **Second Entry (H2/L2)** pull-back strategy (from
`SecondEntry_Session_Notes.md`) across six major FX pairs on **H4** data,
2010-01 → 2026-02.

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
| Tradeable signals | 837 (768 resolved, 69 cancelled) |
| Win rate @ 2R | **46.9%** (break-even 33.3%) |
| Expectancy | **+0.41R / trade** |
| Total return | **+312R** |
| Profit factor | 1.76 |
| Max drawdown | −9R |

Every pair posted positive expectancy (GBPUSD best at +0.64R, USDCAD weakest at
+0.18R). Full per-pair table and the equity curve are in the HTML report.

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
