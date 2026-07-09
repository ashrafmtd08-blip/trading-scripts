"""
Second Entry (H2/L2) — paper-trading simulation (simulated demo account).

The closest thing to a demo run that can execute off-MetaTrader: it replays real
history through the SAME detector the live bot uses, on a simulated account with
a starting balance, constant 1%-risk position sizing (no compounding),
break-even at 1R, order expiry, and — crucially — a modelled spread. Signals are
found on the execution timeframe
(M3 by default); fills and SL/TP are walked on the underlying M1 data for
intrabar accuracy.

This is a historical simulation, not a live forward test. For a true forward
demo, run mt5_live_bot.py on your broker's MT5 demo account.

    python paper_trade.py            # M3, last 12 months, 1-pip spread
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import second_entry_execution as ex
from second_entry_backtest import INP_EXPIRY_BARS, INP_RR, point_size

# --------------------------------------------------------------------------- #
# Paper-account configuration
# --------------------------------------------------------------------------- #
START_BALANCE   = 10_000.0
RISK_PCT        = 1.0             # % of balance risked per trade
BREAKEVEN_AT_R  = 1.0
SYMBOLS         = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD",
                   "AUDUSD", "NZDUSD"]
EXEC_TF         = "M3"
RESAMPLE_RULE   = "3min"
TF_SECONDS      = 3 * 60
PAPER_START     = "2025-01-01"    # simulate the most recent ~12 months
SPREAD_PIPS     = 1.0             # modelled round-trip spread (majors, retail-ish)
SLIPPAGE_PIPS   = 0.5             # adverse slippage per fill (entry + exit)
MIN_STOP_PIPS   = 3.0             # skip signals with a tighter stop than a broker
                                  # would accept (and that costs would destroy)
ONE_PER_SIDE    = True

HERE = os.path.dirname(os.path.abspath(__file__))


def pip_size(sym: str) -> float:
    return 0.01 if sym.endswith("JPY") else 0.0001


def load_m1(sym: str) -> pd.DataFrame:
    path = os.path.join(HERE, "data", "m1_parquet", f"{sym}.parquet")
    if not os.path.exists(path):
        import fetch_m1_data
        fetch_m1_data.fetch()
    return pd.read_parquet(
        path, columns=["timestamp_utc", "open", "high", "low", "close"]
    ).set_index("timestamp_utc").sort_index()


def simulate_symbol(sym: str, spread_pips: float, slippage_pips: float = 0.0) -> list[dict]:
    """Return a list of closed paper trades for one symbol (R is cost-adjusted)."""
    m1 = load_m1(sym)
    warm = pd.Timestamp(PAPER_START, tz="UTC") - pd.Timedelta(days=60)
    m1 = m1[m1.index >= warm]

    # execution-timeframe frame for signal detection
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    m3 = m1.resample(RESAMPLE_RULE).agg(agg).dropna(subset=["open"]).reset_index()
    m3 = m3.rename(columns={"timestamp_utc": "Time", "open": "Open", "high": "High",
                            "low": "Low", "close": "Close"})
    sigs = ex.detect_signals(m3[["Time", "Open", "High", "Low", "Close"]], sym, EXEC_TF)

    # M1 arrays for intrabar fill / exit (epoch seconds, unit-robust)
    t1 = m1.index.values.astype("datetime64[s]").astype("int64")
    h1 = m1["high"].to_numpy(float)
    l1 = m1["low"].to_numpy(float)
    n1 = len(t1)
    pip = pip_size(sym)
    spread = spread_pips * pip
    slip = slippage_pips * pip
    min_stop = MIN_STOP_PIPS * pip
    start_epoch = int(pd.Timestamp(PAPER_START, tz="UTC").timestamp())

    trades: list[dict] = []
    last_exit_epoch = {"BUY": -1, "SELL": -1}   # ONE_PER_SIDE gate

    for s in sigs:
        sig_ts = pd.Timestamp(s.time)
        if sig_ts.tzinfo is None:
            sig_ts = sig_ts.tz_localize("UTC")
        # order becomes active once the confirming bar has closed (2 bars after
        # the signal-bar start), matching the live bot's "closed-bar" detection
        active = int(sig_ts.timestamp()) + 2 * TF_SECONDS
        if active < start_epoch:
            continue
        if ONE_PER_SIDE and active < last_exit_epoch[s.side]:
            continue  # already have a live trade this side

        k = int(np.searchsorted(t1, active))
        if k >= n1:
            continue
        expire = active + INP_EXPIRY_BARS * TF_SECONDS
        bull = s.side == "BUY"
        entry, sl, tp = s.entry, s.stop, s.target
        r_dist = abs(entry - sl)
        if r_dist <= 0 or r_dist < min_stop:
            continue  # too-tight stop: a real broker would reject it, and costs
                      # would swamp it — exclude, don't pretend we'd trade it

        # ---- phase 1: fill within expiry ---------------------------------- #
        fill_k = None
        kk = k
        while kk < n1 and t1[kk] <= expire:
            if (bull and h1[kk] >= entry) or (not bull and l1[kk] <= entry):
                fill_k = kk
                break
            kk += 1
        if fill_k is None:
            continue  # expired unfilled — no trade

        # ---- phase 2: hold to SL/TP with break-even ----------------------- #
        cur_sl = sl
        be_done = False
        raw_r = None
        kk = fill_k
        while kk < n1:
            hi, lo = h1[kk], l1[kk]
            if not be_done:
                if bull and hi >= entry + BREAKEVEN_AT_R * r_dist:
                    be_done, cur_sl = True, entry
                elif not bull and lo <= entry - BREAKEVEN_AT_R * r_dist:
                    be_done, cur_sl = True, entry
            if bull:
                if lo <= cur_sl:                       # SL-first on ties
                    raw_r = (cur_sl - entry) / r_dist
                    break
                if hi >= tp:
                    raw_r = INP_RR
                    break
            else:
                if hi >= cur_sl:
                    raw_r = (entry - cur_sl) / r_dist
                    break
                if lo <= tp:
                    raw_r = INP_RR
                    break
            kk += 1
        if raw_r is None:
            continue  # still open at end of data — drop

        exit_epoch = int(t1[kk])
        # costs in R: one spread + adverse slippage on entry AND exit fills
        realized_r = raw_r - (spread + 2.0 * slip) / r_dist
        last_exit_epoch[s.side] = exit_epoch
        trades.append({
            "symbol": sym, "side": s.side,
            "entry_epoch": int(t1[fill_k]), "exit_epoch": exit_epoch,
            "r": round(float(realized_r), 4),
        })
    return trades


def run(spread_pips: float = SPREAD_PIPS, slippage_pips: float = 0.0, label: str = "") -> dict:
    all_trades: list[dict] = []
    for sym in SYMBOLS:
        all_trades += simulate_symbol(sym, spread_pips, slippage_pips)
    all_trades.sort(key=lambda x: x["exit_epoch"])

    # peak concurrent open positions (portfolio heat context)
    events = []
    for t in all_trades:
        events.append((t["entry_epoch"], 1))
        events.append((t["exit_epoch"], -1))
    events.sort()
    cur = peak_conc = 0
    for _, d in events:
        cur += d
        peak_conc = max(peak_conc, cur)

    # CONSTANT risk = 1% of the *initial* balance (no compounding blow-up)
    risk = START_BALANCE * RISK_PCT / 100.0
    bal = START_BALANCE
    peak = bal
    max_dd = 0.0
    curve = []
    wins = losses = 0
    r_sum = 0.0
    gross_win = gross_loss = 0.0
    for t in all_trades:
        pnl = t["r"] * risk
        bal += pnl
        peak = max(peak, bal)
        max_dd = min(max_dd, (bal - peak) / peak)
        r_sum += t["r"]
        if t["r"] > 0:
            wins += 1; gross_win += pnl
        else:
            losses += 1; gross_loss += -pnl
        curve.append({"date": pd.to_datetime(t["exit_epoch"], unit="s").strftime("%Y-%m-%d"),
                      "balance": round(bal, 2)})

    n = len(all_trades)
    res = {
        "label": label or f"{EXEC_TF} spread={spread_pips}p",
        "spread_pips": spread_pips, "slippage_pips": slippage_pips,
        "start_balance": START_BALANCE, "end_balance": round(bal, 2),
        "return_pct": round(100 * (bal / START_BALANCE - 1), 1),
        "trades": n, "wins": wins, "losses": losses,
        "win_rate": round(100 * wins / n, 1) if n else 0,
        "expectancy_R": round(r_sum / n, 3) if n else 0,
        "total_R": round(r_sum, 1),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
        "max_drawdown_pct": round(100 * max_dd, 1),
        "peak_concurrent_positions": peak_conc,
        "curve": curve,
    }
    return res


def main() -> None:
    print(f"Paper-trading simulation — Second Entry (H2/L2) {EXEC_TF}")
    print(f"Account ${START_BALANCE:,.0f} | risk {RISK_PCT}%/trade | 7 majors | "
          f"{PAPER_START} -> data end | BE at {BREAKEVEN_AT_R}R\n")

    frictionless = run(0.0, 0.0, label="no costs (upper bound)")
    withspread   = run(SPREAD_PIPS, 0.0, label=f"{SPREAD_PIPS:.0f}-pip spread")
    withcosts    = run(SPREAD_PIPS, SLIPPAGE_PIPS,
                       label=f"spread+{SLIPPAGE_PIPS:.1f}p slippage")

    hdr = f"{'Scenario':24} {'Trades':>7} {'Win%':>6} {'ExpR':>7} {'PF':>5} {'Return':>8} {'MaxDD':>7} {'End $':>10}"
    print(hdr); print("-" * len(hdr))
    for r in (frictionless, withspread, withcosts):
        print(f"{r['label']:24} {r['trades']:7d} {r['win_rate']:5.1f}% "
              f"{r['expectancy_R']:+6.2f}R {r['profit_factor']:5.2f} "
              f"{r['return_pct']:+7.1f}% {r['max_drawdown_pct']:6.1f}% "
              f"{r['end_balance']:>10,.0f}")

    out = {"config": {"start_balance": START_BALANCE, "risk_pct": RISK_PCT,
                      "symbols": SYMBOLS, "timeframe": EXEC_TF,
                      "paper_start": PAPER_START, "breakeven_at_r": BREAKEVEN_AT_R,
                      "spread_pips": SPREAD_PIPS, "slippage_pips": SLIPPAGE_PIPS,
                      "min_stop_pips": MIN_STOP_PIPS},
           "frictionless": frictionless, "with_spread": withspread,
           "with_costs": withcosts}
    path = os.path.join(HERE, "paper_trade_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {os.path.basename(path)}.  Peak concurrent positions: "
          f"{withcosts['peak_concurrent_positions']}.")
    print(f"Model: constant 1%-of-initial risk (no compounding); {SPREAD_PIPS:.0f}-pip "
          f"spread + {SLIPPAGE_PIPS:.1f}-pip slippage per fill; stops < {MIN_STOP_PIPS:.0f} "
          f"pips skipped (broker would reject). Still idealized (flat spread, no swaps/"
          f"commission, one vendor feed). A live demo / Strategy Tester is the real test.")


if __name__ == "__main__":
    main()
