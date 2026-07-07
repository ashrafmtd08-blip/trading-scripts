"""Generate the execution-timeframe comparison report from timeframe_results.json."""
import json
import os

HERE = os.path.dirname(__file__)
d = json.load(open(os.path.join(HERE, "timeframe_results.json")))
meta = d["meta"]
tfs = d["timeframes"]
ORDER = ["M3", "M5", "M15"]
PAIRS = meta["pairs"]

# timeframe accent colors (validated categorical palette)
COL = {"M3": ("#0f9d84", "#4bb6a6"), "M5": ("#c08a2b", "#d3ac5a"),
       "M15": ("#7b5fd0", "#9385d8")}  # (light, dark)

best_totr = max(ORDER, key=lambda t: tfs[t]["total_r"])
best_exp = max(ORDER, key=lambda t: tfs[t]["expectancy"])
max_totr = max(tfs[t]["total_r"] for t in ORDER)

# ---- per-timeframe KPI cards ----------------------------------------------
def tf_card(t):
    a = tfs[t]
    crown = " ★" if t == best_totr else ""
    return f"""
      <div class="tfcard" data-tf="{t}">
        <div class="tfhead"><span class="tfdot"></span><span class="tfname">{t}{crown}</span>
          <span class="tftag">{'most total R' if t==best_totr else ('best edge' if t==best_exp else '')}</span></div>
        <div class="tfbig">{a['total_r']:+.0f}<span class="unit">R</span></div>
        <div class="tfgrid">
          <div><span class="l">Win rate</span><span class="v">{a['win_rate']:.1f}%</span></div>
          <div><span class="l">Expectancy</span><span class="v">{a['expectancy']:+.2f}R</span></div>
          <div><span class="l">Trades</span><span class="v">{a['trades']:,}</span></div>
          <div><span class="l">Profit factor</span><span class="v">{a['profit_factor']:.2f}</span></div>
          <div><span class="l">Trades / day</span><span class="v">{a['trades_per_day']:.2f}</span></div>
          <div><span class="l">Cancelled</span><span class="v">{a['cancelled']:,}</span></div>
        </div>
      </div>"""
tf_cards = "".join(tf_card(t) for t in ORDER)

# ---- total-R bar chart -----------------------------------------------------
bars = "".join(f"""
      <div class="barrow">
        <span class="barlbl" data-tf="{t}">{t}</span>
        <div class="bartrack"><div class="barfill" data-tf="{t}" style="width:{round(100*tfs[t]['total_r']/max_totr,1)}%"></div></div>
        <span class="barval">{tfs[t]['total_r']:+.0f}R</span>
      </div>""" for t in ORDER)

# ---- per-pair heatmap (expectancy) ----------------------------------------
exp_vals = [tfs[t]["pairs"][p]["expectancy"] for t in ORDER for p in PAIRS]
emin, emax = min(exp_vals), max(exp_vals)
def heat(v):
    # 0..1 within observed expectancy range -> gold ramp intensity
    f = (v - emin) / (emax - emin) if emax > emin else 0.5
    return round(0.12 + 0.78 * f, 3)

heat_rows = ""
for p in PAIRS:
    cells = ""
    # best tf for this pair (by total R)
    bestp = max(ORDER, key=lambda t: tfs[t]["pairs"][p]["total_r"])
    for t in ORDER:
        pr = tfs[t]["pairs"][p]
        star = "<span class='star'>★</span>" if t == bestp else ""
        cells += (f"<td class='hc' style='--a:{heat(pr['expectancy'])}'>"
                  f"<span class='he'>{pr['expectancy']:+.2f}R</span>"
                  f"<span class='ht'>{pr['total_r']:+.0f}R · {pr['win_rate']:.0f}%</span>{star}</td>")
    heat_rows += f"<tr><td class='pl'>{p}</td>{cells}</tr>"

# aggregate deltas for verdict copy
d_m5_m3 = tfs["M5"]["total_r"] - tfs["M3"]["total_r"]

html = f"""<title>Second Entry (H2/L2) — M3 vs M5 vs M15</title>
<style>
  :root {{
    --bg:#f4f5f2; --surface:#fbfbf9; --surface-2:#eef0ea;
    --ink:#181d1c; --ink-2:#4b5350; --ink-3:#828c88; --line:#dcded7;
    --gold:#b98a2e; --pos:#1f8f6f; --neg:#c0523a;
    --m3:#0f9d84; --m5:#c08a2b; --m15:#7b5fd0;
    --shadow:0 1px 2px rgba(20,28,26,.05),0 8px 26px rgba(20,28,26,.06);
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
  }}
  @media (prefers-color-scheme:dark) {{
    :root {{ --bg:#0e1413; --surface:#141b1a; --surface-2:#1b2322;
      --ink:#e9ede9; --ink-2:#a7b0ac; --ink-3:#6d7773; --line:#26302e;
      --gold:#d3ac5a; --pos:#43b892; --neg:#dd6b50;
      --m3:#4bb6a6; --m5:#d3ac5a; --m15:#9385d8;
      --shadow:0 1px 2px rgba(0,0,0,.35),0 12px 34px rgba(0,0,0,.4); }}
  }}
  :root[data-theme="light"] {{ --bg:#f4f5f2; --surface:#fbfbf9; --surface-2:#eef0ea;
    --ink:#181d1c; --ink-2:#4b5350; --ink-3:#828c88; --line:#dcded7;
    --gold:#b98a2e; --pos:#1f8f6f; --neg:#c0523a; --m3:#0f9d84; --m5:#c08a2b; --m15:#7b5fd0;
    --shadow:0 1px 2px rgba(20,28,26,.05),0 8px 26px rgba(20,28,26,.06); }}
  :root[data-theme="dark"] {{ --bg:#0e1413; --surface:#141b1a; --surface-2:#1b2322;
    --ink:#e9ede9; --ink-2:#a7b0ac; --ink-3:#6d7773; --line:#26302e;
    --gold:#d3ac5a; --pos:#43b892; --neg:#dd6b50; --m3:#4bb6a6; --m5:#d3ac5a; --m15:#9385d8;
    --shadow:0 1px 2px rgba(0,0,0,.35),0 12px 34px rgba(0,0,0,.4); }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans); line-height:1.55; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:clamp(20px,4vw,52px) clamp(16px,4vw,40px) 80px; }}
  .mono {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}
  .mut {{ color:var(--ink-3); }}

  header.mast {{ border-bottom:1px solid var(--line); padding-bottom:26px; margin-bottom:30px; }}
  .eyebrow {{ font-family:var(--mono); font-size:12px; letter-spacing:.16em; text-transform:uppercase; color:var(--gold); margin:0 0 14px; }}
  h1 {{ font-family:var(--serif); font-weight:600; font-size:clamp(30px,5vw,46px); line-height:1.05; letter-spacing:-.01em; margin:0 0 14px; text-wrap:balance; }}
  h1 em {{ font-style:italic; color:var(--gold); }}
  .sub {{ color:var(--ink-2); font-size:16.5px; max-width:62ch; margin:0; }}
  .facts {{ display:flex; flex-wrap:wrap; gap:8px 10px; margin-top:20px; }}
  .chip {{ font-family:var(--mono); font-size:12.5px; color:var(--ink-2); background:var(--surface-2); border:1px solid var(--line); border-radius:999px; padding:5px 12px; }}
  .chip b {{ color:var(--ink); font-weight:600; }}

  .verdict {{ background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--m5); border-radius:12px; padding:18px 20px; margin:0 0 32px; box-shadow:var(--shadow); }}
  .verdict .tag {{ font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--m5); }}
  .verdict p {{ margin:8px 0 0; font-size:16px; }}
  .verdict b.m5 {{ color:var(--m5); }} .verdict b.m15 {{ color:var(--m15); }} .verdict b.pos {{ color:var(--pos); }}

  section {{ margin-bottom:42px; }}
  h2 {{ font-family:var(--serif); font-weight:600; font-size:22px; letter-spacing:-.01em; margin:0 0 4px; }}
  .lede {{ color:var(--ink-2); font-size:14.5px; margin:0 0 18px; max-width:66ch; }}

  /* tf cards */
  .tfrow {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
  @media (max-width:720px) {{ .tfrow {{ grid-template-columns:1fr; }} }}
  .tfcard {{ background:var(--surface); border:1px solid var(--line); border-top:3px solid var(--tf); border-radius:14px; padding:18px 20px; box-shadow:var(--shadow); }}
  .tfcard[data-tf="M3"] {{ --tf:var(--m3); }} .tfcard[data-tf="M5"] {{ --tf:var(--m5); }} .tfcard[data-tf="M15"] {{ --tf:var(--m15); }}
  .tfhead {{ display:flex; align-items:center; gap:8px; }}
  .tfdot {{ width:10px; height:10px; border-radius:50%; background:var(--tf); }}
  .tfname {{ font-family:var(--mono); font-weight:600; font-size:15px; }}
  .tftag {{ margin-left:auto; font-family:var(--mono); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--tf); }}
  .tfbig {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:38px; font-weight:600; letter-spacing:-.02em; color:var(--tf); margin:10px 0 14px; line-height:1; }}
  .tfbig .unit {{ font-size:20px; margin-left:2px; }}
  .tfgrid {{ display:grid; grid-template-columns:1fr 1fr; gap:9px 16px; }}
  .tfgrid > div {{ display:flex; justify-content:space-between; align-items:baseline; border-top:1px solid var(--line); padding-top:7px; }}
  .tfgrid .l {{ font-size:12.5px; color:var(--ink-3); }}
  .tfgrid .v {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-weight:600; font-size:13.5px; }}

  /* bar chart */
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:22px 24px; box-shadow:var(--shadow); }}
  .barrow {{ display:flex; align-items:center; gap:14px; margin:14px 0; }}
  .barlbl {{ font-family:var(--mono); font-weight:600; font-size:14px; width:38px; }}
  .barlbl[data-tf="M3"] {{ color:var(--m3); }} .barlbl[data-tf="M5"] {{ color:var(--m5); }} .barlbl[data-tf="M15"] {{ color:var(--m15); }}
  .bartrack {{ flex:1; height:26px; background:var(--surface-2); border-radius:6px; overflow:hidden; }}
  .barfill {{ height:100%; border-radius:6px; }}
  .barfill[data-tf="M3"] {{ background:var(--m3); }} .barfill[data-tf="M5"] {{ background:var(--m5); }} .barfill[data-tf="M15"] {{ background:var(--m15); }}
  .barval {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-weight:600; width:64px; text-align:right; }}
  .cap {{ font-size:12.5px; color:var(--ink-3); margin:14px 0 0; font-family:var(--mono); }}

  /* heatmap */
  .heat-scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); }}
  table.heat {{ border-collapse:collapse; width:100%; min-width:560px; background:var(--surface); }}
  table.heat th {{ font-family:var(--mono); font-size:12px; padding:13px 10px; border-bottom:1px solid var(--line); color:var(--ink-2); font-weight:600; }}
  table.heat th.tfh[data-tf="M3"] {{ color:var(--m3); }} table.heat th.tfh[data-tf="M5"] {{ color:var(--m5); }} table.heat th.tfh[data-tf="M15"] {{ color:var(--m15); }}
  table.heat td.pl {{ font-family:var(--mono); font-weight:600; font-size:13px; padding:0 14px; text-align:left; white-space:nowrap; }}
  td.hc {{ position:relative; padding:11px 10px; text-align:center; border-left:2px solid var(--surface); background:color-mix(in srgb, var(--gold) calc(var(--a)*100%), var(--surface)); }}
  td.hc .he {{ display:block; font-family:var(--mono); font-variant-numeric:tabular-nums; font-weight:600; font-size:14px; color:var(--ink); }}
  td.hc .ht {{ display:block; font-family:var(--mono); font-size:10.5px; color:var(--ink-2); margin-top:2px; }}
  td.hc .star {{ position:absolute; top:4px; right:6px; color:var(--gold); font-size:11px; }}
  tr:not(:last-child) td.hc {{ border-bottom:2px solid var(--surface); }}

  .method {{ columns:2; column-gap:34px; margin-top:6px; }}
  @media (max-width:640px) {{ .method {{ columns:1; }} }}
  .method .item {{ break-inside:avoid; margin-bottom:18px; }}
  .method h3 {{ font-family:var(--mono); font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--gold); margin:0 0 5px; }}
  .method p {{ margin:0; font-size:13.5px; color:var(--ink-2); }}
  .warn {{ background:var(--surface-2); border:1px solid var(--line); border-radius:12px; padding:16px 20px; margin-top:24px; }}
  .warn h3 {{ margin:0 0 6px; font-family:var(--serif); font-size:16px; }}
  .warn p {{ margin:0; font-size:13.5px; color:var(--ink-2); }}
  footer {{ margin-top:50px; padding-top:20px; border-top:1px solid var(--line); font-family:var(--mono); font-size:12px; color:var(--ink-3); display:flex; flex-wrap:wrap; gap:6px 16px; justify-content:space-between; }}
</style>

<div class="wrap">
  <header class="mast">
    <p class="eyebrow">Strategy Backtest · Timeframe Study</p>
    <h1>Which execution timeframe wins — <em>M3, M5 or M15?</em></h1>
    <p class="sub">The same Second Entry (H2/L2) pull-back strategy, run on three
    intraday candle sizes built from one shared 1-minute feed for seven majors,
    2015–2025. Identical rules and window — only the timeframe changes.</p>
    <div class="facts">
      <span class="chip"><b>Pairs</b> 7 majors</span>
      <span class="chip"><b>Source</b> M1 → resampled</span>
      <span class="chip"><b>Window</b> 2015–2025</span>
      <span class="chip"><b>Target</b> {meta['rr']:.1f}R fixed</span>
      <span class="chip"><b>Break-even</b> {meta['breakeven_win_rate']:.1f}%</span>
    </div>
  </header>

  <div class="verdict">
    <span class="tag">Verdict</span>
    <p><b class="m5">M5 is the most profitable</b> by total accumulated return
    (<b class="pos">{tfs['M5']['total_r']:+.0f}R</b>), just ahead of M3
    ({tfs['M3']['total_r']:+.0f}R) on ~10% fewer trades — so it earns the same money
    with less exposure. <b class="m15">M15 has the best per-trade quality</b>
    ({tfs['M15']['expectancy']:+.2f}R, {tfs['M15']['win_rate']:.1f}% win, PF
    {tfs['M15']['profit_factor']:.2f}) but trades less, so it accumulates less.
    All three clear the {meta['breakeven_win_rate']:.1f}% break-even floor comfortably.
    Costs are not modelled — and since lower timeframes trade more often for smaller
    stops, spread would erode M3 hardest, tilting the practical choice toward
    <b class="m5">M5</b>.</p>
  </div>

  <section>
    <h2>The three timeframes head-to-head</h2>
    <p class="lede">Aggregate across all seven majors. ★ marks the timeframe with the
    highest total return.</p>
    <div class="tfrow">{tf_cards}</div>
  </section>

  <section>
    <h2>Total return by timeframe</h2>
    <p class="lede">Sum of R over the full 2015–2025 window, all pairs combined.
    M3 and M5 finish neck-and-neck; M15 trails on volume.</p>
    <div class="card">{bars}
      <p class="cap">1R = one risk unit. M5 reaches the top with {tfs['M5']['trades']:,} trades vs M3's {tfs['M3']['trades']:,}.</p>
    </div>
  </section>

  <section>
    <h2>Per-pair × timeframe</h2>
    <p class="lede">Cell shading = expectancy (R/trade); small line = total R · win rate.
    ★ = the best timeframe for that pair by total R. No single timeframe wins
    everywhere — GBPUSD and USDJPY love M3, while AUD/NZD/CAD prefer M15.</p>
    <div class="heat-scroll">
      <table class="heat">
        <thead><tr><th style="text-align:left">Pair</th>
          <th class="tfh" data-tf="M3">M3</th><th class="tfh" data-tf="M5">M5</th><th class="tfh" data-tf="M15">M15</th></tr></thead>
        <tbody>{heat_rows}</tbody>
      </table>
    </div>
    <p class="cap">Darker = stronger per-trade edge. Range {emin:+.2f}R to {emax:+.2f}R.</p>
  </section>

  <section>
    <h2>Method &amp; caveats</h2>
    <div class="method">
      <div class="item"><h3>One source, three views</h3><p>M3/M5/M15 are resampled from the same M1 (1-minute) OHLCV feed per pair, so differences are purely the timeframe — not different data.</p></div>
      <div class="item"><h3>Identical engine</h3><p>Same EMA(20)/H1-H2/FVG/ADX rules, same 2R target, same 12-bar pending expiry, same forward-replay win/loss (SL-first on ties) as the H4 report.</p></div>
      <div class="item"><h3>No costs modelled</h3><p>Spread, slippage and commission are excluded. This is deliberate — it isolates the timeframe effect on the raw edge, but flatters lower timeframes most.</p></div>
      <div class="item"><h3>Why M5 over M3</h3><p>Near-identical gross R, fewer trades, larger stops in price terms → a better cost-adjusted profile once real spread is added.</p></div>
      <div class="item"><h3>Data</h3><p>Seven majors (EUR/GBP/JPY/CHF/CAD/AUD/NZD vs USD), Jan 2015–Dec 2025, ~4.0M M1 bars each, from a public parquet dataset.</p></div>
      <div class="item"><h3>Point inputs</h3><p>EMA-touch 300 pts and 20-pt buffers are mapped per symbol (JPY = 3-dp). These intraday scales suit M3–M15, unlike the H4 study.</p></div>
    </div>
    <div class="warn">
      <h3>Read this before trading it</h3>
      <p>These are frictionless results — an upper bound, not a forecast. The timeframe
      ranking is robust across pairs, but real spread/slippage will compress every
      number and hit M3 the most. Validate on a demo / Strategy Tester with your
      broker's actual costs before committing to a timeframe.</p>
    </div>
  </section>

  <footer>
    <span>Second Entry (H2/L2) · timeframe study</span>
    <span>M3 / M5 / M15 · 7 majors · 2015–2025 · no costs modelled</span>
  </footer>
</div>
"""

out = os.path.join(HERE, "second_entry_timeframe_report.html")
with open(out, "w") as f:
    f.write(html)
print("wrote", out, len(html), "bytes")
