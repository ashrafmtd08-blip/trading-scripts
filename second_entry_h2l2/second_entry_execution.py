"""
Second Entry (H2/L2) — execution module (default timeframe: M3).

Canonical, timeframe-agnostic signal generator for live/paper execution. Given a
stream of closed candles it emits an OrderPlan (side, entry, stop, target) for
each valid H2/L2 signal and can flag whether the most recently closed bar just
produced one. It reuses the exact detection rules and indicators from
second_entry_backtest.py, so signals line up 1:1 with that engine's tradeable
signals on the same bars.

Default execution timeframe is **M3** — the most profitable timeframe in the
corrected run-to-resolution study (highest total R *and* expectancy across the
seven majors). Override per call, or change EXEC_TIMEFRAME / EXEC_RESAMPLE_RULE.

    from second_entry_execution import latest_signal, detect_signals, build_bars
    df  = build_bars("EURUSD")            # M3 bars from the M1 parquet
    sig = latest_signal(df, "EURUSD")     # None, or an OrderPlan for the last bar

Data columns expected: Time, Open, High, Low, Close.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from second_entry_backtest import (
    ema, adx, point_size,
    INP_EMA_PERIOD, INP_ADX_PERIOD, INP_ADX_MIN_LEVEL, INP_TREND_LOOKBACK,
    INP_CLOSE_POS_RATIO, INP_EMA_TOUCH_PTS, INP_BUFFER_PTS, INP_RR,
)

# Default execution timeframe. M3 = 3-minute candles.
EXEC_TIMEFRAME     = "M3"
EXEC_RESAMPLE_RULE = "3min"

# Minutes per timeframe label — used by callers (e.g. the MT5 bot) for expiry.
TF_MINUTES = {"M1": 1, "M3": 3, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}


@dataclass
class OrderPlan:
    symbol: str
    timeframe: str
    time: str            # signal (H2/L2) bar close time
    side: str            # "BUY" or "SELL"
    entry: float         # buy-stop / sell-stop price
    stop: float          # protective stop
    target: float        # fixed-RR take profit
    risk_pips: float     # entry->stop distance in pips
    rr: float            # reward:risk
    bar_index: int       # index of the signal bar in the supplied frame

    def as_dict(self) -> dict:
        return asdict(self)


def _detect(df: pd.DataFrame, symbol: str, bull: bool, tf: str) -> list[OrderPlan]:
    """Scan one direction, emitting OrderPlans (mirrors the backtest engine)."""
    pt = point_size(symbol)
    pip = 0.01 if symbol.endswith("JPY") else 0.0001
    touch = INP_EMA_TOUCH_PTS * pt
    buffer = INP_BUFFER_PTS * pt

    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    e = ema(df["Close"], INP_EMA_PERIOD).to_numpy(float)
    a = adx(df["High"], df["Low"], df["Close"], INP_ADX_PERIOD).to_numpy(float)
    t = df["Time"]
    n = len(df)
    warmup = max(INP_EMA_PERIOD, INP_ADX_PERIOD, INP_TREND_LOOKBACK) + 2
    out: list[OrderPlan] = []

    def quality_ok(j: int) -> bool:
        rng = h[j] - l[j]
        if rng <= 0:
            return False
        if bull:
            return c[j] > o[j] and (c[j] - l[j]) / rng >= INP_CLOSE_POS_RATIO
        return c[j] < o[j] and (h[j] - c[j]) / rng >= INP_CLOSE_POS_RATIO

    def trend_ok(j: int) -> bool:
        if np.isnan(a[j]) or a[j] < INP_ADX_MIN_LEVEL:
            return False
        slope = e[j] - e[j - INP_TREND_LOOKBACK]
        return slope > 0 if bull else slope < 0

    def fvg_impulse(j: int):
        for mid in (j, j + 1):
            if mid - 1 < 0 or mid + 1 >= n:
                continue
            if bull and l[mid + 1] > h[mid - 1]:
                return mid
            if not bull and h[mid + 1] < l[mid - 1]:
                return mid
        return None

    i = warmup
    while i < n - 2:
        regime = (c[i] > e[i]) if bull else (c[i] < e[i])
        if not regime:
            i += 1
            continue
        started = (l[i] < l[i - 1]) if bull else (h[i] > h[i - 1])
        if not started:
            i += 1
            continue

        pb_ext = l[i] if bull else h[i]
        pb_gap = (l[i] - e[i]) if bull else (e[i] - h[i])
        h1_seen = deeper = False
        h1_ref = None
        j = i + 1
        resolved = False

        while j < n - 1:
            if (bull and c[j] < e[j] - touch) or (not bull and c[j] > e[j] + touch):
                break
            if bull:
                pb_ext = min(pb_ext, l[j]); pb_gap = min(pb_gap, l[j] - e[j])
            else:
                pb_ext = max(pb_ext, h[j]); pb_gap = min(pb_gap, e[j] - h[j])

            up_break = (h[j] > h[j - 1]) if bull else (l[j] < l[j - 1])

            if up_break and not h1_seen:
                h1_seen = True; h1_ref = pb_ext; j += 1; continue
            if h1_seen and not deeper:
                if (bull and pb_ext < h1_ref) or (not bull and pb_ext > h1_ref):
                    deeper = True
            if up_break and h1_seen and deeper:
                impulse = fvg_impulse(j)
                if trend_ok(j) and pb_gap <= touch and quality_ok(j) and impulse is not None:
                    if bull:
                        entry = h[j] + buffer; stop = l[impulse] - buffer
                        risk = entry - stop; target = entry + INP_RR * risk
                    else:
                        entry = l[j] - buffer; stop = h[impulse] + buffer
                        risk = stop - entry; target = entry - INP_RR * risk
                    if risk > 0:
                        out.append(OrderPlan(
                            symbol=symbol, timeframe=tf,
                            time=str(pd.Timestamp(t.iloc[j])),
                            side="BUY" if bull else "SELL",
                            entry=round(entry, 5), stop=round(stop, 5),
                            target=round(target, 5),
                            risk_pips=round(risk / pip, 1), rr=INP_RR,
                            bar_index=int(j)))
                resolved = True; i = j + 1; break
            j += 1
        if not resolved:
            i += 1
    return out


def detect_signals(df: pd.DataFrame, symbol: str,
                   tf: str = EXEC_TIMEFRAME) -> list[OrderPlan]:
    """All valid H2 (long) and L2 (short) order plans in the frame, time-ordered."""
    sigs = _detect(df, symbol, True, tf) + _detect(df, symbol, False, tf)
    sigs.sort(key=lambda s: s.bar_index)
    return sigs


def latest_signal(df: pd.DataFrame, symbol: str, tf: str = EXEC_TIMEFRAME,
                  max_age_bars: int = 1) -> OrderPlan | None:
    """The freshest signal whose bar is within `max_age_bars` of the last closed
    bar — i.e. an order you could still act on now. None if nothing fresh."""
    last = len(df) - 1
    fresh = [s for s in detect_signals(df, symbol, tf)
             if last - s.bar_index <= max_age_bars]
    return fresh[-1] if fresh else None


def build_bars(symbol: str, rule: str = EXEC_RESAMPLE_RULE) -> pd.DataFrame:
    """Resample the M1 parquet into the execution timeframe (default M3)."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "data", "m1_parquet", f"{symbol}.parquet")
    if not os.path.exists(path):
        import fetch_m1_data
        fetch_m1_data.fetch()
    m1 = pd.read_parquet(
        path, columns=["timestamp_utc", "open", "high", "low", "close", "volume"]
    ).set_index("timestamp_utc").sort_index()
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    r = m1.resample(rule).agg(agg).dropna(subset=["open"]).reset_index()
    return r.rename(columns={"timestamp_utc": "Time", "open": "Open", "high": "High",
                             "low": "Low", "close": "Close"})[
        ["Time", "Open", "High", "Low", "Close"]]


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    df = build_bars(sym)
    sigs = detect_signals(df, sym)
    print(f"{sym} {EXEC_TIMEFRAME}: {len(df):,} bars, {len(sigs)} valid H2/L2 "
          f"signals ({df['Time'].iloc[0]} -> {df['Time'].iloc[-1]})")
    print("\nMost recent 5 signals:")
    for s in sigs[-5:]:
        print(f"  {s.time}  {s.side:4}  entry={s.entry}  stop={s.stop}  "
              f"target={s.target}  risk={s.risk_pips}p  {s.rr:.0f}R")
    fresh = latest_signal(df, sym, max_age_bars=1)
    print("\nActionable on last closed bar:", fresh.as_dict() if fresh else "none")
