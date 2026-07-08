"""Render the Gold & Bitcoin companion report from xau_btc_results.json."""
import json
import os

HERE = os.path.dirname(__file__)
d = json.load(open(os.path.join(HERE, "xau_btc_results.json")))
inst = d["instruments"]
be = d["meta"]["breakeven"]

META = {
    "XAUUSD": {"name": "Gold", "sym": "XAU/USD", "accent": "--gold",
               "note": "the instrument the strategy was originally built on (Gold M5)"},
    "BTCUSD": {"name": "Bitcoin", "sym": "BTC/USD", "accent": "--btc",
               "note": "24/7 crypto — the most volatile test of the pattern"},
}
TFS = ["M3", "M5", "M15"]


def tf_row(sym, tf):
    r = inst.get(sym, {}).get(tf)
    if not r:
        return (f'<tr class="pending"><td class="tf">{tf}</td>'
                f'<td colspan="4" class="pend">needs 1-min data — run <code>export_m1.py</code></td></tr>')
    pos = "pos" if r["expectancy"] >= 0 else "neg"
    return (f'<tr><td class="tf">{tf}</td>'
            f'<td class="num">{r["trades"]}</td>'
            f'<td class="num">{r["win_rate"]:.1f}%</td>'
            f'<td class="num {pos}">{r["expectancy"]:+.2f}R</td>'
            f'<td class="num {pos}">{r["total_r"]:+.0f}R</td>'
            f'<td class="num">{r["profit_factor"]:.2f}</td></tr>')


def card(sym):
    m = META[sym]
    rows = "".join(tf_row(sym, tf) for tf in TFS)
    got = inst.get(sym, {})
    best = max((t for t in TFS if t in got), key=lambda t: got[t]["expectancy"], default=None)
    win = got.get("M5", got.get("M15", {})).get("window", "")
    verdict = ""
    if best:
        b = got[best]
        verdict = (f'Best so far: <b>{best}</b> at {b["expectancy"]:+.2f}R '
                   f'({b["win_rate"]:.1f}% win, PF {b["profit_factor"]:.2f}).')
    return f"""
    <div class="inst" data-sym="{sym}">
      <div class="inst-head">
        <span class="dot"></span>
        <div><div class="iname">{m['name']}</div><div class="isym">{m['sym']}</div></div>
      </div>
      <p class="inote">{m['note']}.</p>
      <div class="tbl-wrap">
      <table>
        <thead><tr><th>TF</th><th class="num">Trades</th><th class="num">Win%</th><th class="num">Exp</th><th class="num">Total R</th><th class="num">PF</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      </div>
      <p class="verdict">{verdict}</p>
      <p class="win">Window {win}</p>
    </div>"""


cards = "".join(card(s) for s in ["XAUUSD", "BTCUSD"])

html = f"""<title>Gold &amp; Bitcoin — Second Entry (H2/L2)</title>
<style>
  :root{{--bg:#f3f4f0;--surface:#fcfcfa;--surface-2:#eceee7;--ink:#161b1a;--ink-2:#4b5350;
    --ink-3:#838d88;--line:#dde0d8;--gold:#a9781f;--btc:#c06718;--pos:#1e8f6a;--neg:#c0523a;
    --shadow:0 1px 2px rgba(20,28,26,.05),0 9px 28px rgba(20,28,26,.07);
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;}}
  @media (prefers-color-scheme:dark){{:root{{--bg:#0d1211;--surface:#131a18;--surface-2:#1a2220;
    --ink:#e9ede9;--ink-2:#a6afab;--ink-3:#6b7571;--line:#26302d;--gold:#d8b25c;--btc:#e2933f;
    --pos:#45b98f;--neg:#dd6a50;--shadow:0 1px 2px rgba(0,0,0,.4),0 14px 38px rgba(0,0,0,.45);}}}}
  :root[data-theme="light"]{{--bg:#f3f4f0;--surface:#fcfcfa;--surface-2:#eceee7;--ink:#161b1a;--ink-2:#4b5350;--ink-3:#838d88;--line:#dde0d8;--gold:#a9781f;--btc:#c06718;--pos:#1e8f6a;--neg:#c0523a;--shadow:0 1px 2px rgba(20,28,26,.05),0 9px 28px rgba(20,28,26,.07);}}
  :root[data-theme="dark"]{{--bg:#0d1211;--surface:#131a18;--surface-2:#1a2220;--ink:#e9ede9;--ink-2:#a6afab;--ink-3:#6b7571;--line:#26302d;--gold:#d8b25c;--btc:#e2933f;--pos:#45b98f;--neg:#dd6a50;--shadow:0 1px 2px rgba(0,0,0,.4),0 14px 38px rgba(0,0,0,.45);}}
  *{{box-sizing:border-box;}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.6;-webkit-font-smoothing:antialiased;}}
  .wrap{{max-width:900px;margin:0 auto;padding:clamp(22px,4vw,52px) clamp(16px,4vw,36px) 80px;}}
  .eyebrow{{font-family:var(--mono);font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin:0 0 14px;}}
  h1{{font-family:var(--serif);font-weight:600;font-size:clamp(30px,5vw,46px);line-height:1.04;margin:0 0 14px;text-wrap:balance;}}
  .sub{{color:var(--ink-2);font-size:16.5px;max-width:62ch;margin:0 0 22px;}}
  .facts{{display:flex;flex-wrap:wrap;gap:8px 10px;margin-bottom:34px;}}
  .chip{{font-family:var(--mono);font-size:12.5px;color:var(--ink-2);background:var(--surface-2);border:1px solid var(--line);border-radius:999px;padding:5px 12px;}}
  .chip b{{color:var(--ink);}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;}}
  @media(max-width:680px){{.grid{{grid-template-columns:1fr;}}}}
  .inst{{background:var(--surface);border:1px solid var(--line);border-top:3px solid var(--ac);border-radius:15px;padding:20px 22px;box-shadow:var(--shadow);}}
  .inst[data-sym="XAUUSD"]{{--ac:var(--gold);}} .inst[data-sym="BTCUSD"]{{--ac:var(--btc);}}
  .inst-head{{display:flex;align-items:center;gap:11px;}}
  .dot{{width:13px;height:13px;border-radius:50%;background:var(--ac);}}
  .iname{{font-family:var(--serif);font-weight:600;font-size:22px;line-height:1;}}
  .isym{{font-family:var(--mono);font-size:12px;color:var(--ink-3);margin-top:3px;}}
  .inote{{color:var(--ink-2);font-size:13px;margin:12px 0 14px;}}
  .tbl-wrap{{overflow-x:auto;}}
  table{{border-collapse:collapse;width:100%;font-size:14px;}}
  th,td{{padding:9px 8px;border-bottom:1px solid var(--line);text-align:right;}}
  th:first-child,td:first-child{{text-align:left;}}
  thead th{{font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-3);font-weight:500;}}
  td.tf{{font-family:var(--mono);font-weight:600;color:var(--ac);}}
  td.num{{font-family:var(--mono);font-variant-numeric:tabular-nums;}}
  td.pos{{color:var(--pos);}} td.neg{{color:var(--neg);}}
  tr.pending td{{color:var(--ink-3);}} td.pend{{text-align:left;font-size:12.5px;font-style:italic;}}
  td.pend code{{font-family:var(--mono);font-style:normal;background:var(--surface-2);border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:.9em;}}
  tbody tr:last-child td{{border-bottom:none;}}
  .verdict{{font-size:13.5px;color:var(--ink-2);margin:14px 0 4px;}}
  .verdict b{{color:var(--ink);font-family:var(--mono);}}
  .win{{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);margin:0;}}
  .warn{{background:var(--surface-2);border:1px solid var(--line);border-radius:13px;padding:17px 21px;margin-top:26px;}}
  .warn h3{{font-family:var(--serif);font-size:17px;margin:0 0 8px;}}
  .warn p{{margin:0 0 7px;font-size:13.5px;color:var(--ink-2);}} .warn p:last-child{{margin:0;}}
  .warn code{{font-family:var(--mono);background:var(--surface);border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:.9em;}}
  footer{{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);font-family:var(--mono);font-size:12px;color:var(--ink-3);display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;}}
</style>

<div class="wrap">
  <p class="eyebrow">Strategy Backtest · Beyond FX</p>
  <h1>Gold &amp; Bitcoin — the same strategy, new markets</h1>
  <p class="sub">The Second Entry (H2/L2) engine, unchanged, applied to XAUUSD and
  BTCUSD. A companion to the FX-majors timeframe study — same rules, same 2R
  target, same run-to-resolution win/loss. Point sizes are instrument-correct
  (Gold $0.01, BTC $1).</p>
  <div class="facts">
    <span class="chip"><b>Target</b> {d['meta']['rr']:.1f}R</span>
    <span class="chip"><b>Break-even</b> {be:.1f}%</span>
    <span class="chip"><b>Costs</b> none modelled</span>
    <span class="chip"><b>M5 &amp; M15</b> same window each</span>
  </div>

  <div class="grid">{cards}</div>

  <div class="warn">
    <h3>Read this alongside the numbers</h3>
    <p><b>Both instruments print a positive edge on every timeframe run</b> — Gold
    favours M5, Bitcoin is strong on both M5 and M15 — all clear the {be:.1f}%
    break-even. Encouraging that the pattern isn't FX-only.</p>
    <p><b>Different window from the FX study.</b> These use ~2022–2024 public data
    (a shorter, more recent slice), so don't compare their totals directly to the
    FX majors' decade-long totals — compare win rate / expectancy / PF instead.</p>
    <p><b>M3 is pending.</b> 3-minute candles need 1-minute data, which isn't freely
    available for Gold/BTC. Run <code>export_m1.py</code> on your own MT5 to dump
    M1, then <code>xau_btc_backtest.py</code> fills in M3 (and broker-accurate M5).</p>
    <p><b>No costs modelled.</b> As everywhere in this project — spread and slippage
    will lower these, most on the fastest timeframe. Demo-test before trusting them.</p>
  </div>

  <footer>
    <span>Second Entry (H2/L2) · Gold &amp; Bitcoin</span>
    <span>M5 &amp; M15 · ~2022–2024 · no costs modelled</span>
  </footer>
</div>
"""

out = os.path.join(HERE, "second_entry_instruments_report.html")
with open(out, "w") as f:
    f.write(html)
print("wrote", out, len(html), "bytes")
