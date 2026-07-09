"""Render a paper-trading statement from paper_trade_results.json."""
import json
import os

HERE = os.path.dirname(__file__)
d = json.load(open(os.path.join(HERE, "paper_trade_results.json")))
cfg, fr, ws = d["config"], d["frictionless"], d["with_spread"]
sp = d.get("with_costs", d["with_spread"])   # headline = most realistic scenario
_slip = cfg.get("slippage_pips", 0.0)

payload = json.dumps({
    "spread": [[p["date"], p["balance"]] for p in sp["curve"]],
    "frictionless": [[p["date"], p["balance"]] for p in fr["curve"]],
    "start": cfg["start_balance"],
}, separators=(",", ":"))

exp_drop = round(100 * (1 - sp["expectancy_R"] / fr["expectancy_R"]), 0)

html = f"""<title>Paper-Trading Statement — Second Entry (H2/L2) M3</title>
<style>
  :root {{
    --bg:#f4f5f2; --surface:#fbfbf9; --surface-2:#eef0ea; --ink:#181d1c;
    --ink-2:#4b5350; --ink-3:#828c88; --line:#dcded7; --gold:#b8892e;
    --pos:#1f8f6f; --neg:#c0523a; --ref:#4a9b8e;
    --shadow:0 1px 2px rgba(20,28,26,.05),0 8px 26px rgba(20,28,26,.06);
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
  }}
  @media (prefers-color-scheme:dark) {{
    :root {{ --bg:#0e1413; --surface:#141b1a; --surface-2:#1b2322; --ink:#e9ede9;
      --ink-2:#a7b0ac; --ink-3:#6d7773; --line:#26302e; --gold:#d3ac5a;
      --pos:#43b892; --neg:#dd6b50; --ref:#4bb6a6;
      --shadow:0 1px 2px rgba(0,0,0,.35),0 12px 34px rgba(0,0,0,.4); }}
  }}
  :root[data-theme="light"] {{ --bg:#f4f5f2; --surface:#fbfbf9; --surface-2:#eef0ea;
    --ink:#181d1c; --ink-2:#4b5350; --ink-3:#828c88; --line:#dcded7; --gold:#b8892e;
    --pos:#1f8f6f; --neg:#c0523a; --ref:#4a9b8e;
    --shadow:0 1px 2px rgba(20,28,26,.05),0 8px 26px rgba(20,28,26,.06); }}
  :root[data-theme="dark"] {{ --bg:#0e1413; --surface:#141b1a; --surface-2:#1b2322;
    --ink:#e9ede9; --ink-2:#a7b0ac; --ink-3:#6d7773; --line:#26302e; --gold:#d3ac5a;
    --pos:#43b892; --neg:#dd6b50; --ref:#4bb6a6;
    --shadow:0 1px 2px rgba(0,0,0,.35),0 12px 34px rgba(0,0,0,.4); }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans); line-height:1.55; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:clamp(20px,4vw,52px) clamp(16px,4vw,40px) 80px; }}
  .mono {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}
  header.mast {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:28px; }}
  .eyebrow {{ font-family:var(--mono); font-size:12px; letter-spacing:.16em; text-transform:uppercase; color:var(--gold); margin:0 0 12px; }}
  h1 {{ font-family:var(--serif); font-weight:600; font-size:clamp(28px,4.6vw,42px); line-height:1.06; margin:0 0 12px; text-wrap:balance; }}
  .sub {{ color:var(--ink-2); font-size:16px; max-width:64ch; margin:0; }}
  .facts {{ display:flex; flex-wrap:wrap; gap:8px 10px; margin-top:18px; }}
  .chip {{ font-family:var(--mono); font-size:12.5px; color:var(--ink-2); background:var(--surface-2); border:1px solid var(--line); border-radius:999px; padding:5px 12px; }}
  .chip b {{ color:var(--ink); font-weight:600; }}
  .verdict {{ background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--gold); border-radius:12px; padding:18px 20px; margin:0 0 30px; box-shadow:var(--shadow); }}
  .verdict .tag {{ font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--gold); }}
  .verdict p {{ margin:8px 0 0; font-size:15.5px; }}
  .verdict b.pos {{ color:var(--pos); }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:13px; margin-bottom:34px; }}
  .kpi {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:15px 17px; box-shadow:var(--shadow); }}
  .kpi .k {{ font-size:11.5px; letter-spacing:.04em; text-transform:uppercase; color:var(--ink-3); margin:0 0 7px; font-family:var(--mono); }}
  .kpi .v {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:27px; font-weight:600; letter-spacing:-.02em; line-height:1; }}
  .kpi .d {{ font-size:12px; color:var(--ink-2); margin:7px 0 0; }}
  section {{ margin-bottom:38px; }}
  h2 {{ font-family:var(--serif); font-weight:600; font-size:21px; margin:0 0 4px; }}
  .lede {{ color:var(--ink-2); font-size:14.5px; margin:0 0 16px; max-width:66ch; }}
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:20px; box-shadow:var(--shadow); }}
  .legend {{ display:flex; gap:18px; margin:0 0 12px; font-family:var(--mono); font-size:12.5px; color:var(--ink-2); }}
  .legend i {{ display:inline-block; width:14px; height:3px; border-radius:2px; margin-right:6px; vertical-align:middle; }}
  .chart-wrap {{ position:relative; }}
  canvas {{ display:block; width:100%; height:auto; }}
  .tip {{ position:absolute; pointer-events:none; opacity:0; transition:opacity .1s; background:var(--ink); color:var(--bg); font-family:var(--mono); font-size:12px; padding:6px 9px; border-radius:7px; white-space:nowrap; transform:translate(-50%,-130%); z-index:5; }}
  .tip b {{ color:var(--gold); }}
  .cap {{ font-size:12.5px; color:var(--ink-3); margin:12px 0 0; font-family:var(--mono); }}
  table {{ border-collapse:collapse; width:100%; background:var(--surface); font-size:14px; border:1px solid var(--line); border-radius:12px; overflow:hidden; box-shadow:var(--shadow); }}
  th, td {{ padding:12px 16px; border-bottom:1px solid var(--line); text-align:right; }}
  th:first-child, td:first-child {{ text-align:left; }}
  thead th {{ font-family:var(--mono); font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-3); font-weight:500; }}
  tbody tr:last-child td {{ border-bottom:none; }}
  td.mono, th.mono {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}
  .warn {{ background:var(--surface-2); border:1px solid var(--line); border-radius:12px; padding:16px 20px; margin-top:22px; }}
  .warn h3 {{ margin:0 0 6px; font-family:var(--serif); font-size:16px; }}
  .warn p {{ margin:0 0 8px; font-size:13.5px; color:var(--ink-2); }}
  .warn p:last-child {{ margin:0; }}
  footer {{ margin-top:46px; padding-top:18px; border-top:1px solid var(--line); font-family:var(--mono); font-size:12px; color:var(--ink-3); display:flex; flex-wrap:wrap; gap:6px 16px; justify-content:space-between; }}
</style>

<div class="wrap">
  <header class="mast">
    <p class="eyebrow">Paper-Trading Statement · Simulated Demo Account</p>
    <h1>Second Entry (H2/L2) — M3 paper run</h1>
    <p class="sub">The live bot's logic replayed over the last 12 months on a
    simulated ${cfg['start_balance']:,.0f} account: 1% risk per trade, break-even at
    1R, order expiry, fills &amp; stops walked on 1-minute data, and a modelled
    spread. This is a historical simulation, not a live forward test.</p>
    <div class="facts">
      <span class="chip"><b>Timeframe</b> {cfg['timeframe']}</span>
      <span class="chip"><b>Pairs</b> {len(cfg['symbols'])} majors</span>
      <span class="chip"><b>Window</b> {cfg['paper_start']} → 2025-12</span>
      <span class="chip"><b>Risk</b> {cfg['risk_pct']:.0f}% / trade</span>
      <span class="chip"><b>Costs</b> {sp['spread_pips']:.0f}p spread + {_slip:.1f}p slip</span>
      <span class="chip"><b>Peak open</b> {sp['peak_concurrent_positions']} positions</span>
    </div>
  </header>

  <div class="verdict">
    <span class="tag">Read this first</span>
    <p>With realistic costs (a {sp['spread_pips']:.0f}-pip spread <b>and</b>
    {_slip:.1f}-pip slippage per fill) the simulated account grew
    <b class="pos">{sp['return_pct']:+.0f}%</b> ({fr['return_pct']:+.0f}% with no
    costs) at a {abs(sp['max_drawdown_pct']):.1f}% max drawdown — the edge survives,
    but thinner. <b>Treat it as an upper bound, not a forecast:</b> costs cut
    per-trade expectancy by ~{exp_drop:.0f}%
    ({fr['expectancy_R']:+.2f}R → {sp['expectancy_R']:+.2f}R), and the model still
    assumes a flat spread with no swaps, commission or variable news-time spread.
    On M3's tight ~11-pip stops these bite hard. A live demo is the real test.</p>
  </div>

  <div class="kpis">
    <div class="kpi"><p class="k">End balance</p><div class="v pos">${sp['end_balance']:,.0f}</div><p class="d">from ${cfg['start_balance']:,.0f} · {sp['return_pct']:+.0f}%</p></div>
    <div class="kpi"><p class="k">Expectancy</p><div class="v pos">{sp['expectancy_R']:+.2f}R</div><p class="d">per trade, after costs</p></div>
    <div class="kpi"><p class="k">Win rate</p><div class="v">{sp['win_rate']:.1f}%</div><p class="d">{sp['wins']:,}W · {sp['losses']:,}L (BE lowers this)</p></div>
    <div class="kpi"><p class="k">Profit factor</p><div class="v">{sp['profit_factor']:.2f}</div><p class="d">gross win ÷ gross loss</p></div>
    <div class="kpi"><p class="k">Max drawdown</p><div class="v">{sp['max_drawdown_pct']:.1f}%</div><p class="d">on the equity curve</p></div>
    <div class="kpi"><p class="k">Trades</p><div class="v">{sp['trades']:,}</div><p class="d">~{sp['trades']/12:.0f}/month, 7 pairs</p></div>
  </div>

  <section>
    <h2>Account equity</h2>
    <p class="lede">Balance after each closed trade (constant 1%-of-initial risk, so
    the curve is linear, not compounded). The faint line is the same run with zero
    costs — the gap between them is what spread + slippage cost you.</p>
    <div class="card">
      <div class="legend">
        <span><i style="background:var(--gold)"></i>with costs (spread + slippage)</span>
        <span><i style="background:var(--ref)"></i>no costs (upper bound)</span>
      </div>
      <div class="chart-wrap">
        <canvas id="eq" width="1000" height="360" aria-label="Paper-trading equity curve"></canvas>
        <div class="tip" id="tip"></div>
      </div>
      <p class="cap">Simulated ${cfg['start_balance']:,.0f} account · {cfg['paper_start']}–2025-12 · peak {sp['peak_concurrent_positions']} concurrent positions.</p>
    </div>
  </section>

  <section>
    <h2>What the costs take</h2>
    <p class="lede">Same trades, same signals — each row just adds a friction layer.
    Costs are the single biggest gap between backtest and reality, and they compound.</p>
    <table>
      <thead><tr><th>Scenario</th><th class="mono">Win%</th><th class="mono">Expectancy</th><th class="mono">Profit factor</th><th class="mono">Return</th><th class="mono">End balance</th></tr></thead>
      <tbody>
        <tr><td>No costs (upper bound)</td><td class="mono">{fr['win_rate']:.1f}%</td><td class="mono">{fr['expectancy_R']:+.2f}R</td><td class="mono">{fr['profit_factor']:.2f}</td><td class="mono">{fr['return_pct']:+.0f}%</td><td class="mono">${fr['end_balance']:,.0f}</td></tr>
        <tr><td>+ {ws['spread_pips']:.0f}-pip spread</td><td class="mono">{ws['win_rate']:.1f}%</td><td class="mono">{ws['expectancy_R']:+.2f}R</td><td class="mono">{ws['profit_factor']:.2f}</td><td class="mono">{ws['return_pct']:+.0f}%</td><td class="mono">${ws['end_balance']:,.0f}</td></tr>
        <tr><td>+ {_slip:.1f}-pip slippage</td><td class="mono">{sp['win_rate']:.1f}%</td><td class="mono">{sp['expectancy_R']:+.2f}R</td><td class="mono">{sp['profit_factor']:.2f}</td><td class="mono">{sp['return_pct']:+.0f}%</td><td class="mono">${sp['end_balance']:,.0f}</td></tr>
      </tbody>
    </table>
    <p class="cap">Spread + slippage erased ~{exp_drop:.0f}% of the per-trade edge ({fr['expectancy_R']:+.2f}R → {sp['expectancy_R']:+.2f}R). Real variable spread on news erases more.</p>
  </section>

  <div class="warn">
    <h3>Why this isn't a green light</h3>
    <p><b>Flat spread + fixed slippage.</b> This models {sp['spread_pips']:.0f} pip of
    spread and {_slip:.1f} pip of slippage per fill — but real spread <em>widens</em>
    around news and rollover, exactly when this breakout strategy fires, and stop
    fills can slip much more in fast moves.</p>
    <p><b>No swaps or commission.</b> Overnight financing and per-lot commission
    aren't modelled; both drag on a high-frequency system.</p>
    <p><b>One vendor feed, one spread.</b> Your broker's bid/ask and fills will
    differ — sometimes materially — from this single historical series.</p>
    <p><b>The return magnitude is still generous, not a promise.</b> Even after costs,
    +{sp['return_pct']:.0f}% assumes flawless execution. Run
    <code>mt5_live_bot.py</code> (or the EA in the Strategy Tester) on demo for weeks
    before trusting any of it.</p>
  </div>

  <footer>
    <span>Second Entry (H2/L2) · paper-trading simulation</span>
    <span>{cfg['timeframe']} · {len(cfg['symbols'])} majors · {cfg['paper_start']}–2025-12 · spread + slippage modelled</span>
  </footer>
</div>

<script>
const DATA = {payload};
(function(){{
  const root=document.documentElement, cv=document.getElementById('eq'),
        tip=document.getElementById('tip'), ctx=cv.getContext('2d');
  const A=DATA.spread, B=DATA.frictionless, DPR=Math.min(devicePixelRatio||1,2);
  let W,H,plot;
  const css=v=>getComputedStyle(root).getPropertyValue(v).trim();
  function layout(){{
    const r=cv.getBoundingClientRect(); W=r.width; H=r.height;
    cv.width=W*DPR; cv.height=H*DPR; ctx.setTransform(DPR,0,0,DPR,0,0);
    plot={{l:62,r:14,t:14,b:28,w:W-76,h:H-42}};
  }}
  function sc(){{
    const ys=A.concat(B).map(d=>d[1]); const mn=Math.min(...ys),mx=Math.max(...ys);
    const pad=(mx-mn)*0.06;
    return {{x:i=>plot.l+(i/(A.length-1))*plot.w,
             y:v=>plot.t+plot.h-((v-mn)/((mx+pad)-mn))*plot.h, mn,mx:mx+pad}};
  }}
  function line(s,arr,color,width,dash){{
    ctx.beginPath(); ctx.setLineDash(dash||[]);
    arr.forEach((d,i)=>{{const x=s.x(i),y=s.y(d[1]); i?ctx.lineTo(x,y):ctx.moveTo(x,y);}});
    ctx.strokeStyle=color; ctx.lineWidth=width; ctx.lineJoin='round'; ctx.stroke();
    ctx.setLineDash([]);
  }}
  function fmt(v){{ return '$'+Math.round(v).toLocaleString(); }}
  function draw(){{
    layout(); const s=sc(); ctx.clearRect(0,0,W,H);
    const line0=css('--line'),ink3=css('--ink-3'),gold=css('--gold'),ref=css('--ref');
    ctx.font='11px ui-monospace,Menlo,monospace'; ctx.textBaseline='middle';
    const range=s.mx-s.mn, step=Math.pow(10,Math.floor(Math.log10(range/4)));
    const stp=(range/4/step)>=5?step*5:(range/4/step)>=2?step*2:step;
    ctx.strokeStyle=line0; ctx.fillStyle=ink3; ctx.lineWidth=1;
    for(let v=Math.ceil(s.mn/stp)*stp; v<=s.mx; v+=stp){{
      const y=s.y(v); ctx.globalAlpha=.5; ctx.beginPath();
      ctx.moveTo(plot.l,y); ctx.lineTo(plot.l+plot.w,y); ctx.stroke();
      ctx.globalAlpha=1; ctx.textAlign='right'; ctx.fillText(fmt(v),plot.l-8,y);
    }}
    ctx.textAlign='center'; ctx.textBaseline='top'; let last=null;
    A.forEach((d,i)=>{{const yr=d[0].slice(0,7);
      if(yr!==last && d[0].slice(8)<='03'){{last=yr;
        ctx.fillStyle=ink3; ctx.fillText(d[0].slice(0,7),s.x(i),plot.t+plot.h+7);}}}});
    line(s,B,ref,1.5,[4,4]);
    line(s,A,gold,2);
    cv._s=s;
  }}
  cv.addEventListener('mousemove',e=>{{
    const s=cv._s; if(!s)return; const r=cv.getBoundingClientRect();
    let i=Math.round(((e.clientX-r.left)-plot.l)/plot.w*(A.length-1));
    i=Math.max(0,Math.min(A.length-1,i)); const d=A[i];
    tip.style.opacity=1; tip.style.left=s.x(i)+'px'; tip.style.top=s.y(d[1])+'px';
    tip.innerHTML=`<b>${{fmt(d[1])}}</b> · ${{d[0]}} · #${{i+1}}`;
  }});
  cv.addEventListener('mouseleave',()=>tip.style.opacity=0);
  new ResizeObserver(draw).observe(cv); draw();
  matchMedia('(prefers-color-scheme:dark)').addEventListener('change',draw);
  new MutationObserver(draw).observe(root,{{attributes:true,attributeFilter:['data-theme']}});
}})();
</script>
"""

out = os.path.join(HERE, "second_entry_paper_report.html")
with open(out, "w") as f:
    f.write(html)
print("wrote", out, len(html), "bytes")
