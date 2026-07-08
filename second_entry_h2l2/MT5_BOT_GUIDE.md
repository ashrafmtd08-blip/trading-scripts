# Running the Second Entry (H2/L2) bot on MetaTrader 5

This turns the strategy into an automated bot using **`mt5_live_bot.py`**, which
drives your MetaTrader 5 terminal from Python and trades the *exact* logic that
was backtested (`second_entry_m5_strategy.detect_signals`).

There are two ways to auto-trade on MT5. This guide covers the Python bridge
because it reuses the validated Python code 1:1; the alternative (a native MQL5
Expert Advisor) is discussed at the end.

---

## How it works

```
MT5 terminal (logged in)  ──copy_rates──►  mt5_live_bot.py
      ▲                                          │
      │                                     detect_signals()  (your strategy)
      └────────────order_send()◄──────────────  places buy/sell-stop + SL/TP
```

Every few seconds the bot:
1. Pulls the last ~600 **closed** M5 candles per symbol.
2. Runs the H2/L2 detector on them.
3. If the just-closed bar produced a fresh signal, places a **pending stop
   order** (buy-stop above H2 / sell-stop below L2) with SL at the FVG impulse
   candle and TP at 2R, sized to **1% of balance**, expiring after 12 bars.
4. Moves the stop to **break-even at +1R** on any open position.

It only ever manages its own orders (tagged with `MAGIC = 250707`).

---

## One-time setup (Windows)

> The `MetaTrader5` Python package is **Windows-only**. On Mac/Linux, run it in a
> Windows VM or a cheap Windows VPS (most people run MT5 bots on a VPS so it
> stays online 24/5).

1. **Install MetaTrader 5** and log in to your broker account. **Use a DEMO
   account first.**
2. In MT5: **Tools → Options → Expert Advisors → tick "Allow algorithmic
   trading"**. (Also tick "Allow WebRequest" is not needed here.)
3. Install Python 3.10+ (64-bit, to match the 64-bit terminal).
4. Install the packages:
   ```bat
   pip install MetaTrader5 pandas numpy
   ```
5. Put these three files in the same folder:
   `mt5_live_bot.py`, `second_entry_m5_strategy.py`, `second_entry_backtest.py`.

---

## Configure

Open `mt5_live_bot.py` and edit the block at the top:

| Setting | Default | Meaning |
|---|---|---|
| `DRY_RUN` | `True` | **Logs orders but sends nothing.** Keep it on until you trust the log. |
| `SYMBOLS` | 7 majors | Match your broker's exact symbol names (some add suffixes like `EURUSD.a`). |
| `RISK_PERCENT` | `1.0` | % of balance risked per trade. |
| `BREAKEVEN_AT_R` | `1.0` | Move SL to entry at +1R. |
| `MAX_SPREAD_PTS` | `25` | Skip a signal if spread is wider than this. |
| `ONE_PER_SIDE` | `True` | At most one order/position per symbol per side. |
| `MAGIC` | `250707` | Leave unique so the bot only touches its own trades. |

If your terminal is already logged in, leave `MT5_LOGIN/PASSWORD/SERVER` as
`None` — the bot attaches to the running terminal. Set them only if you want the
bot to log in itself.

---

## Run

```bat
python mt5_live_bot.py
```

- **First run it in DRY_RUN on a demo account for a few days.** Read the log:
  it prints every `SIGNAL`, every `[DRY] would send …`, and every skip reason.
- When the dry-run orders look correct (right side, sane entry/SL/TP, sensible
  lot size), set `DRY_RUN = False` **on the demo** and let it actually place
  orders for a while.
- Only after a demo run that matches your expectations should you consider a
  live account. Keep the terminal (or VPS) running the whole time.

Stop with **Ctrl-C** (it shuts the MT5 connection down cleanly).

---

## Important caveats — read before going live

- **Not yet run against a real terminal by its author.** You are validating it.
  Demo first, no exceptions.
- **Costs.** The backtest modelled **no spread/slippage/commission**. Live, you
  pay all three. On M5 the average stop is ~12 pips, so a 1-pip spread is ~8% of
  risk per trade — it will lower the real edge.
- **The backtest horizon quirk we discussed.** The backtester only counted
  trades that resolved within 12 bars and dropped the rest (~54% of M5 signals).
  **Live, the bot lets trades run to their real SL/TP** (only the *unfilled*
  pending order expires after 12 bars), which is correct — but it means live
  results will *not* match those truncated backtest stats. Re-running the
  backtest with a proper resolution horizon is the right thing to do before
  trusting any expectancy number.
- **Broker digits.** The strategy assumes 5-digit (3-digit JPY) pricing. The bot
  warns if a symbol's digits differ; on a 4-digit broker the point-based buffers
  would be mis-scaled.
- **Symbol names & filling modes** vary by broker; adjust `SYMBOLS` and expect to
  tune `filling_mode()` if orders are rejected with "unsupported filling".

---

## Alternative: a native MQL5 Expert Advisor

Your session notes already reference an EA (`SecondEntry_H2L2_EA.mq5`). A native
EA is the more robust production path because:
- it runs **inside** MT5 (no Python process, no terminal-to-Python bridge),
- it survives terminal restarts and is trivial to run on a VPS,
- it can be backtested in MT5's own Strategy Tester with tick data + real spread.

The trade-off: the EA is a *re-implementation* in MQL5, so its logic can drift
from the Python you backtested. The Python bot here guarantees the live logic is
byte-for-byte the detector you validated. A good workflow:

1. Prove the edge with the Python backtest (fix the horizon issue first).
2. Paper-trade with this Python bot on demo to confirm live behaviour.
3. If you want 24/5 robustness, port the confirmed rules to the MQL5 EA and
   verify it reproduces the Python signals bar-for-bar before trusting it.
