# Second Entry (H2/L2) — TradingView indicator

`SecondEntry_H2L2.pine` — a Pine Script v5 **indicator** that marks BUY (H2) and
SELL (L2) signals and draws each trade's **Entry / SL / TP**. Same rules as the
Python/MQL5 versions (EMA-20 trend, failed first break, deeper pull-back, second
break, gated by bar quality + EMA-touch + trend/ADX + a 3-candle Fair Value Gap,
fixed 2R target).

## Install

1. Open your chart on **TradingView** → bottom panel **Pine Editor**.
2. **Open → New indicator**, delete the template, and paste the contents of
   `SecondEntry_H2L2.pine`.
3. Click **Save**, then **Add to chart**.
4. A ▲ (teal) prints below a bar on a BUY signal, a ▼ (red) above a bar on a
   SELL, each with dashed **Entry**, red **SL** and green **TP** lines + a label.

## What it draws

- **▲ H2 / ▼ L2** markers at the confirmed signal bar.
- **Entry** (grey dashed) = second-break bar's high + buffer (buy) / low − buffer (sell).
- **SL** (red) = the FVG impulse candle's low/high ∓ buffer.
- **TP** (green) = fixed 2R from entry.
- **EMA(20)** line for trend context.

## Inputs

Match the backtest defaults: EMA 20, ADX 14 (min 15), trend lookback 5, close
ratio 0.50, EMA-touch 300 points, buffer 20 points, RR 2.0. "Points" use the
symbol's `mintick`, so they scale across FX / Gold / Crypto automatically.

## Non-repainting

The signal only prints once the **FVG-confirming bar closes** (1–2 bars after the
second-break bar) — the same moment a live bot could act. Entry/SL/TP come from
the already-closed second-break bar, so they never redraw. (Signals evaluate on
bar close; don't judge a still-forming bar.)

## Alerts

Two alert conditions are included — **"Second Entry BUY (H2)"** and
**"…SELL (L2)"**. Right-click the chart → Add alert → Condition → this indicator.

## Notes

- This is a **signal indicator**, not a `strategy{}` — it shows setups; it does not
  simulate a backtest equity curve inside TradingView. Use `strategy_tester.py`
  (Python) or the MQL5 EA's Strategy Tester for performance stats with costs.
- It hasn't been compiled by its author (no Pine environment here). If TradingView
  flags a line on save, paste the error and it'll be a one-line fix.
