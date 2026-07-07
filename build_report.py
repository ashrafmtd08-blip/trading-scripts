"""Generate a self-contained HTML report from backtest_results.json."""
import json
import os

HERE = os.path.dirname(__file__)
data = json.load(open(os.path.join(HERE, "backtest_results.json")))

meta = data["meta"]
pairs = data["pairs"]
allp = data["all"]
ec = data["equity_curve"]

# max drawdown in R
peak, dd = -1e9, 0.0
for p in ec:
    peak = max(peak, p["cum_r"])
    dd = min(dd, p["cum_r"] - peak)
max_dd = round(dd, 1)
final_r = ec[-1]["cum_r"]

payload = json.dumps({
    "equity": [[p["date"], p["cum_r"]] for p in ec],
    "pairs": pairs,
}, separators=(",", ":"))

def fmt_sign(x, suffix="R"):
    return f"{x:+.2f}{suffix}" if isinstance(x, float) else f"{x:+d}{suffix}"

# ---- per-pair rows ---------------------------------------------------------
max_totr = max(p["total_r"] for p in pairs)
rows = []
for p in pairs:
    wr = p["win_rate"]
    exp = p["expectancy"]
    totr = p["total_r"]
    rej = p["rej"]
    totrej = rej["trend"] + rej["ema"] + rej["quality"] + rej["fvg"]
    barw = round(100 * totr / max_totr, 1)
    rows.append(f"""
      <tr>
        <td class="sym">{p['symbol']}</td>
        <td class="num">{p['trades']}</td>
        <td class="num">{p['wins']}<span class="mut">/</span>{p['losses']}</td>
        <td class="num">
          <div class="wr">
            <div class="wrbar"><span style="width:{wr}%"></span></div>
            <span class="wrnum">{wr:.1f}%</span>
          </div>
        </td>
        <td class="num {'pos' if exp>=0 else 'neg'}">{exp:+.2f}R</td>
        <td class="num">
          <div class="rbar">
            <div class="rbarfill" style="width:{barw}%"></div>
            <span class="rnum">{totr:+.0f}R</span>
          </div>
        </td>
        <td class="num">{p['profit_factor']:.2f}</td>
        <td class="num mut">{p['cancelled']}</td>
        <td class="num rej" title="Trend / EMA-touch / Quality / FVG">{rej['trend']}<span class="mut">/</span>{rej['ema']}<span class="mut">/</span>{rej['quality']}<span class="mut">/</span>{rej['fvg']}</td>
      </tr>""")
rows_html = "".join(rows)

# ---- aggregate rejection totals -------------------------------------------
agg_rej = {"trend": 0, "ema": 0, "quality": 0, "fvg": 0}
for p in pairs:
    for k in agg_rej:
        agg_rej[k] += p["rej"][k]
passed = allp["trades"]
rej_total = sum(agg_rej.values())
gate_items = [
    ("Trend / ADX", agg_rej["trend"], "EMA slope wrong way or ADX below "
     f"{meta['adx_min']:.0f} — no established trend."),
    ("Bar quality", agg_rej["quality"], "H2/L2 bar didn't close with the break "
     "in the upper/lower half of its range."),
    ("FVG", agg_rej["fvg"], "No Fair Value Gap on the signal candle or the one "
     "right after it."),
    ("EMA touch", agg_rej["ema"], f"Pull-back never came within "
     f"{meta['ema_touch_pts']} points of the EMA."),
]
gate_items.sort(key=lambda x: -x[1])
gate_max = max(x[1] for x in gate_items)
gate_html = "".join(
    f"""
      <div class="gate">
        <div class="gate-h"><span>{name}</span><span class="num">{cnt:,}</span></div>
        <div class="gate-track"><div class="gate-fill" style="width:{round(100*cnt/gate_max,1)}%"></div></div>
        <p>{desc}</p>
      </div>""" for name, cnt, desc in gate_items)

html = f"""<title>Second Entry (H2/L2) — FX Majors Backtest</title>
<style>
  :root {{
    --bg:#f4f5f2; --surface:#fbfbf9; --surface-2:#eef0ea;
    --ink:#181d1c; --ink-2:#4b5350; --ink-3:#828c88; --line:#dcded7;
    --gold:#b98a2e; --gold-soft:#cda349;
    --pos:#1f8f6f; --neg:#c0523a;
    --shadow:0 1px 2px rgba(20,28,26,.05),0 8px 26px rgba(20,28,26,.06);
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
  }}
  @media (prefers-color-scheme:dark) {{
    :root {{
      --bg:#0e1413; --surface:#141b1a; --surface-2:#1b2322;
      --ink:#e9ede9; --ink-2:#a7b0ac; --ink-3:#6d7773; --line:#26302e;
      --gold:#d3ac5a; --gold-soft:#c79f4e;
      --pos:#43b892; --neg:#dd6b50;
      --shadow:0 1px 2px rgba(0,0,0,.35),0 12px 34px rgba(0,0,0,.4);
    }}
  }}
  :root[data-theme="light"] {{
    --bg:#f4f5f2; --surface:#fbfbf9; --surface-2:#eef0ea;
    --ink:#181d1c; --ink-2:#4b5350; --ink-3:#828c88; --line:#dcded7;
    --gold:#b98a2e; --gold-soft:#cda349; --pos:#1f8f6f; --neg:#c0523a;
    --shadow:0 1px 2px rgba(20,28,26,.05),0 8px 26px rgba(20,28,26,.06);
  }}
  :root[data-theme="dark"] {{
    --bg:#0e1413; --surface:#141b1a; --surface-2:#1b2322;
    --ink:#e9ede9; --ink-2:#a7b0ac; --ink-3:#6d7773; --line:#26302e;
    --gold:#d3ac5a; --gold-soft:#c79f4e; --pos:#43b892; --neg:#dd6b50;
    --shadow:0 1px 2px rgba(0,0,0,.35),0 12px 34px rgba(0,0,0,.4);
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:var(--sans); line-height:1.55;
    -webkit-font-smoothing:antialiased;
  }}
  .wrap {{ max-width:1060px; margin:0 auto; padding:clamp(20px,4vw,52px) clamp(16px,4vw,40px) 80px; }}
  .num {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}
  .mut {{ color:var(--ink-3); }}
  .pos {{ color:var(--pos); }} .neg {{ color:var(--neg); }}

  /* masthead */
  header.mast {{ border-bottom:1px solid var(--line); padding-bottom:26px; margin-bottom:30px; }}
  .eyebrow {{ font-family:var(--mono); font-size:12px; letter-spacing:.16em; text-transform:uppercase; color:var(--gold); margin:0 0 14px; }}
  h1 {{ font-family:var(--serif); font-weight:600; font-size:clamp(30px,5vw,46px); line-height:1.05; letter-spacing:-.01em; margin:0 0 14px; text-wrap:balance; }}
  h1 em {{ font-style:italic; color:var(--gold); }}
  .sub {{ color:var(--ink-2); font-size:16.5px; max-width:60ch; margin:0; }}
  .facts {{ display:flex; flex-wrap:wrap; gap:8px 10px; margin-top:20px; }}
  .chip {{ font-family:var(--mono); font-size:12.5px; color:var(--ink-2); background:var(--surface-2); border:1px solid var(--line); border-radius:999px; padding:5px 12px; }}
  .chip b {{ color:var(--ink); font-weight:600; }}

  /* verdict */
  .verdict {{ display:flex; align-items:flex-start; gap:14px; background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--gold); border-radius:12px; padding:18px 20px; margin:0 0 30px; box-shadow:var(--shadow); }}
  .verdict .tag {{ font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--gold); padding-top:3px; white-space:nowrap; }}
  .verdict p {{ margin:0; font-size:16px; color:var(--ink); }}
  .verdict b {{ color:var(--pos); }}

  /* KPI grid */
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin-bottom:36px; }}
  .kpi {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px 18px; box-shadow:var(--shadow); }}
  .kpi .k {{ font-size:12px; letter-spacing:.04em; text-transform:uppercase; color:var(--ink-3); margin:0 0 8px; font-family:var(--mono); }}
  .kpi .v {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:30px; font-weight:600; letter-spacing:-.02em; line-height:1; }}
  .kpi .d {{ font-size:12.5px; color:var(--ink-2); margin:8px 0 0; }}

  section {{ margin-bottom:40px; }}
  h2 {{ font-family:var(--serif); font-weight:600; font-size:22px; letter-spacing:-.01em; margin:0 0 4px; }}
  .lede {{ color:var(--ink-2); font-size:14.5px; margin:0 0 18px; max-width:64ch; }}

  /* chart */
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:20px; box-shadow:var(--shadow); }}
  .chart-wrap {{ position:relative; }}
  canvas {{ display:block; width:100%; height:auto; }}
  .tip {{ position:absolute; pointer-events:none; opacity:0; transition:opacity .1s; background:var(--ink); color:var(--bg); font-family:var(--mono); font-size:12px; padding:6px 9px; border-radius:7px; white-space:nowrap; transform:translate(-50%,-130%); z-index:5; }}
  .tip b {{ color:var(--gold-soft); }}
  .cap {{ font-size:12.5px; color:var(--ink-3); margin:12px 0 0; font-family:var(--mono); }}

  /* table */
  .tbl-scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); }}
  table {{ border-collapse:collapse; width:100%; min-width:720px; background:var(--surface); font-size:14px; }}
  thead th {{ font-family:var(--mono); font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-3); text-align:right; padding:14px 14px; border-bottom:1px solid var(--line); font-weight:500; }}
  thead th:first-child {{ text-align:left; }}
  tbody td {{ padding:12px 14px; border-bottom:1px solid var(--line); text-align:right; }}
  tbody tr:last-child td {{ border-bottom:none; }}
  tbody tr:hover {{ background:var(--surface-2); }}
  td.sym {{ text-align:left; font-family:var(--mono); font-weight:600; color:var(--ink); letter-spacing:.02em; }}
  .wr {{ display:flex; align-items:center; gap:9px; justify-content:flex-end; }}
  .wrbar {{ width:64px; height:6px; background:var(--surface-2); border-radius:99px; overflow:hidden; }}
  .wrbar span {{ display:block; height:100%; background:var(--ink-3); border-radius:99px; }}
  .wrnum {{ min-width:46px; }}
  .rbar {{ display:flex; align-items:center; gap:9px; justify-content:flex-end; }}
  .rbarfill {{ height:8px; background:linear-gradient(90deg,var(--gold-soft),var(--gold)); border-radius:4px; min-width:2px; }}
  .rnum {{ min-width:42px; color:var(--pos); font-weight:600; }}
  td.rej {{ color:var(--ink-2); font-size:12.5px; }}
  tr.total td {{ border-top:2px solid var(--line); font-weight:600; background:var(--surface-2); }}
  tr.total td.sym {{ color:var(--gold); }}

  /* gates */
  .gates {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }}
  .gate {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px 18px; box-shadow:var(--shadow); }}
  .gate-h {{ display:flex; justify-content:space-between; align-items:baseline; font-family:var(--mono); font-size:13px; }}
  .gate-h .num {{ font-size:17px; font-weight:600; }}
  .gate-track {{ height:6px; background:var(--surface-2); border-radius:99px; margin:10px 0; overflow:hidden; }}
  .gate-fill {{ height:100%; background:var(--neg); opacity:.7; border-radius:99px; }}
  .gate p {{ margin:0; font-size:12.5px; color:var(--ink-2); line-height:1.5; }}

  /* method / caveats */
  .method {{ columns:2; column-gap:34px; }}
  @media (max-width:640px) {{ .method {{ columns:1; }} }}
  .method .item {{ break-inside:avoid; margin-bottom:18px; }}
  .method h3 {{ font-family:var(--mono); font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--gold); margin:0 0 5px; }}
  .method p {{ margin:0; font-size:13.5px; color:var(--ink-2); }}
  .warn {{ background:var(--surface-2); border:1px solid var(--line); border-radius:12px; padding:16px 20px; margin-top:26px; }}
  .warn h3 {{ margin:0 0 6px; font-family:var(--serif); font-size:16px; }}
  .warn p {{ margin:0; font-size:13.5px; color:var(--ink-2); }}
  footer {{ margin-top:50px; padding-top:20px; border-top:1px solid var(--line); font-family:var(--mono); font-size:12px; color:var(--ink-3); display:flex; flex-wrap:wrap; gap:6px 16px; justify-content:space-between; }}
</style>

<div class="wrap">
  <header class="mast">
    <p class="eyebrow">Strategy Backtest · FX Majors</p>
    <h1>Second Entry <em>(H2/L2)</em> pull-back strategy</h1>
    <p class="sub">A two-legged pull-back system — EMA(20) trend, a failed first
    break (H1/L1), a deeper pull-back, then the second break as entry, gated by a
    Fair Value Gap and a trend/ADX filter, with a fixed {meta['rr']:.0f}R target.
    Replayed bar-by-bar across six major pairs.</p>
    <div class="facts">
      <span class="chip"><b>Timeframe</b> H4</span>
      <span class="chip"><b>Window</b> {meta['start'][:7]} → 2026-02</span>
      <span class="chip"><b>Pairs</b> 6 majors</span>
      <span class="chip"><b>Target</b> {meta['rr']:.1f}R fixed</span>
      <span class="chip"><b>ADX ≥</b> {meta['adx_min']:.0f}</span>
      <span class="chip"><b>Trades</b> {allp['trades']}</span>
    </div>
  </header>

  <div class="verdict">
    <span class="tag">Verdict</span>
    <p>Across {allp['trades']} tradeable signals the edge holds on every pair — a
    <b>{allp['win_rate']:.1f}% win rate at {meta['rr']:.0f}R</b> gives
    <b>+{allp['expectancy']:.2f}R per trade</b>, comfortably above the
    {meta['breakeven_win_rate']:.1f}% break-even floor. Compounded over the window:
    <b>+{final_r:.0f}R</b> with a shallow {abs(max_dd):.0f}R peak-to-trough dip.
    Costs (spread, slippage, commission) are <em>not</em> modelled.</p>
  </div>

  <div class="kpis">
    <div class="kpi"><p class="k">Win rate</p><div class="v">{allp['win_rate']:.1f}%</div><p class="d">{allp['wins']} wins · {allp['losses']} losses</p></div>
    <div class="kpi"><p class="k">Expectancy</p><div class="v pos">+{allp['expectancy']:.2f}R</div><p class="d">per resolved trade</p></div>
    <div class="kpi"><p class="k">Total return</p><div class="v pos">+{final_r:.0f}R</div><p class="d">sum of R, 2010–2026</p></div>
    <div class="kpi"><p class="k">Profit factor</p><div class="v">{allp['profit_factor']:.2f}</div><p class="d">gross win ÷ gross loss</p></div>
    <div class="kpi"><p class="k">Max drawdown</p><div class="v">−{abs(max_dd):.0f}R</div><p class="d">worst peak-to-trough</p></div>
    <div class="kpi"><p class="k">Break-even</p><div class="v mut">{meta['breakeven_win_rate']:.1f}%</div><p class="d">floor at {meta['rr']:.0f}R</p></div>
  </div>

  <section>
    <h2>Equity curve</h2>
    <p class="lede">Cumulative R over all {len(ec)} resolved trades from the six pairs,
    ordered by signal date. Each win adds {meta['rr']:.0f}R, each loss subtracts 1R.</p>
    <div class="card">
      <div class="chart-wrap">
        <canvas id="eq" width="1000" height="380" aria-label="Cumulative R equity curve"></canvas>
        <div class="tip" id="tip"></div>
      </div>
      <p class="cap">One risk unit = 1R. Diversifying across six pairs keeps the deepest dip to just {abs(max_dd):.0f}R.</p>
    </div>
  </section>

  <section>
    <h2>Per-pair breakdown</h2>
    <p class="lede">Every major cleared the {meta['breakeven_win_rate']:.1f}% break-even
    hurdle and posted positive expectancy. GBPUSD led, USDCAD lagged.</p>
    <div class="tbl-scroll">
      <table>
        <thead><tr>
          <th>Pair</th><th>Trades</th><th>W/L</th><th>Win rate</th>
          <th>Expectancy</th><th>Total R</th><th>PF</th><th>Cxl</th>
          <th>Rej T/E/Q/F</th>
        </tr></thead>
        <tbody>{rows_html}
          <tr class="total">
            <td class="sym">ALL</td>
            <td class="num">{allp['trades']}</td>
            <td class="num">{allp['wins']}<span class="mut">/</span>{allp['losses']}</td>
            <td class="num">{allp['win_rate']:.1f}%</td>
            <td class="num pos">+{allp['expectancy']:.2f}R</td>
            <td class="num pos">+{final_r:.0f}R</td>
            <td class="num">{allp['profit_factor']:.2f}</td>
            <td class="num mut">{allp['cancelled']}</td>
            <td class="num rej">{agg_rej['trend']}<span class="mut">/</span>{agg_rej['ema']}<span class="mut">/</span>{agg_rej['quality']}<span class="mut">/</span>{agg_rej['fvg']}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="cap">Cxl = pending order expired unfilled. Rej = candidates killed by the Trend / EMA-touch / Quality / FVG gate.</p>
  </section>

  <section>
    <h2>What the filters throw away</h2>
    <p class="lede">The engine scanned {allp['candidates']:,} raw H2/L2 patterns and let only
    {passed} through to trade. Here's which gate rejected the most (by first-failing gate).</p>
    <div class="gates">{gate_html}</div>
  </section>

  <section>
    <h2>Method &amp; caveats</h2>
    <div class="method">
      <div class="item"><h3>Data</h3><p>H4 OHLC for the six majors, 2010→Feb 2026 (~1,550 bars/pair/year). H4 is the finest timeframe available for all majors in the free source used.</p></div>
      <div class="item"><h3>Fill model</h3><p>Signals become buy/sell-stop pending orders that expire after 12 bars. A fill needs the bar's high/low to reach the entry; unfilled orders are cancelled, not counted as trades.</p></div>
      <div class="item"><h3>Win / loss</h3><p>Once filled, the trade is walked forward against real highs/lows — whichever of SL or TP is hit first decides it. Ties within one bar are scored as losses (conservative).</p></div>
      <div class="item"><h3>Not modelled</h3><p>No spread, slippage or commission — exactly as the session notes flag. On H4 majors spread is a small fraction of a typical stop, but it still trims the real edge.</p></div>
      <div class="item"><h3>Timeframe note</h3><p>The notes developed this on Gold M5. Point-based inputs (EMA-touch 300 pts, buffer 20 pts) are mapped per symbol; behaviour on H4 FX differs from M5 metal.</p></div>
      <div class="item"><h3>EA extras</h3><p>The live EA adds 1%-risk position sizing and break-even at 1R. Neither is in this win-rate methodology, which mirrors the indicator's on-chart replay.</p></div>
    </div>
    <div class="warn">
      <h3>Read this before trading it</h3>
      <p>A frictionless backtest is an upper bound, not a forecast. The result says the
      <em>pattern</em> carried a positive expectancy on historical H4 data — it does not
      account for spread/slippage, execution gaps, regime change, or the fact that these
      inputs were tuned on a different instrument and timeframe. Validate on a demo /
      Strategy Tester with real costs before risking capital.</p>
    </div>
  </section>

  <footer>
    <span>Second Entry (H2/L2) · forward-replay backtest</span>
    <span>H4 · {meta['start'][:7]}–2026-02 · {allp['trades']} trades · no costs modelled</span>
  </footer>
</div>

<script>
const DATA = {payload};
(function(){{
  const root = document.documentElement;
  const cv = document.getElementById('eq');
  const tip = document.getElementById('tip');
  const eq = DATA.equity;              // [[date, cumR], ...]
  const ctx = cv.getContext('2d');
  const DPR = Math.min(window.devicePixelRatio||1, 2);
  let W, H, plot;

  function css(v){{ return getComputedStyle(root).getPropertyValue(v).trim(); }}

  function layout(){{
    const rect = cv.getBoundingClientRect();
    W = rect.width; H = rect.height;
    cv.width = W*DPR; cv.height = H*DPR;
    ctx.setTransform(DPR,0,0,DPR,0,0);
    plot = {{l:52, r:16, t:16, b:30, w:W-68, h:H-46}};
  }}

  function scales(){{
    const xs = eq.map((_,i)=>i);
    const ys = eq.map(d=>d[1]);
    const minY = Math.min(0, ...ys), maxY = Math.max(...ys);
    const padY = (maxY-minY)*0.06;
    return {{
      x:i => plot.l + (i/(eq.length-1))*plot.w,
      y:v => plot.t + plot.h - ((v-minY)/((maxY+padY)-minY))*plot.h,
      minY, maxY:maxY+padY
    }};
  }}

  function niceStep(range, target){{
    const raw = range/target, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const n = raw/mag; const s = n<1.5?1:n<3?2:n<7?5:10; return s*mag;
  }}

  function draw(){{
    layout();
    const s = scales();
    ctx.clearRect(0,0,W,H);
    const ink3 = css('--ink-3'), line = css('--line'), gold = css('--gold');
    const goldSoft = css('--gold-soft'), ink2 = css('--ink-2');

    // y grid
    ctx.font = "11px ui-monospace,Menlo,monospace";
    ctx.textBaseline = "middle";
    const step = niceStep(s.maxY - s.minY, 5);
    ctx.strokeStyle = line; ctx.fillStyle = ink3; ctx.lineWidth = 1;
    for(let v=Math.ceil(s.minY/step)*step; v<=s.maxY; v+=step){{
      const y = s.y(v);
      ctx.globalAlpha = v===0?0.9:0.5;
      ctx.beginPath(); ctx.moveTo(plot.l, y); ctx.lineTo(plot.l+plot.w, y); ctx.stroke();
      ctx.globalAlpha = 1; ctx.textAlign="right";
      ctx.fillText((v>0?'+':'')+v+'R', plot.l-8, y);
    }}

    // x year ticks
    ctx.textAlign="center"; ctx.textBaseline="top";
    let lastYr=null;
    eq.forEach((d,i)=>{{
      const yr = d[0].slice(0,4);
      if(yr!==lastYr && (+yr)%3===0){{
        lastYr=yr;
        const x=s.x(i);
        ctx.fillStyle=ink3; ctx.fillText(yr, x, plot.t+plot.h+8);
      }} else if(yr!==lastYr){{ lastYr=yr; }}
    }});

    // area fill
    const grad = ctx.createLinearGradient(0,plot.t,0,plot.t+plot.h);
    grad.addColorStop(0, hexA(goldSoft,0.28));
    grad.addColorStop(1, hexA(goldSoft,0.02));
    ctx.beginPath();
    ctx.moveTo(s.x(0), s.y(eq[0][1]));
    eq.forEach((d,i)=>ctx.lineTo(s.x(i), s.y(d[1])));
    ctx.lineTo(s.x(eq.length-1), s.y(s.minY));
    ctx.lineTo(s.x(0), s.y(s.minY));
    ctx.closePath(); ctx.fillStyle=grad; ctx.fill();

    // line
    ctx.beginPath();
    eq.forEach((d,i)=>{{ const x=s.x(i), y=s.y(d[1]); i?ctx.lineTo(x,y):ctx.moveTo(x,y); }});
    ctx.strokeStyle=gold; ctx.lineWidth=2; ctx.lineJoin="round"; ctx.stroke();

    // endpoint
    const ex=s.x(eq.length-1), ey=s.y(eq[eq.length-1][1]);
    ctx.beginPath(); ctx.arc(ex,ey,4,0,7); ctx.fillStyle=gold; ctx.fill();
    ctx.beginPath(); ctx.arc(ex,ey,4,0,7);
    ctx.strokeStyle=css('--surface'); ctx.lineWidth=2; ctx.stroke();

    cv._s = s;
  }}

  function hexA(hex,a){{
    hex=hex.replace('#',''); if(hex.length===3) hex=hex.split('').map(c=>c+c).join('');
    const r=parseInt(hex.slice(0,2),16),g=parseInt(hex.slice(2,4),16),b=parseInt(hex.slice(4,6),16);
    return `rgba(${{r}},${{g}},${{b}},${{a}})`;
  }}

  cv.addEventListener('mousemove', e=>{{
    const s=cv._s; if(!s) return;
    const rect=cv.getBoundingClientRect();
    const mx=e.clientX-rect.left;
    let i=Math.round(((mx-plot.l)/plot.w)*(eq.length-1));
    i=Math.max(0,Math.min(eq.length-1,i));
    const d=eq[i];
    tip.style.opacity=1;
    tip.style.left=s.x(i)+'px';
    tip.style.top=s.y(d[1])+'px';
    tip.innerHTML=`<b>${{(d[1]>0?'+':'')+d[1]}}R</b> · ${{d[0]}} · #${{i+1}}`;
  }});
  cv.addEventListener('mouseleave', ()=>tip.style.opacity=0);

  const ro=new ResizeObserver(draw); ro.observe(cv);
  draw();
  matchMedia('(prefers-color-scheme:dark)').addEventListener('change', draw);
  new MutationObserver(draw).observe(root,{{attributes:true,attributeFilter:['data-theme']}});
}})();
</script>
"""

out = os.path.join(HERE, "second_entry_report.html")
with open(out, "w") as f:
    f.write(html)
print("wrote", out, len(html), "bytes")
