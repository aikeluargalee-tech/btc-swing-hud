"use strict";
const $=id=>document.getElementById(id), M="missing";
const n0=v=>typeof v==="number"?Math.round(v).toLocaleString("en-US"):M;
const pct=(v,d=4)=>typeof v==="number"?`${v>=0?"+":""}${v.toFixed(d)}%`:M;
const usdM=v=>typeof v==="number"?`$${(v/1e6).toFixed(2)}M`:M;
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const myt=(ms,o)=>new Date(ms).toLocaleString("en-GB",{timeZone:"Asia/Kuala_Lumpur",...o});
let X={},C=null,D=null,live={price:null,src:null,at:0,h1:null,last1h:null,last1hAt:null},view="48h",bview="has";

async function j(u){const r=await fetch(u,{cache:"no-store"});if(!r.ok)throw new Error(r.status);return r.json();}
async function loadStatic(){
  const t=Date.now();
  [C,D]=await Promise.all([j("config/levels.json?t="+t),j("data/hud.json?t="+t).catch(()=>({missing:["data/hud.json not found"]}))]);
}
async function livePrice(){
  try{const r=await j("https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT");live.price=+r.price;live.src="Binance";}
  catch(e){try{const r=await j("https://api.exchange.coinbase.com/products/BTC-USD/ticker");live.price=+r.price;live.src="Coinbase";}catch(e2){live.src=null;}}
  if(live.src)live.at=Date.now(); renderTop();
}
async function liveKlines(){
  try{const k=await j("https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=49");
    live.h1=k.slice(0,-1).map(x=>[myt(x[0],{day:"2-digit",hour:"2-digit",hour12:false})+":00",+x[4]]);
    live.last1h=+k[k.length-2][4];live.last1hAt=myt(k[k.length-2][6]+1,{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit",hour12:false});
    renderTop();renderChart();}catch(e){}
}

const XS={
  bFund:["https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",r=>({fund:+r.lastFundingRate*100,mark:+r.markPrice})],
  bLS:["https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=1",r=>({ls:+r[0].longShortRatio})],
  bOI:["https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",r=>({oi:+r.openInterest})],
  bPerpK:["https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1h&limit=25",r=>{const c=r.slice(0,-1).map(x=>2*+x[9]-+x[5]);return{p4:c.slice(-4).reduce((s,v)=>s+v,0),p24:c.slice(-24).reduce((s,v)=>s+v,0)};}],
  bybit:["https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT",r=>{const x=r.result.list[0];return{fund:+x.fundingRate*100,oi:+x.openInterest};}],
  okxFund:["https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP",r=>({fund:+r.data[0].fundingRate*100})],
  okxOI:["https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP",r=>({oi:+r.data[0].oiCcy})],
};
async function liveDeriv(){
  await Promise.all(Object.entries(XS).map(async([k,[u,p]])=>{try{const v=p(await j(u));if(Object.values(v).some(n=>!isFinite(n)))throw 0;X[k]=v;}catch(e){delete X[k];}}));
  if(D)renderStatic();
}
const snapT=()=>{const m=String(D?.asOf||"").match(/(\d\d:\d\d)/);return m?m[1]:"?";};
// value with provenance: live value if present, else snapshot value
function pv(lv,sv,fmt){if(typeof lv==="number")return fmt(lv)+" · live";if(typeof sv==="number")return fmt(sv)+` · snapshot ${snapT()} MYT`;return "n/a (live fetch failed, not in snapshot)";}
const price=()=>live.price??D?.price;
const last1h=()=>live.last1h??D?.last1h;
function hit(t){const v={spot:price(),"1h":last1h(),"1d":D?.lastD}[t.basis];if(typeof v!=="number")return null;
  return t.op===">"?v>t.v:t.op==="<"?v<t.v:v>=t.v&&v<=t.v2;}
const row=(t,d,pill,tone)=>`<div class="row"><div class="l"><div class="t">${t}</div>${d?`<div class="d">${d}</div>`:""}</div>${pill!=null?`<span class="pill ${tone||""}">${pill}</span>`:""}</div>`;
const kv=items=>items.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");

function renderTop(){
  if(!C)return;const P=price(),L=C.levels;
  const above=L.filter(l=>l.p>P).sort((a,b)=>a.p-b.p)[0],below=L.filter(l=>l.p<P).sort((a,b)=>b.p-a.p)[0];
  const ch=D?.chg24;const v=C.verdict;
  $("verdict").className="card verdict "+(v.tone||"");
  $("verdict").innerHTML=`<div class="lead">${esc(v.lead)}</div><div class="price">${n0(P)}</div>
   <div class="${ch>=0?"up":"dn"}">${pct(ch,2)} 24h <span class="mut">H ${n0(D?.high24)} · L ${n0(D?.low24)}</span></div>
   ${row("▲ "+(above?esc(above.label):M),above?`+${n0(above.p-P)} away`:"")}${row("▼ "+(below?esc(below.label):M),below?`-${n0(P-below.p)} away`:"")}
   <div class="mut">Verdict set ${esc(v.asOf)}</div>`;
  $("triggers").innerHTML=C.triggers.map(t=>{const h=hit(t);return row(esc(t.title),esc(t.detail),h==null?M:h?"HIT":"Not hit",h?"success":"");}).join("");
  $("trigNote").textContent=`Last 1H close ${n0(last1h())} (${live.last1hAt||D?.last1hAt||M}). Daily ${n0(D?.lastD)}. ${C.plan}`;
  const age=live.at?Math.round((Date.now()-live.at)/1000):null;
  $("dot").className="dot"+(age!=null&&age<20?" live":"");
  $("feed").textContent=live.src?`live ${live.src} · ${age}s`:"live feed down, using snapshot";
}
function renderChart(){
  const s=(view==="48h"?(live.h1||D?.h1):D?.d1)||[];if(s.length<2){$("chart").innerHTML=`<p class="mut">${M}</p>`;return;}
  const W=380,H=300,Lp=8,R=92,T=12,B=26,vals=s.map(p=>p[1]),lo=Math.min(...vals)-150,hi=Math.max(...vals)+150;
  const x=i=>Lp+i/(s.length-1)*(W-Lp-R),y=p=>T+(hi-p)/(hi-lo)*(H-T-B);
  let out=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="BTC closes with key levels">`;
  const z=C.bidZone;if(z){const zt=Math.max(T,y(z.hi)),zb=Math.min(H-B,y(z.lo));if(zb>zt)out+=`<rect x="${Lp}" y="${zt}" width="${W-Lp-R}" height="${zb-zt}" fill="var(--zone)"/>`;}
  let last=-100;C.levels.filter(l=>l.p>lo&&l.p<hi).sort((a,b)=>b.p-a.p).forEach(l=>{const yy=y(l.p),ly=Math.max(yy+4,last+16);last=ly;
    out+=`<line x1="${Lp}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="${l.side==="r"?"var(--dn)":"var(--up)"}" stroke-dasharray="4 4" opacity=".8"/><text x="${W-R+6}" y="${ly}" fill="var(--mut)" font-size="12">${esc(l.label)}</text>`;});
  out+=`<path d="${s.map((p,i)=>`${i?"L":"M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ")}" fill="none" stroke="var(--acc)" stroke-width="2.5"/>`;
  const P=price();if(view==="48h"&&P>lo&&P<hi)out+=`<circle cx="${x(s.length-1)}" cy="${y(P)}" r="4" fill="var(--warn)"/>`;
  [0,Math.round((s.length-1)/3),Math.round((s.length-1)*2/3),s.length-1].forEach((i,k)=>out+=`<text x="${x(i)}" y="${H-6}" text-anchor="${k===0?"start":k===3?"end":"middle"}" fill="var(--mut)" font-size="12">${esc(s[i][0])}</text>`);
  $("chart").innerHTML=out+"</svg>";
}
function renderStatic(){
  const p=D.pos||{},cz=D.cz||{},f=D.flow||{},mac=D.macro||{};
  const f4=v=>pct(v,4),btc=v=>`${n0(v)} BTC`,r2=v=>v.toFixed(2);
  $("pos").innerHTML=kv([["OI (all venues)",cz.oiUsd?`$${(cz.oiUsd/1e9).toFixed(2)}B, ${pct(cz.oiChg24,2)} 24h · snapshot ${snapT()} MYT`:M],["Funding avg",pct(cz.fundAvg)],["Predicted funding",pct(cz.predFundAvg)],
    ["Funding Binance",pv(X.bFund?.fund,p.fundBinance,f4)],["Funding Bybit",pv(X.bybit?.fund,p.fundBybit,f4)],["Funding OKX",pv(X.okxFund?.fund,p.fundOKX,f4)],
    ["OI Binance perp",pv(X.bOI?.oi,p.oiBinance,btc)],["OI Bybit",pv(X.bybit?.oi,p.oiBybit,btc)],["OI OKX",pv(X.okxOI?.oi,p.oiOKX,btc)],
    ["Liqs 24h long",usdM(cz.liqLongUsd24)],["Liqs 24h short",usdM(cz.liqShortUsd24)],
    ["L/S Binance",pv(X.bLS?.ls,p.lsBinance,r2)],["L/S OKX",typeof p.lsOKX==="number"?`${p.lsOKX.toFixed(2)} · snapshot ${snapT()} MYT`:M],
    ["Spot CVD",`${n0(f.spot4h)} 4h / ${n0(f.spot24h)} 24h BTC`],
    ["Perp CVD (Binance)",X.bPerpK?`${n0(X.bPerpK.p4)} 4h / ${n0(X.bPerpK.p24)} 24h BTC · live`:typeof f.perp4h==="number"?`${n0(f.perp4h)} 4h / ${n0(f.perp24h)} 24h BTC · snapshot ${snapT()} MYT`:M]]);
  $("sent").innerHTML=kv([["Fear & Greed",D.fng?`${D.fng.v}, ${D.fng.label}`:M],["Coinbase premium",typeof D.cbPremium==="number"?`${D.cbPremium>=0?"+":"-"}$${Math.abs(D.cbPremium)}`:M]]);
  const today=String(D.asOf||"").slice(0,6);
  const mv=(k,u)=>{const o=mac[k];return o?`${o.v}${u} (${o.chg>=0?"+":""}${o.chg}%)${o.date===today?"":", "+o.date}`:M;};
  $("macro").innerHTML=kv([["VIX",mv("vix","")],["DXY",mv("dxy","")],["US 10Y",mv("us10y","%")],["S&P 500",mv("spx","")],["Nasdaq",mv("ndx","")],["BTC ETF flow",D.etf?`$${D.etf.usdM}M, ${D.etf.date}`:"-$643.2M, 30 Oct (stale)"]]);
  renderBots();
  const LIVEMAP={bFund:"Binance funding",bLS:"Binance long/short",bOI:"Binance perp OI",bPerpK:"Binance perp klines",bybit:"Bybit ticker"};
  const covered=Object.keys(LIVEMAP).filter(k=>X[k]).map(k=>LIVEMAP[k]);
  const errs=(D.missing||[]).filter(m=>!covered.some(c=>m.startsWith(c)));
  const pend=Object.keys(LIVEMAP).filter(k=>!X[k]).map(k=>LIVEMAP[k]);
  $("gaps").textContent=`${C.knownGaps} CVD: ${f.asOf||M}. Price source in Actions: ${D.priceSource||M}. Refresh errors: ${errs.length?errs.join("; "):"none"}.${pend.length?" Not available live right now: "+pend.join(", ")+".":""}`;
  $("foot").textContent=`Snapshot ${D.asOf||M} · refreshed every 15 min by GitHub Actions · not financial advice`;
}
function renderBots(){
  $("bots").innerHTML=C.bots.map(g=>{const b=bview==="has"?g.bots.filter(x=>x.status):g.bots;if(!b.length)return"";
    return `<div class="mut" style="margin-top:8px">${esc(g.section)}</div>`+b.map(x=>row(`${esc(x.code)} ${esc(x.name)}`,esc(x.detail||""),esc(x.status||"Not run"),x.tone)).join("");}).join("");
}
function tick(){
  const now=Date.now();
  $("events").innerHTML=C.events.map(e=>{const ms=new Date(e.t)-now;let m="passed";if(ms>0){const h=Math.floor(ms/36e5),mi=Math.floor(ms%36e5/6e4);m=h>=24?`${Math.floor(h/24)}d ${h%24}h`:`${h}h ${mi}m`;}
    return row(esc(e.title),esc(e.detail),m,ms>0&&ms<6*36e5?"warning":"");}).join("");
  const d=new Date(now+8*36e5),hr=d.getUTCHours()+d.getUTCMinutes()/60;
  $("clock").textContent=myt(now,{hour:"2-digit",minute:"2-digit",hour12:false});
  $("sessions").innerHTML=C.sessions.map(s=>{const on=(hr>=s.start&&hr<s.end)||(hr+24>=s.start&&hr+24<s.end);return row(esc(s.name),s.hours,on?"Active":"Closed",on?"success":"");}).join("");
  renderTop();
}
function seg(id,cb){$(id).addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;[...$(id).children].forEach(x=>x.classList.toggle("on",x===b));cb(b.dataset.v);});}
(async()=>{
  await loadStatic();renderStatic();renderChart();tick();
  seg("seg",v=>{view=v;renderChart();});seg("bseg",v=>{bview=v;renderBots();});
  livePrice();liveKlines();liveDeriv();setInterval(liveDeriv,60000);setInterval(livePrice,5000);setInterval(liveKlines,60000);setInterval(tick,1000);
  setInterval(async()=>{try{await loadStatic();renderStatic();renderChart();}catch(e){}},5*60000);
})();
