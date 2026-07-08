"""
MT5 connection test — run this FIRST to prove Python is linked to your terminal.

It does not trade. It connects, prints your account/terminal/symbol details, and
tells you exactly what (if anything) is misconfigured before you run the bot.

    python mt5_connect_test.py                 # attach to the running terminal
    python mt5_connect_test.py EURUSD GBPUSD   # also check specific symbols

If the terminal is already open and logged in, no credentials are needed. To let
Python launch a specific terminal / log in itself, fill MT5_PATH/LOGIN/... below.
"""
from __future__ import annotations

import sys

# Optional explicit login (leave as None to attach to the running terminal).
MT5_PATH     = None    # e.g. r"C:\Program Files\MetaTrader 5\terminal64.exe"
MT5_LOGIN    = None    # e.g. 12345678   (your DEMO account number)
MT5_PASSWORD = None    # e.g. "your-demo-password"
MT5_SERVER   = None    # e.g. "MetaQuotes-Demo"

CHECK_SYMBOLS = sys.argv[1:] or ["EURUSD"]


def main() -> int:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("✗ MetaTrader5 package not installed (Windows only).")
        print("  Fix: pip install MetaTrader5   (64-bit Python + 64-bit terminal)")
        return 1

    kwargs = {}
    if MT5_PATH:
        kwargs["path"] = MT5_PATH
    if MT5_LOGIN:
        kwargs.update(login=int(MT5_LOGIN), password=MT5_PASSWORD, server=MT5_SERVER)

    print(f"MetaTrader5 package version: {mt5.__version__}")
    if not mt5.initialize(**kwargs):
        print("✗ initialize() FAILED:", mt5.last_error())
        print("  Checklist: terminal open & logged in? 64-bit match? "
              "If multiple terminals, set MT5_PATH above.")
        return 1
    print("✓ Linked to the MT5 terminal.\n")

    ti = mt5.terminal_info()
    ai = mt5.account_info()
    if ti is None or ai is None:
        print("✗ Connected but could not read terminal/account info:", mt5.last_error())
        mt5.shutdown()
        return 1

    print("Terminal")
    print(f"  build={ti.build}  connected_to_broker={ti.connected}")
    print(f"  algo_trading_allowed={ti.trade_allowed}")
    print(f"  path={ti.path}")
    if not ti.trade_allowed:
        print("  ⚠ Algo trading is OFF. Enable Tools → Options → Expert Advisors →")
        print("    'Allow algorithmic trading', and click the 'Algo Trading' toolbar")
        print("    button so it turns green. The bot cannot place orders until this is on.")

    print("\nAccount")
    demo = "DEMO" if ai.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "REAL/OTHER"
    print(f"  login={ai.login}  server={ai.server}  type={demo}")
    print(f"  balance={ai.balance:.2f} {ai.currency}  leverage=1:{ai.leverage}")
    print(f"  account_trade_allowed={ai.trade_allowed}")
    if demo != "DEMO":
        print("  ⚠ This is NOT a demo account. Test on DEMO before anything else.")

    print("\nSymbols")
    for sym in CHECK_SYMBOLS:
        if not mt5.symbol_select(sym, True):
            print(f"  ✗ {sym}: not found. Check the broker's exact name "
                  f"(suffixes like {sym}.a / {sym}-ECN are common).")
            continue
        info = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        exp_digits = 3 if sym.endswith("JPY") else 5
        flag = "" if info.digits == exp_digits else \
            f"  ⚠ expected {exp_digits} digits — point buffers may be mis-scaled"
        print(f"  ✓ {sym}: bid={tick.bid} ask={tick.ask} "
              f"spread={info.spread}pts digits={info.digits}{flag}")

    ok = ti.trade_allowed and ai.trade_allowed
    print("\n" + ("✓ Link looks good — you can run mt5_live_bot.py (keep DRY_RUN=True first)."
                  if ok else
                  "⚠ Linked, but trading is disabled — fix the warnings above first."))
    mt5.shutdown()
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
