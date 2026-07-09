#!/usr/bin/env python3
"""Render a FrontierMultiResultData JSON into a self-contained HTML report.

Usage: python3 render_report.py <result.json> [-o out.html]
No dependencies, no server - the data is embedded and the page renders itself.
"""
import json, sys, os, html

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Go Wild - __TITLE__</title>
<style>
:root{--bg:#08080b;--card:#101016;--card2:#16161f;--line:#26263a;--ink:#e8e8f2;--dim:#8a8aa3;
--violet:#8b5cf6;--green:#34d399;--amber:#fbbf24;--red:#f87171;--chip:#1d1533;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;padding:28px 20px 80px}
.wrap{max-width:1240px;margin:0 auto}
h1{font-size:19px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--dim);font-size:12.5px;margin-bottom:18px}
.hero{border:1px solid var(--violet);background:linear-gradient(180deg,#141024,#0e0c18);border-radius:12px;padding:14px 18px;margin-bottom:16px}
.hero .k{font-size:11px;letter-spacing:.12em;color:var(--violet);text-transform:uppercase;font-weight:700}
.hero .v{font-size:15px;margin-top:3px}
.hero b{color:#fff}
.banner{border:1px solid rgba(251,191,36,.4);background:rgba(251,191,36,.08);color:var(--amber);border-radius:10px;padding:10px 14px;font-size:12.5px;margin-bottom:16px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.qchip{font-size:11.5px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:4px 11px;background:var(--card)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:10px;margin-bottom:26px}
.dest{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 13px;cursor:pointer;transition:border-color .15s}
.dest:hover{border-color:var(--violet)}
.dest .code{font-weight:700;font-family:ui-monospace,Menlo,monospace}
.dest .city{color:var(--dim);font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dest .meta{font-size:11px;color:var(--dim);margin-top:4px}
.fee{float:right;background:var(--chip);border:1px solid var(--violet);color:#c4b5fd;border-radius:8px;padding:3px 9px;font-weight:700;font-size:13px}
.fee.none{border-color:var(--line);color:var(--dim);background:transparent;font-weight:500;font-size:11px}
.fee.amberc{border-color:rgba(251,191,36,.5);color:var(--amber);background:rgba(251,191,36,.06)}
h2{font-size:14px;margin:28px 0 10px;color:#c4b5fd}
.days{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:9px}
.day{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:12px}
.day .dh{display:flex;justify-content:space-between;font-weight:600;margin-bottom:6px}
.ok{color:var(--green)} .no{color:var(--dim)} .uf{color:var(--amber)}
.route{border-top:1px dashed var(--line);padding:6px 0 2px;margin-top:6px}
.route .rf{font-weight:700;color:#c4b5fd}
.legs{color:var(--dim);font-size:11.5px;margin-top:2px}
.bo{color:var(--red);font-size:10.5px;font-weight:700;margin-left:6px}
.note{color:var(--dim);font-size:11px;margin-top:4px;font-style:italic}
.section{margin-bottom:8px}
details{margin-bottom:10px}
summary{cursor:pointer;padding:8px 4px;font-weight:600;list-style:none;display:flex;align-items:center;gap:10px}
summary::before{content:"▸";color:var(--violet);transition:transform .15s}
details[open] summary::before{transform:rotate(90deg)}
summary .scity{color:var(--dim);font-weight:400;font-size:12px}
.lt{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-top:30px;font-size:12.5px}
.lt h3{margin:0 0 8px;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
.lt table{border-collapse:collapse;width:100%}
.lt td,.lt th{text-align:left;padding:4px 12px 4px 0;border-bottom:1px solid var(--line);color:var(--dim);font-size:12px}
.lt th{color:var(--ink)}
.foot{margin-top:26px;color:var(--dim);font-size:11px;text-align:center}
</style>
</head>
<body><div class="wrap">
<h1>Go Wild flights - __TITLE__</h1>
<div class="sub" id="sub"></div>
<div id="root"></div>
<div class="foot">frontier-go-wild · self-contained report · generated __GENAT__</div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const $=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e};
const esc=s=>String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const root=document.getElementById('root');
const q=D.query||{};
document.getElementById('sub').textContent=`${q.origin} → ${(q.destinationsInput||[]).map(d=>d.input).join(', ')} · ${q.dateStart} to ${q.dateEnd}`;
// summary numbers
let flights=0,availDests=0;
for(const d of D.destinations||[]){let any=false;for(const day of d.days||[]){flights+=(day.routes||[]).length;if(day.available)any=true;}
 if(any||d.best)availDests++;}
const hero=$('div','hero');
hero.append($('div','k','Go Wild flights'));
const ob=D.overallBest;
hero.append($('div','v',`<b>${flights}</b> constraint-passing routes · <b>${availDests}</b> of ${(D.destinations||[]).length} destinations with seats`+(ob?` · cheapest: <b>$${ob.goWildFee} ${esc(q.origin)} → ${esc(ob.destination)}</b> ${esc(ob.weekday)} ${esc(ob.date)}`:'')));
root.append(hero);
// partial banner
const unse=(D.destinations||[]).filter(d=>d.unsearched).length;
const unfe=(D.destinations||[]).filter(d=>!d.unsearched&&(d.days||[]).some(x=>x.unfetched)).length;
if(unse||unfe)root.append($('div','banner',`Partial coverage: ${unfe?unfe+' destination(s) have unfetched dates':''}${unfe&&unse?' and ':''}${unse?unse+' destination(s) were never started (cap expired)':''}. Missing means not searched, not searched-and-empty.`));
// query chips
const chips=$('div','chips');
for(const t of [`≤${q.maxStops} stop`,`layover ${q.layoverMin}-${q.layoverMax}m`,`<${q.maxTripHours}h total`, q.cap?`cap ${JSON.stringify(q.cap).replace(/[{}"]/g,'')}`:'no cap',(D.blackoutInRange||[]).length?`blackout: ${D.blackoutInRange.join(', ')}`:'no blackout dates in range'])
 chips.append($('span','qchip',esc(t)));
root.append(chips);
// scoreboard
const grid=$('div','grid');
for(const d of D.destinations||[]){
 const c=$('div','dest');
 const avDays=(d.days||[]).filter(x=>x.available).length;
 let chip;
 if(d.best&&d.best.goWildFee!=null)chip=`<span class="fee">$${d.best.goWildFee}</span>`;
 else if(d.best)chip=`<span class="fee amberc">seats</span>`;
 else if(d.unsearched)chip=`<span class="fee none">skipped (cap)</span>`;
 else if((d.days||[]).some(x=>x.unfetched))chip=`<span class="fee none">unfetched</span>`;
 else chip=`<span class="fee none">no seats</span>`;
 c.innerHTML=`${chip}<div class="code">${esc(d.code)}</div><div class="city">${esc(d.city)}</div><div class="meta">${avDays} of ${(d.days||[]).length} days</div>`;
 c.onclick=()=>{const el=document.getElementById('sec-'+d.code);if(el){el.open=true;el.scrollIntoView({behavior:'smooth'});}};
 grid.append(c);
}
root.append($('h2',null,'Destinations (cheapest first)'));root.append(grid);
// per-destination day grids
root.append($('h2',null,'Day-by-day'));
for(const d of D.destinations||[]){
 if(d.unsearched)continue;
 const det=$('details','section');det.id='sec-'+d.code;
 const best=d.best&&d.best.goWildFee!=null?` · best $${d.best.goWildFee} ${d.best.weekday}`:'';
 det.append($('summary',null,`${esc(d.code)} <span class="scity">${esc(d.city)}${best}</span>`));
 if(d.note)det.append($('div','note',esc(d.note)));
 const days=$('div','days');
 for(const day of d.days||[]){
  const card=$('div','day');
  const st=day.unfetched?'<span class="uf">unfetched</span>':day.available?'<span class="ok">available</span>':'<span class="no">no seats</span>';
  card.append($('div','dh',`<span>${esc(day.weekday)} ${esc(day.date.slice(5))}${day.blackout?'<span class="bo">BLACKOUT</span>':''}</span>${st}`));
  for(const r of day.routes||[]){
   const legs=(r.legs||[]).map(l=>`${esc(l.from)} ${esc(l.dep)} → ${esc(l.to)} ${esc(l.arr)}${l.flight?' · '+esc(l.flight):''}`).join('<br>');
   const via=r.stops?` · ${r.stops} stop ${(r.transferCities||[]).join(',')}`:' · nonstop';
   const st=r.selfTransfer?' · <span style="color:var(--amber);font-weight:700">2 bookings (self-transfer)</span>':'';
   card.append($('div','route',`<span class="rf">$${r.goWildFee}</span>${via}${st}${r.totalMinutes?` · ${Math.floor(r.totalMinutes/60)}h${String(r.totalMinutes%60).padStart(2,'0')}`:''}<div class="legs">${legs}</div>${r.note?`<div class="note">${esc(r.note)}</div>`:''}`));
  }
  if(!((day.routes||[]).length)&&day.pillFee)card.append($('div','note',`pill fee $${day.pillFee} observed, detail not captured`));
  else if(day.note)card.append($('div','note',esc(day.note)));
  days.append(card);
 }
 det.append(days);root.append(det);
}
// limit test panel (optional field)
if(D.limitTest){
 const lt=$('div','lt');lt.append($('h3',null,'Limit test'));
 lt.append($('div',null,`maxStableWorkers: <b>${D.limitTest.maxStableWorkers}</b> · bottleneck: <b>${esc(D.limitTest.bottleneck)}</b>`));
 const t=$('table');t.innerHTML='<tr><th>workers</th><th>searches</th><th>fail %</th><th>events</th></tr>'+
  (D.limitTest.stages||[]).map(s=>`<tr><td>${s.workers}</td><td>${s.searches}</td><td>${s.failPct}</td><td>${(s.events||[]).map(esc).join('; ')}</td></tr>`).join('');
 lt.append(t);root.append(lt);
}
</script>
</body>
</html>"""

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    src = args[0]
    out = None
    if "-o" in args:
        out = args[args.index("-o") + 1]
    data = json.load(open(src))
    q = data.get("query", {})
    title = f"{q.get('origin','?')} {q.get('dateStart','')}–{q.get('dateEnd','')}"
    import datetime
    page = (TEMPLATE
            .replace("__TITLE__", html.escape(title))
            .replace("__GENAT__", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__DATA__", json.dumps(data).replace("</", "<\\/")))
    if not out:
        out = os.path.splitext(src)[0] + ".html"
    with open(out, "w") as f:
        f.write(page)
    print(out)

if __name__ == "__main__":
    main()
