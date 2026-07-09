"""
Second Entry (H2/L2) — standalone Python strategy tester.

Point it at any OHLC CSV and get a full backtest report: win rate, expectancy,
profit factor, total R, max drawdown, and the same numbers again with spread +
slippage costs applied. Optionally resample to a different timeframe first.

Uses the same detection + run-to-resolution engine as the rest of the project
(second_entry_backtest.py), so results are consistent and there's one source of
truth for the rules.

Examples
--------
    # test the bundled Gold M5 data
    python strategy_tester.py data/xau_btc/XAUUSD_M5.csv --symbol XAUUSD

    # take a 1-minute CSV, resample to M3, model 1-pip spread + 0.5-pip slippage
    python strategy_tester.py EURUSD_M1.csv --symbol EURUSD --resample 3min \
        --spread 1.0 --slippage 0.5

    # only test 2023 onward
    python strategy_tester.py gold.csv --symbol XAUUSD --start 2023-01-01

CSV columns are matched case-insensitively; a time/date/timestamp column plus
open, high, low, close are required (volume optional).
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

import second_entry_backtest as se


def load_ohlc(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    low = {c.lower(): c for c in df.columns}
    tcol = next((low[k] for k in ("time", "date", "datetime", "timestamp") if k in low), None)
    if tcol is None:
        tcol = df.columns[0]
    need = {}
    for k in ("open", "high", "low", "close"):
        if k not in low:
            raise SystemExit(f"CSV is missing a '{k}' column (found: {list(df.columns)})")
        need[k] = low[k]
    out = pd.DataFrame({
        "Time": pd.to_datetime(df[tcol], utc=True, errors="coerce").dt.tz_localize(None),
        "Open": df[need["open"]].astype(float),
        "High": df[need["high"]].astype(float),
        "Low":  df[need["low"]].astype(float),
        "Close": df[need["close"]].astype(float),
    }).dropna()
    return out.drop_duplicates(subset="Time").sort_values("Time").reset_index(drop=True)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    r = (df.set_index("Time")
           .resample(rule)
           .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
           .dropna(subset=["Open"]).reset_index())
    return r


def cost_adjusted(stats: se.Stats, symbol: str, spread_pips: float, slippage_pips: float):
    """Recompute win/loss/expectancy after spread + slippage, from the raw trades."""
    pip = se.pip_size(symbol)
    cost_price = (spread_pips + 2.0 * slippage_pips) * pip
    wins = losses = 0
    r_sum = gw = gl = 0.0
    r_seq = []
    for t in stats.trades:
        outcome, r = t[5], t[6]
        if outcome not in ("win", "loss"):
            continue
        rdist = abs(t[2] - t[3])            # |entry - sl| in price
        net = r - (cost_price / rdist if rdist > 0 else 0.0)
        r_sum += net
        r_seq.append(net)
        if net > 0:
            wins += 1; gw += net
        else:
            losses += 1; gl += -net
    n = wins + losses
    # max drawdown in R
    cum = peak = 0.0
    dd = 0.0
    for r in r_seq:
        cum += r; peak = max(peak, cum); dd = min(dd, cum - peak)
    return {
        "trades": n, "wins": wins, "losses": losses,
        "win_rate": 100 * wins / n if n else 0,
        "expectancy": r_sum / n if n else 0,
        "total_r": r_sum,
        "profit_factor": gw / gl if gl else float("inf"),
        "max_dd_r": dd,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Second Entry (H2/L2) strategy tester")
    ap.add_argument("csv", help="path to an OHLC CSV")
    ap.add_argument("--symbol", default="EURUSD",
                    help="symbol name (sets point size: FX/JPY/XAUUSD/BTC*)")
    ap.add_argument("--resample", default=None,
                    help="pandas offset to resample to, e.g. 3min, 5min, 15min")
    ap.add_argument("--start", default=None, help="ignore bars before this date")
    ap.add_argument("--end", default=None, help="ignore bars after this date")
    ap.add_argument("--spread", type=float, default=1.0, help="spread in pips")
    ap.add_argument("--slippage", type=float, default=0.5, help="slippage pips/fill")
    args = ap.parse_args()

    df = load_ohlc(args.csv)
    if args.start:
        df = df[df["Time"] >= pd.Timestamp(args.start)].reset_index(drop=True)
    if args.end:
        df = df[df["Time"] <= pd.Timestamp(args.end)].reset_index(drop=True)
    if args.resample:
        df = resample(df, args.resample)
    if len(df) < 100:
        raise SystemExit(f"Only {len(df)} bars after filtering — need more data.")

    st = se.backtest(df.copy(), args.symbol)
    net = cost_adjusted(st, args.symbol, args.spread, args.slippage)
    be = 100.0 / (1.0 + se.INP_RR)

    span_days = (df["Time"].iloc[-1] - df["Time"].iloc[0]).days
    print("=" * 66)
    print(f"Second Entry (H2/L2) strategy tester — {args.symbol}")
    print(f"{os.path.basename(args.csv)} | {len(df):,} bars"
          f"{' resampled ' + args.resample if args.resample else ''} | "
          f"{df['Time'].iloc[0].date()} → {df['Time'].iloc[-1].date()} ({span_days}d)")
    print(f"RR={se.INP_RR}  break-even={be:.1f}%  "
          f"costs: {args.spread}p spread + {args.slippage}p slippage")
    print("=" * 66)

    def row(label, trades, wins, losses, wr, exp, tot, pf, dd):
        print(f"{label:16} {trades:>6} {wins:>5} {losses:>5} {wr:6.1f}% "
              f"{exp:+7.2f}R {tot:+9.1f}R {pf:6.2f} {dd:+8.1f}R")

    print(f"{'':16} {'Trades':>6} {'Win':>5} {'Loss':>5} {'Win%':>7} "
          f"{'ExpR':>8} {'TotalR':>10} {'PF':>6} {'MaxDD':>9}")
    print("-" * 66)
    row("raw (no costs)", st.resolved, st.wins, st.losses, st.win_rate,
        st.expectancy, st.r_sum, st.profit_factor, _dd_r(st))
    row("after costs", net["trades"], net["wins"], net["losses"], net["win_rate"],
        net["expectancy"], net["total_r"], net["profit_factor"], net["max_dd_r"])
    print("-" * 66)
    print(f"Cancelled (pending expired, unfilled): {st.cancelled}   "
          f"Candidates scanned: {st.signals}")
    print(f"Rejected by filter  Trend/EMA/Quality/FVG: "
          f"{st.rej_trend}/{st.rej_ema}/{st.rej_quality}/{st.rej_fvg}")
    print("No look-ahead (FVG confirmed before fill); costs applied as an R haircut.")


def _dd_r(st: se.Stats) -> float:
    cum = peak = dd = 0.0
    for t in st.trades:
        if t[5] not in ("win", "loss"):
            continue
        cum += t[6]; peak = max(peak, cum); dd = min(dd, cum - peak)
    return dd


if __name__ == "__main__":
    main()
