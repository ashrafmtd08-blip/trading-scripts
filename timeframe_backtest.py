"""
Second Entry (H2/L2) across execution timeframes — M3 vs M5 vs M15.

Same strategy engine as second_entry_backtest.py, but run on intraday
timeframes to find which execution timeframe is most profitable. All three
timeframes are resampled from ONE source of 1-minute (M1) data per pair, so the
comparison is apples-to-apples: identical pairs, identical window, identical
rules — only the candle size changes.

Data: M1 OHLCV for seven majors, 2015-2025, from the public
`Kanyal-HarsH/forex-algo-trading` dataset (parquet). ~78 MB/pair; fetched into
data/m1_parquet/ (gitignored) by fetch_m1_data.py, not committed.

As with the H4 report, no spread / slippage / commission is modelled — this
isolates the effect of the timeframe on the raw pattern edge.
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd

import second_entry_backtest as se

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"]
TIMEFRAMES = [("M3", "3min"), ("M5", "5min"), ("M15", "15min")]

HERE = os.path.dirname(os.path.abspath(__file__))
M1_DIR = os.path.join(HERE, "data", "m1_parquet")
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def load_m1(symbol: str) -> pd.DataFrame:
    path = os.path.join(M1_DIR, f"{symbol}.parquet")
    if not os.path.exists(path):
        import fetch_m1_data
        fetch_m1_data.fetch()
    df = pd.read_parquet(
        path, columns=["timestamp_utc", "open", "high", "low", "close", "volume"]
    )
    return df.set_index("timestamp_utc").sort_index()


def resample(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
    r = m1.resample(rule).agg(AGG).dropna(subset=["open"]).reset_index()
    r = r.rename(columns={
        "timestamp_utc": "Time", "open": "Open", "high": "High",
        "low": "Low", "close": "Close",
    })
    return r[["Time", "Open", "High", "Low", "Close"]]


def main() -> None:
    # stats[tf][symbol] = Stats
    per = {tf: {} for tf, _ in TIMEFRAMES}
    t0 = time.time()
    for sym in PAIRS:
        m1 = load_m1(sym)
        for tf, rule in TIMEFRAMES:
            df = resample(m1, rule)
            st = se.backtest(df, sym)
            per[tf][sym] = st
            print(f"  {sym} {tf:3}  bars={len(df):>9,}  trades={st.valid:>4}  "
                  f"win={st.win_rate:4.1f}%  exp={st.expectancy:+.2f}R  "
                  f"totR={st.r_sum:+7.1f}  ({time.time()-t0:5.0f}s)")
        del m1
    print()

    # ---- aggregate per timeframe ------------------------------------------ #
    def aggregate(tf: str) -> se.Stats:
        tot = se.Stats(symbol=tf)
        for st in per[tf].values():
            tot.wins += st.wins; tot.losses += st.losses
            tot.cancelled += st.cancelled; tot.signals += st.signals
            tot.r_sum += st.r_sum
            tot.rej_trend += st.rej_trend; tot.rej_ema += st.rej_ema
            tot.rej_quality += st.rej_quality; tot.rej_fvg += st.rej_fvg
            tot.span_days = max(tot.span_days, st.span_days)
        return tot

    aggs = {tf: aggregate(tf) for tf, _ in TIMEFRAMES}

    # ---- comparison table -------------------------------------------------- #
    hdr = (f"{'TF':4} {'Trades':>7} {'Win':>5} {'Loss':>5} {'Win%':>6} "
           f"{'ExpR':>7} {'Total R':>9} {'PF':>5} {'T/day':>7}")
    line = "=" * len(hdr)
    print(line)
    print(f"Second Entry (H2/L2) — execution-timeframe comparison")
    print(f"7 majors | M1 resampled | 2015-2025 | RR={se.INP_RR} | "
          f"break-even {100/(1+se.INP_RR):.1f}%")
    print(line)
    print(hdr)
    print("-" * len(hdr))
    for tf, _ in TIMEFRAMES:
        a = aggs[tf]
        print(f"{tf:4} {a.valid:7d} {a.wins:5d} {a.losses:5d} {a.win_rate:5.1f}% "
              f"{a.expectancy:+6.2f}R {a.r_sum:+8.1f}R {a.profit_factor:5.2f} "
              f"{a.trades_per_day:7.2f}")
    print(line)

    best_totr = max(aggs.values(), key=lambda a: a.r_sum)
    best_exp = max(aggs.values(), key=lambda a: a.expectancy)
    print(f"\nMost total R : {best_totr.symbol}  ({best_totr.r_sum:+.0f}R)")
    print(f"Best per-trade edge : {best_exp.symbol}  ({best_exp.expectancy:+.2f}R/trade)")

    # ---- per-pair x timeframe expectancy grid ------------------------------ #
    print("\nExpectancy (R/trade) by pair x timeframe:")
    print(f"{'Pair':7}" + "".join(f"{tf:>9}" for tf, _ in TIMEFRAMES))
    for sym in PAIRS:
        row = f"{sym:7}"
        for tf, _ in TIMEFRAMES:
            row += f"{per[tf][sym].expectancy:+8.2f}R"
        print(row)

    # ---- dump json --------------------------------------------------------- #
    out = {
        "meta": {"strategy": "Second Entry (H2/L2)", "source": "M1 resampled",
                 "pairs": PAIRS, "window": "2015-2025", "rr": se.INP_RR,
                 "breakeven_win_rate": round(100 / (1 + se.INP_RR), 1)},
        "timeframes": {
            tf: {
                "trades": aggs[tf].valid, "wins": aggs[tf].wins,
                "losses": aggs[tf].losses, "cancelled": aggs[tf].cancelled,
                "win_rate": round(aggs[tf].win_rate, 1),
                "expectancy": round(aggs[tf].expectancy, 3),
                "total_r": round(aggs[tf].r_sum, 1),
                "profit_factor": round(aggs[tf].profit_factor, 2),
                "trades_per_day": round(aggs[tf].trades_per_day, 3),
                "candidates": aggs[tf].signals,
                "pairs": {
                    sym: {
                        "trades": per[tf][sym].valid, "wins": per[tf][sym].wins,
                        "losses": per[tf][sym].losses,
                        "win_rate": round(per[tf][sym].win_rate, 1),
                        "expectancy": round(per[tf][sym].expectancy, 3),
                        "total_r": round(per[tf][sym].r_sum, 1),
                        "profit_factor": round(per[tf][sym].profit_factor, 2),
                        "trades_per_day": round(per[tf][sym].trades_per_day, 3),
                    } for sym in PAIRS
                },
            } for tf, _ in TIMEFRAMES
        },
    }
    path = os.path.join(HERE, "timeframe_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {os.path.basename(path)}.  Total runtime {time.time()-t0:.0f}s.")


if __name__ == "__main__":
    main()
