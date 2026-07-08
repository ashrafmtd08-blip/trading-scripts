"""
Second Entry (H2/L2) pullback strategy — vectorized-ish backtester for FX majors.

Implements the strategy documented in SecondEntry_Session_Notes.md:

  - Trend context: close above EMA(20) = bull, below = bear.
  - Break test ("body or wick"): a bar whose high > prior bar's high is a bull
    break (mirror for bear).
  - Leg 1 -> H1: first up-break during a pullback (recorded, NOT traded).
  - Leg 2 -> H2: valid only after price makes a DEEPER pullback low than the
    low that preceded H1; the next up-break bar is the signal, gated by:
      * bar quality  - closes with the break, in the upper/lower half of range
      * EMA touch    - the pullback came within InpEmaTouchPoints of the EMA
      * trend filter - EMA slope over InpTrendLookback bars + ADX >= InpAdxMinLevel
      * FVG          - the H2 candle OR the candle right after it is the impulse
                       (middle) bar of a 3-candle Fair Value Gap
  - Bear side (L1/L2) is the exact mirror.
  - Entry: H2 high + buffer (buy stop) / L2 low - buffer (sell stop).
  - SL:    low/high of the actual FVG impulse candle -/+ buffer.
  - TP:    fixed InpRR x risk (default 2.0 = 2RR).

The win/loss engine is a forward replay against real bar highs/lows (does SL or
TP hit first), matching the indicator's on-chart backtest. As the notes state,
no spread / slippage / commission is modeled. The EA-only extras (1% risk
sizing, break-even at 1R) are NOT part of this win-rate methodology.

Data: H4 OHLC for the majors (finest common timeframe in the free dataset used).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Strategy parameters (defaults mirror the "loosened" values from the notes)
# --------------------------------------------------------------------------- #
INP_EMA_PERIOD      = 20
INP_ADX_PERIOD      = 14
INP_ADX_MIN_LEVEL   = 15.0     # ADX >= this to allow a trade
INP_TREND_LOOKBACK  = 5        # bars for EMA-slope trend check
INP_CLOSE_POS_RATIO = 0.50     # close must sit in upper/lower half of the range
INP_EMA_TOUCH_PTS   = 300      # pullback must come within this many points of EMA
INP_BUFFER_PTS      = 20       # entry/SL buffer, in points
INP_RR              = 2.0      # reward:risk (fixed TP)
INP_EXPIRY_BARS     = 12       # pending buy/sell-stop auto-cancels if not FILLED in N bars
INP_MAX_HOLD_BARS   = 0        # once filled, hold to SL/TP; 0 = until end of data (no time stop)

START_DATE = "2010-01-01"      # backtest window start (data runs to 2026-02)


def point_size(symbol: str) -> float:
    """MT5-style point per instrument. FX 5-dp; JPY 3-dp; Gold 2-dp ($0.01);
    BTC uses a $1 point so the point-based EMA-touch/buffer stay a sane fraction
    of price (300 pts = $300 touch on ~$40k BTC, matching the Gold-M5 intent)."""
    if symbol.endswith("JPY"):
        return 0.001
    if symbol == "XAUUSD":
        return 0.01
    if symbol.startswith("BTC"):
        return 1.0
    return 0.00001


def pip_size(symbol: str) -> float:
    if symbol.endswith("JPY"):
        return 0.01
    if symbol == "XAUUSD":
        return 0.1
    if symbol.startswith("BTC"):
        return 1.0
    return 0.0001


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Wilder's ADX."""
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    # Wilder smoothing == EMA with alpha = 1/period
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=high.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=high.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
@dataclass
class Stats:
    symbol: str
    signals: int = 0
    wins: int = 0
    losses: int = 0
    cancelled: int = 0
    # rejection breakdown (Rej T/E/Q/F in the notes)
    rej_trend: int = 0
    rej_ema: int = 0
    rej_quality: int = 0
    rej_fvg: int = 0
    r_sum: float = 0.0            # sum of R over resolved trades
    bars: int = 0
    span_days: float = 0.0
    trades: list = field(default_factory=list)

    @property
    def resolved(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        return 100.0 * self.wins / self.resolved if self.resolved else 0.0

    @property
    def expectancy(self) -> float:
        return self.r_sum / self.resolved if self.resolved else 0.0

    @property
    def valid(self) -> int:
        """Tradeable signals that passed every gate (resolved + cancelled)."""
        return self.resolved + self.cancelled

    @property
    def trades_per_day(self) -> float:
        return self.valid / self.span_days if self.span_days else 0.0

    @property
    def profit_factor(self) -> float:
        gross_win = self.wins * INP_RR
        gross_loss = self.losses * 1.0
        return gross_win / gross_loss if gross_loss else float("inf")


# --------------------------------------------------------------------------- #
# Core backtest
# --------------------------------------------------------------------------- #
def backtest(df: pd.DataFrame, symbol: str,
             rr: float = INP_RR,
             ema_touch_pts: int = INP_EMA_TOUCH_PTS,
             adx_min: float = INP_ADX_MIN_LEVEL) -> Stats:
    """Run the H2/L2 detection + forward-replay on one symbol's OHLC frame."""
    pt = point_size(symbol)
    touch = ema_touch_pts * pt
    buffer = INP_BUFFER_PTS * pt

    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    e = ema(df["Close"], INP_EMA_PERIOD).to_numpy(float)
    a = adx(df["High"], df["Low"], df["Close"], INP_ADX_PERIOD).to_numpy(float)
    n = len(df)

    st = Stats(symbol=symbol)
    st.bars = n
    st.span_days = (df["Time"].iloc[-1] - df["Time"].iloc[0]).total_seconds() / 86400.0

    warmup = max(INP_EMA_PERIOD, INP_ADX_PERIOD, INP_TREND_LOOKBACK) + 2

    def bar_quality_ok(j: int, bull: bool) -> bool:
        rng = h[j] - l[j]
        if rng <= 0:
            return False
        if bull:
            if c[j] <= o[j]:
                return False
            return (c[j] - l[j]) / rng >= INP_CLOSE_POS_RATIO
        else:
            if c[j] >= o[j]:
                return False
            return (h[j] - c[j]) / rng >= INP_CLOSE_POS_RATIO

    def trend_ok(j: int, bull: bool) -> bool:
        if np.isnan(a[j]) or a[j] < adx_min:
            return False
        slope = e[j] - e[j - INP_TREND_LOOKBACK]
        return slope > 0 if bull else slope < 0

    def find_fvg_impulse(j: int, bull: bool):
        """H2 candle (j) OR the candle right after (j+1) must be the impulse/
        middle bar of a 3-candle FVG. Returns the impulse index or None."""
        for mid in (j, j + 1):
            if mid - 1 < 0 or mid + 1 >= n:
                continue
            if bull:
                # bullish gap: low[mid+1] > high[mid-1]
                if l[mid + 1] > h[mid - 1]:
                    return mid
            else:
                # bearish gap: high[mid+1] < low[mid-1]
                if h[mid + 1] < l[mid - 1]:
                    return mid
        return None

    def replay(entry: float, sl: float, tp: float, start: int, bull: bool):
        """Forward-replay a pending stop order. Two decoupled horizons:
        the order must FILL within INP_EXPIRY_BARS bars (else 'cancel'); once
        filled it is held to SL or TP with no time stop (bounded only by the end
        of data, or INP_MAX_HOLD_BARS if > 0). Returns ('win'|'loss'|'cancel'
        |'open', R)."""
        # phase 1 — wait for the stop to trigger within the expiry window
        fill_k = None
        for k in range(start, min(start + INP_EXPIRY_BARS + 1, n)):
            if (bull and h[k] >= entry) or (not bull and l[k] <= entry):
                fill_k = k
                break
        if fill_k is None:
            return "cancel", 0.0
        # phase 2 — hold the filled trade until SL or TP (SL-first on ties)
        end = n if INP_MAX_HOLD_BARS <= 0 else min(n, fill_k + INP_MAX_HOLD_BARS + 1)
        for k in range(fill_k, end):
            if bull:
                hit_sl = l[k] <= sl
                hit_tp = h[k] >= tp
            else:
                hit_sl = h[k] >= sl
                hit_tp = l[k] <= tp
            if hit_sl:            # SL-first if both touched in one bar (conservative)
                return "loss", -1.0
            if hit_tp:
                return "win", rr
        return "open", 0.0        # unresolved only at the very end of the data

    def scan(bull: bool):
        i = warmup
        while i < n - 2:
            regime = (c[i] > e[i]) if bull else (c[i] < e[i])
            if not regime:
                i += 1
                continue

            # --- pullback must start: a bar making a lower-low (bull) ------- #
            started = (l[i] < l[i - 1]) if bull else (h[i] > h[i - 1])
            if not started:
                i += 1
                continue

            pb_ext = l[i] if bull else h[i]          # running pullback extreme
            pb_gap = (l[i] - e[i]) if bull else (e[i] - h[i])  # dist to EMA (signed)
            h1_seen = False
            h1_ref = None
            deeper = False
            j = i + 1
            resolved = False

            while j < n - 1:
                # keep regime; abandon if trend flips hard
                if (bull and c[j] < e[j] - touch) or (not bull and c[j] > e[j] + touch):
                    break

                # update pullback extreme + EMA gap while price is pulling back
                if bull:
                    if l[j] < pb_ext:
                        pb_ext = l[j]
                    pb_gap = min(pb_gap, l[j] - e[j])
                else:
                    if h[j] > pb_ext:
                        pb_ext = h[j]
                    pb_gap = min(pb_gap, e[j] - h[j])

                up_break = (h[j] > h[j - 1]) if bull else (l[j] < l[j - 1])

                if up_break and not h1_seen:
                    # Leg 1 -> H1 (recorded, not traded)
                    h1_seen = True
                    h1_ref = pb_ext
                    j += 1
                    continue

                if h1_seen and not deeper:
                    # need a DEEPER pullback low than the pre-H1 extreme
                    if (bull and pb_ext < h1_ref) or (not bull and pb_ext > h1_ref):
                        deeper = True

                if up_break and h1_seen and deeper:
                    # ---- H2/L2 candidate: run the gates -------------------- #
                    st.signals += 1

                    q_ok = bar_quality_ok(j, bull)
                    e_ok = pb_gap <= touch          # came within touch of EMA
                    t_ok = trend_ok(j, bull)
                    impulse = find_fvg_impulse(j, bull)
                    f_ok = impulse is not None

                    if not t_ok:
                        st.rej_trend += 1
                    elif not e_ok:
                        st.rej_ema += 1
                    elif not q_ok:
                        st.rej_quality += 1
                    elif not f_ok:
                        st.rej_fvg += 1
                    else:
                        # ---- valid signal: build the order ---------------- #
                        if bull:
                            entry = h[j] + buffer
                            sl = l[impulse] - buffer
                            risk = entry - sl
                            tp = entry + rr * risk
                        else:
                            entry = l[j] - buffer
                            sl = h[impulse] + buffer
                            risk = sl - entry
                            tp = entry - rr * risk

                        if risk > 0:
                            # start replay the bar AFTER the confirming bar
                            start = max(j, impulse) + 1
                            outcome, r = replay(entry, sl, tp, start, bull)
                            if outcome == "win":
                                st.wins += 1
                                st.r_sum += r
                            elif outcome == "loss":
                                st.losses += 1
                                st.r_sum += r
                            elif outcome == "cancel":
                                st.cancelled += 1
                            # 'open' (ran off end of data) is ignored
                            st.trades.append(
                                (df["Time"].iloc[j], "BUY" if bull else "SELL",
                                 round(entry, 5), round(sl, 5), round(tp, 5),
                                 outcome, r))

                    # reset: look for a fresh pullback after this signal
                    resolved = True
                    i = j + 1
                    break
                j += 1

            if not resolved:
                i += 1

    scan(bull=True)
    scan(bull=False)
    return st


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD"]

DATA_DIR = os.environ.get(
    "FX_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "data", "forex"),
)


def load_symbol(symbol: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, symbol, f"{symbol}-H4.csv")
    if not os.path.exists(path):
        # data isn't committed; pull it on first run
        import fetch_data
        fetch_data.fetch()
    df = pd.read_csv(path, parse_dates=["Time"])
    df = df[df["Time"] >= pd.Timestamp(START_DATE)].reset_index(drop=True)
    # drop any flat synthetic bars (OHLC all equal)
    flat = (df["Open"] == df["High"]) & (df["High"] == df["Low"]) & (df["Low"] == df["Close"])
    df = df[~flat].reset_index(drop=True)
    return df[["Time", "Open", "High", "Low", "Close"]]


def main() -> None:
    results = []
    for sym in MAJORS:
        df = load_symbol(sym)
        st = backtest(df, sym)
        results.append(st)

    # ----- per-pair table -------------------------------------------------- #
    hdr = (f"{'Pair':7} {'Trades':>6} {'Win':>4} {'Loss':>5} {'Win%':>6} "
           f"{'ExpR':>7} {'TotR':>8} {'PF':>5} {'Cxl':>4} {'T/day':>6}  RejT/E/Q/F")
    print("=" * len(hdr))
    print(f"Second Entry (H2/L2)  |  H4  |  {START_DATE} -> 2026-02  |  RR={INP_RR}")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    tot = Stats(symbol="ALL")
    for st in results:
        print(f"{st.symbol:7} {st.valid:6d} {st.wins:4d} {st.losses:5d} "
              f"{st.win_rate:5.1f}% {st.expectancy:+6.2f}R {st.r_sum:+7.1f}R "
              f"{st.profit_factor:5.2f} {st.cancelled:4d} {st.trades_per_day:6.2f}  "
              f"{st.rej_trend}/{st.rej_ema}/{st.rej_quality}/{st.rej_fvg}")
        tot.signals += st.signals
        tot.wins += st.wins
        tot.losses += st.losses
        tot.cancelled += st.cancelled
        tot.r_sum += st.r_sum
        tot.rej_trend += st.rej_trend
        tot.rej_ema += st.rej_ema
        tot.rej_quality += st.rej_quality
        tot.rej_fvg += st.rej_fvg
        tot.span_days = max(tot.span_days, st.span_days)

    print("-" * len(hdr))
    print(f"{'ALL':7} {tot.valid:6d} {tot.wins:4d} {tot.losses:5d} "
          f"{tot.win_rate:5.1f}% {tot.expectancy:+6.2f}R {tot.r_sum:+7.1f}R "
          f"{tot.profit_factor:5.2f} {tot.cancelled:4d} {'':6}  "
          f"{tot.rej_trend}/{tot.rej_ema}/{tot.rej_quality}/{tot.rej_fvg}")
    print("=" * len(hdr))

    be = 1.0 / (1.0 + INP_RR) * 100.0
    print(f"\nTotal candidate H2/L2 patterns scanned: {tot.signals} "
          f"(most filtered out by the gates below).")
    print(f"Break-even win rate at {INP_RR}RR = {be:.1f}%  "
          f"(expectancy positive above this).")
    print("TotR = sum of R over resolved trades; PF = profit factor "
          "(gross win R / gross loss R).")
    print("Rej T/E/Q/F = candidates killed by Trend / EMA-touch / Quality / FVG "
          "filter (first failing gate).")
    print("Methodology: forward-replay vs real H4 highs/lows; SL-first on ties; "
          "no spread/slippage/commission (per session notes).")

    _dump_json(results, tot)


def _dump_json(results: list[Stats], tot: Stats) -> None:
    """Write per-pair stats + a chronological, all-pairs equity curve (in R)."""
    all_trades = []
    for st in results:
        for t in st.trades:
            if t[5] in ("win", "loss"):
                all_trades.append((t[0], st.symbol, t[5], t[6]))
    all_trades.sort(key=lambda x: x[0])

    equity, cum = [], 0.0
    for ts, sym, outcome, r in all_trades:
        cum += r
        equity.append({"date": str(pd.Timestamp(ts).date()), "cum_r": round(cum, 1)})

    out = {
        "meta": {
            "strategy": "Second Entry (H2/L2)",
            "timeframe": "H4",
            "start": START_DATE,
            "rr": INP_RR,
            "adx_min": INP_ADX_MIN_LEVEL,
            "ema_touch_pts": INP_EMA_TOUCH_PTS,
            "breakeven_win_rate": round(100.0 / (1.0 + INP_RR), 1),
        },
        "pairs": [
            {
                "symbol": s.symbol, "trades": s.valid, "wins": s.wins,
                "losses": s.losses, "cancelled": s.cancelled,
                "win_rate": round(s.win_rate, 1), "expectancy": round(s.expectancy, 3),
                "total_r": round(s.r_sum, 1), "profit_factor": round(s.profit_factor, 2),
                "trades_per_day": round(s.trades_per_day, 3),
                "candidates": s.signals,
                "rej": {"trend": s.rej_trend, "ema": s.rej_ema,
                        "quality": s.rej_quality, "fvg": s.rej_fvg},
            }
            for s in results
        ],
        "all": {
            "trades": tot.valid, "wins": tot.wins, "losses": tot.losses,
            "cancelled": tot.cancelled, "win_rate": round(tot.win_rate, 1),
            "expectancy": round(tot.expectancy, 3), "total_r": round(tot.r_sum, 1),
            "profit_factor": round(tot.profit_factor, 2), "candidates": tot.signals,
        },
        "equity_curve": equity,
    }
    path = os.path.join(os.path.dirname(__file__), "backtest_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote machine-readable results -> {os.path.basename(path)} "
          f"({len(equity)} resolved trades on the equity curve).")


if __name__ == "__main__":
    main()
