"""
Second Entry (H2/L2) — live MetaTrader 5 trading bot.

Connects to a running MT5 terminal, watches the majors on M5, and places
pending stop orders for each fresh H2/L2 signal using the SAME detection logic
that was backtested (second_entry_m5_strategy.detect_signals). It sizes each
trade to a fixed % of balance, attaches SL/TP, expires unfilled orders, and
trails to break-even at 1R — mirroring the EA behaviour described in the notes.

REQUIREMENTS (Windows only — the MetaTrader5 package is Windows-only):
    pip install MetaTrader5 pandas numpy
    A MetaTrader 5 terminal installed and logged in to your (demo!) account,
    with Tools -> Options -> Expert Advisors -> "Allow algorithmic trading" ON.

SAFETY:
    * DRY_RUN = True by default — it logs the orders it WOULD send and places
      nothing. Flip to False only after you've read the log on a demo account.
    * Start on DEMO. This bot has not been run against a live terminal by its
      author; you are the first line of validation.

Run:  python mt5_live_bot.py
Stop: Ctrl-C
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # allows import on non-Windows for inspection; run() will refuse

from second_entry_m5_strategy import detect_signals, OrderPlan
from second_entry_backtest import INP_EXPIRY_BARS, INP_BUFFER_PTS

# --------------------------------------------------------------------------- #
# Configuration — edit these
# --------------------------------------------------------------------------- #
DRY_RUN          = True          # << set False only after demo-testing
SYMBOLS          = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD",
                    "AUDUSD", "NZDUSD"]
TIMEFRAME        = None          # set in run() to mt5.TIMEFRAME_M5
RISK_PERCENT     = 1.0           # % of account balance risked per trade
BREAKEVEN_AT_R   = 1.0           # move SL to entry once price is +1R
MAX_SPREAD_PTS   = 25            # skip a signal if current spread exceeds this
ONE_PER_SIDE     = True          # at most one order/position per symbol per side
MAGIC            = 250707        # identifies this bot's orders
BARS_TO_PULL     = 600           # closed M5 bars to feed the detector (warmup)
POLL_SECONDS     = 5             # how often to check for a new closed bar

# Optional explicit login (usually not needed if the terminal is already
# logged in). Leave as None to attach to the running terminal's account.
MT5_PATH     = None              # e.g. r"C:\Program Files\MetaTrader 5\terminal64.exe"
MT5_LOGIN    = None              # e.g. 12345678
MT5_PASSWORD = None
MT5_SERVER   = None              # e.g. "MetaQuotes-Demo"


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


# --------------------------------------------------------------------------- #
# MT5 helpers
# --------------------------------------------------------------------------- #
def connect() -> bool:
    if mt5 is None:
        log("ERROR: MetaTrader5 package not available (Windows only). Aborting.")
        return False
    kwargs = {}
    if MT5_PATH:
        kwargs["path"] = MT5_PATH
    if MT5_LOGIN:
        kwargs.update(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not mt5.initialize(**kwargs):
        log("initialize() failed:", mt5.last_error())
        return False
    ai = mt5.account_info()
    log(f"Connected: login={ai.login} server={ai.server} "
        f"balance={ai.balance} {ai.currency}  DRY_RUN={DRY_RUN}")
    for s in SYMBOLS:
        if not mt5.symbol_select(s, True):
            log(f"WARN: could not select {s}")
    return True


def closed_m5_frame(symbol: str) -> pd.DataFrame | None:
    """Recent CLOSED M5 bars as a Time/Open/High/Low/Close frame."""
    # position 0 is the still-forming bar; skip it -> start at 1
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, BARS_TO_PULL)
    if rates is None or len(rates) < 60:
        return None
    df = pd.DataFrame(rates)
    df["Time"] = pd.to_datetime(df["time"], unit="s")
    return df.rename(columns={"open": "Open", "high": "High",
                              "low": "Low", "close": "Close"})[
        ["Time", "Open", "High", "Low", "Close"]]


def digits_ok(symbol: str) -> bool:
    """The strategy assumes 5-digit (3-digit JPY) pricing. Warn otherwise."""
    info = mt5.symbol_info(symbol)
    expected = 3 if symbol.endswith("JPY") else 5
    if info.digits != expected:
        log(f"WARN: {symbol} has {info.digits} digits (expected {expected}); "
            f"point-based buffers may be mis-scaled.")
        return False
    return True


def has_open_side(symbol: str, side: str) -> bool:
    """True if we already have a pending order or position for this side."""
    want_pos = mt5.POSITION_TYPE_BUY if side == "BUY" else mt5.POSITION_TYPE_SELL
    for p in (mt5.positions_get(symbol=symbol) or []):
        if p.magic == MAGIC and p.type == want_pos:
            return True
    want_ord = mt5.ORDER_TYPE_BUY_STOP if side == "BUY" else mt5.ORDER_TYPE_SELL_STOP
    for o in (mt5.orders_get(symbol=symbol) or []):
        if o.magic == MAGIC and o.type == want_ord:
            return True
    return False


def lot_for_risk(symbol: str, entry: float, stop: float) -> float | None:
    """Volume such that |entry-stop| loss ≈ RISK_PERCENT of balance."""
    info = mt5.symbol_info(symbol)
    bal = mt5.account_info().balance
    risk_money = bal * RISK_PERCENT / 100.0
    dist = abs(entry - stop)
    if dist <= 0 or info.trade_tick_size <= 0 or info.trade_tick_value <= 0:
        return None
    ticks = dist / info.trade_tick_size
    risk_per_lot = ticks * info.trade_tick_value
    if risk_per_lot <= 0:
        return None
    lots = risk_money / risk_per_lot
    step = info.volume_step
    lots = max(info.volume_min, min(info.volume_max, (int(lots / step)) * step))
    return round(lots, 8)


def filling_mode(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    # pending stop orders generally accept RETURN; fall back sensibly
    fm = getattr(info, "filling_mode", 0)
    if fm & 2:   # SYMBOL_FILLING_IOC
        return mt5.ORDER_FILLING_IOC
    if fm & 1:   # SYMBOL_FILLING_FOK
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def place_pending(symbol: str, plan: OrderPlan) -> None:
    if ONE_PER_SIDE and has_open_side(symbol, plan.side):
        log(f"skip {symbol} {plan.side}: already have an order/position this side")
        return
    if not digits_ok(symbol):
        return

    info = mt5.symbol_info(symbol)
    spread_pts = info.spread
    if spread_pts > MAX_SPREAD_PTS:
        log(f"skip {symbol} {plan.side}: spread {spread_pts} > {MAX_SPREAD_PTS} pts")
        return

    tick = mt5.symbol_info_tick(symbol)
    # a buy-stop must sit above current ask; a sell-stop below current bid
    if plan.side == "BUY" and plan.entry <= tick.ask:
        log(f"skip {symbol} BUY: entry {plan.entry} already <= ask {tick.ask}")
        return
    if plan.side == "SELL" and plan.entry >= tick.bid:
        log(f"skip {symbol} SELL: entry {plan.entry} already >= bid {tick.bid}")
        return

    lots = lot_for_risk(symbol, plan.entry, plan.stop)
    if not lots:
        log(f"skip {symbol} {plan.side}: could not size lot")
        return

    otype = mt5.ORDER_TYPE_BUY_STOP if plan.side == "BUY" else mt5.ORDER_TYPE_SELL_STOP
    expiry = int(time.time()) + INP_EXPIRY_BARS * 5 * 60  # 5-min bars
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lots,
        "type": otype,
        "price": plan.entry,
        "sl": plan.stop,
        "tp": plan.target,
        "type_time": mt5.ORDER_TIME_SPECIFIED,
        "expiration": expiry,
        "type_filling": filling_mode(symbol),
        "magic": MAGIC,
        "comment": f"H2L2 {plan.time[-14:]}",
    }
    if DRY_RUN:
        log(f"[DRY] would send {symbol} {plan.side} {lots} lots "
            f"entry={plan.entry} sl={plan.stop} tp={plan.target} "
            f"risk={plan.risk_pips}p")
        return
    res = mt5.order_send(request)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        log(f"ORDER FAILED {symbol} {plan.side}: "
            f"{getattr(res,'retcode',None)} {getattr(res,'comment','')}")
    else:
        log(f"ORDER OK {symbol} {plan.side} {lots} lots ticket={res.order} "
            f"entry={plan.entry} sl={plan.stop} tp={plan.target}")


def manage_breakeven(symbol: str) -> None:
    """Move SL to entry once an open position is +BREAKEVEN_AT_R in profit."""
    tick = mt5.symbol_info_tick(symbol)
    for p in (mt5.positions_get(symbol=symbol) or []):
        if p.magic != MAGIC:
            continue
        r_dist = abs(p.price_open - p.sl)
        if r_dist <= 0:
            continue  # SL already at/through entry (BE done) or missing
        if p.type == mt5.POSITION_TYPE_BUY:
            if p.sl < p.price_open and tick.bid >= p.price_open + BREAKEVEN_AT_R * r_dist:
                _modify_sl(symbol, p, p.price_open)
        else:
            if p.sl > p.price_open and tick.ask <= p.price_open - BREAKEVEN_AT_R * r_dist:
                _modify_sl(symbol, p, p.price_open)


def _modify_sl(symbol: str, position, new_sl: float) -> None:
    request = {
        "action": mt5.TRADE_ACTION_SLTP, "symbol": symbol,
        "position": position.ticket, "sl": new_sl, "tp": position.tp,
    }
    if DRY_RUN:
        log(f"[DRY] would move {symbol} #{position.ticket} SL -> break-even {new_sl}")
        return
    res = mt5.order_send(request)
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    log(f"{'BE OK' if ok else 'BE FAIL'} {symbol} #{position.ticket} -> {new_sl}")


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def run() -> None:
    global TIMEFRAME
    if not connect():
        return
    TIMEFRAME = mt5.TIMEFRAME_M5
    last_bar = {s: None for s in SYMBOLS}
    log("Bot running on M5. Ctrl-C to stop.")
    try:
        while True:
            for sym in SYMBOLS:
                manage_breakeven(sym)                 # every poll
                df = closed_m5_frame(sym)
                if df is None or len(df) < 60:
                    continue
                newest = df["Time"].iloc[-1]
                if last_bar[sym] == newest:
                    continue                          # no new closed bar yet
                last_bar[sym] = newest
                sigs = detect_signals(df, sym)
                if not sigs:
                    continue
                # act only on a signal confirmed on the just-closed bar
                fresh = [s for s in sigs if (len(df) - 1) - s.bar_index <= 1]
                for plan in fresh:
                    log(f"SIGNAL {sym} {plan.side} @bar {newest} "
                        f"entry={plan.entry} sl={plan.stop} tp={plan.target}")
                    place_pending(sym, plan)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        log("Stopping (Ctrl-C).")
    finally:
        if mt5 is not None:
            mt5.shutdown()


if __name__ == "__main__":
    run()
