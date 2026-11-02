"use strict";
const $=id=>document.getElementById(id), M="missing";
const n0=v=>typeof v==="number"?Math.round(v).toLocaleString("en-US"):M;
const pct=(v,d=4)=>typeof v==="number"?`${v>=0?"+":""}${v.toFixed(d)}%`:M;
const usdM=v=>typeof v==="number"?`$${(v/1e6).toFixed(2)}M`:M;
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const myt=(ms,o)=>new Date(ms).toLocaleString("en-GB",{timeZone:"Asia/Kuala_Lumpur",...o});
let X={},C=null,D=null,live={price:null,src:null,at:0,h1:null,last1h:null,last1hAt:null},view="48h",bview="has";

let CG=null;
function renderCG(){const el=$("cg");if(!CG){el.innerHTML=kv([["CoinGlass levels","n/a (file not found)"]]);$("cgNote").textContent="";return;}
  const ts=Date.parse(CG.captured_myt.replace(" ","T")+":00+08:00"),ageH=(Date.now()-ts)/36e5,st=ageH>3?` · STALE (${ageH.toFixed(1)}h old)`:"";
  const big=x=>Math.abs(x.price-CG.biggest)<1?" ★ biggest":"";const RP=(typeof live!=="undefined"&&live.price)||D?.price||CG.price,dp=x=>RP?` (${x.price>=RP?"+":""}${((x.price-RP)/RP*100).toFixed(2)}%)`:"";
  el.innerHTML=kv([...CG.above.slice().sort((p,q)=>q.price-p.price).map(x=>[`▲ ${n0(x.price)}${dp(x)}`,`$${x.usd_m.toFixed(2)}M shorts${big(x)}`]),["Price at capture","~"+n0(CG.price)],...CG.below.slice().sort((p,q)=>q.price-p.price).map(x=>[`▼ ${n0(x.price)}${dp(x)}`,`$${x.usd_m.toFixed(2)}M longs${big(x)}`])]);
  $("cgNote").textContent=`CoinGlass ${CG.exchange}, ${CG.range} liquidation map. Captured ${CG.captured_myt} SGT${st}. Scale max $${CG.scale_max_m}M. % = distance from ${live.price?"live":"snapshot"} price ${n0(RP)}.`;}
async function j(u){const r=await fetch(u,{cache:"no-store"});if(!r.ok)throw new Error(r.status);return r.json();}
async function loadStatic(){
  const t=Date.now();
  [C,D]=await Promise.all([j("config/levels.json?t="+t),j("data/hud.json?t="+t).catch(()=>({missing:["data/hud.json not found"]}))]);
  CG=await j("data/coinglass.json?t="+t).catch(()=>null);
}
async function livePrice(){
  try{const r=await j("https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT");live.price=+r.price;live.src="Binance";}
  catch(e){try{const r=await j("https://api.exchange.coinbase.com/products/BTC-USD/ticker");live.price=+r.price;live.src="Coinbase";}catch(e2){live.src=null;}}
  if(live.src)live.at=Date.now(); renderTop(); try{renderCG();}catch(e){}
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

// ---- extra live sources ----
function depthCalc(bids,asks){const mid=(+bids[0][0]+ +asks[0][0])/2,o={mid,reachPct:Math.min(mid-+bids[bids.length-1][0],+asks[asks.length-1][0]-mid)/mid*100};
  for(const b of [1,2]){let bid=0,ask=0;for(const [p,q] of bids)if(+p>=mid*(1-b/100))bid+=p*q;for(const [p,q] of asks)if(+p<=mid*(1+b/100))ask+=p*q;
    o["b"+b]={bid,ask,imb:bid+ask?(bid-ask)/(bid+ask)*100:null,full:o.reachPct>=b};}return o;}
const MON={JAN:0,FEB:1,MAR:2,APR:3,MAY:4,JUN:5,JUL:6,AUG:7,SEP:8,OCT:9,NOV:10,DEC:11};
const expD=s=>Date.UTC(2000+ +s.slice(-2),MON[s.slice(-5,-2)],+s.slice(0,-5),8);
function optCalc(rows){const ex={};let tc=0,tp=0;for(const x of rows){const [,e,k,cp]=x.instrument_name.split("-"),oi=x.open_interest||0;(ex[e]=ex[e]||[]).push([+k,cp,oi,x.mark_iv,x.underlying_price]);cp==="C"?tc+=oi:tp+=oi;}
  const tot=tc+tp,exps=Object.keys(ex).filter(e=>expD(e)>Date.now()).sort((a,b)=>expD(a)-expD(b));
  const big=exps.find(e=>ex[e].reduce((s,o)=>s+o[2],0)>=0.1*tot)||exps[0],L=ex[big],ks=[...new Set(L.map(o=>o[0]))].sort((a,b)=>a-b);
  const pain=K=>L.reduce((s,o)=>s+(o[1]==="C"?o[2]*Math.max(0,K-o[0]):o[2]*Math.max(0,o[0]-K)),0);
  let mp=ks[0];for(const k of ks)if(pain(k)<pain(mp))mp=k;const und=(L.find(o=>o[4])||[])[4]||mp;
  const atm=ks.reduce((a,k)=>Math.abs(k-und)<Math.abs(a-und)?k:a,ks[0]),ivs=L.filter(o=>o[0]===atm&&o[3]).map(o=>o[3]);
  const ec=L.filter(o=>o[1]==="C").reduce((s,o)=>s+o[2],0),ep=L.filter(o=>o[1]==="P").reduce((s,o)=>s+o[2],0);
  return {expiry:big,expiryOI:ec+ep,maxPain:mp,pcrExpiry:ec?ep/ec:null,pcrAll:tc?tp/tc:null,atmStrike:atm,atmIV:ivs.length?ivs.reduce((s,v)=>s+v,0)/ivs.length:null};}
const BK={};
const XE={
  dSpot:["https://data-api.binance.vision/api/v3/depth?symbol=BTCUSDT&limit=5000",r=>{BK.spot=[r.bids,r.asks];return depthCalc(r.bids,r.asks);}],
  dBybit:["https://api.bybit.com/v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=1000",r=>{BK.bybitPerp=[r.result.b,r.result.a];return depthCalc(r.result.b,r.result.a);}],
  oiHist:["https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1h&limit=5",r=>({oi4h:(+r[r.length-1].sumOpenInterest/+r[0].sumOpenInterest-1)*100})],
  k1hLive:["https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=6",r=>{const k=r.slice(0,-1),c=k.map(x=>+x[4]),sc=k.map(x=>2*x[9]-x[5]);return{px1h:(c[4]/c[3]-1)*100,px4h:(c[4]/c[0]-1)*100,spot1h:sc[4],spot4h:sc[1]+sc[2]+sc[3]+sc[4]};}],
  dPerp:["https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=1000",r=>depthCalc(r.bids,r.asks)],
  dOkx:["https://www.okx.com/api/v5/market/books-full?instId=BTC-USDT-SWAP&sz=5000",r=>{const f=L=>L.map(x=>[+x[0],+x[1]*0.01]);const b=f(r.data[0].bids),s=f(r.data[0].asks);BK.okxPerp=[b,s];return depthCalc(b,s);}],
  opt:["https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option",r=>optCalc(r.result)],
  dvol:[()=>`https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=3600&start_timestamp=${Date.now()-6*36e5}&end_timestamp=${Date.now()}`,r=>({dvol:r.result.data[r.result.data.length-1][4]})],
};
async function liveExtra(){
  await Promise.all(Object.entries(XE).map(async([k,[u,p]])=>{try{X[k]=p(await j(typeof u==="function"?u():u));}catch(e){delete X[k];}}));
  if(D)renderStatic();
}
const tag=isLive=>isLive?" · live":` · snapshot ${snapT()} SGT`;
const usdS=v=>typeof v==="number"?(Math.abs(v)>=1e9?`$${(v/1e9).toFixed(2)}B`:`$${(v/1e6).toFixed(1)}M`):M;
function renderExtras(){
  renderCG();
  const le=D.liqEst;
  $("liq").innerHTML=le?kv([...le.above.slice().reverse().map(x=>[`▲ ${n0(x.p)}`,`~${usdS(x.usd)} shorts`]),...le.below.map(x=>[`▼ ${n0(x.p)}`,`~${usdS(x.usd)} longs`])]):kv([["Clusters","n/a"]]);
  $("liqNote").textContent=le?`${le.method}. Snapshot ${snapT()} SGT. Not a heatmap.`:"";
  const dr=(name,live,snap)=>{const d=live||snap;if(!d)return[[name,"n/a"]];const t=tag(!!live);
    return [1,2].filter(b=>b===1||d.reachPct>=1).map(b=>{const x=d["b"+b];return[`${name} ±${b}%`,`bid ${usdS(x.bid)} / ask ${usdS(x.ask)} · imb ${x.imb>=0?"+":""}${(+x.imb).toFixed(1)}%${x.full?"":` (book reaches ±${(+d.reachPct).toFixed(2)}%)`}${t}`];});};
  const sd=D.depth||{},LW=liveAggWalls(),AG=LW?.agg||sd.agg,WL=LW?.walls||sd.walls,at=tag(!!LW);
  const aggRows=AG?[1,2].map(b=>{const g=AG["b"+b];return g?[`Aggregate ±${b}%`,`bid ${usdS(g.bid)} / ask ${usdS(g.ask)} · imb ${g.imb>=0?"+":""}${(+g.imb).toFixed(1)}% [${g.venues.join(", ")}]${at}`]:null;}).filter(Boolean):[];
  const wallRows=WL?Object.entries(WL).map(([t,w])=>[`Walls near ${n0(+t)}`,`bid ${w.bid?n0(w.bid.p)+"-"+n0(w.bid.p+50)+" "+usdS(w.bid.usd):"none"} · ask ${w.ask?n0(w.ask.p)+"-"+n0(w.ask.p+50)+" "+usdS(w.ask.usd):"none"}${at}`]):[];
  $("depth").innerHTML=kv([...aggRows,...wallRows,...dr("Binance spot",X.dSpot,sd.spot),...dr("OKX perp",X.dOkx,sd.okxPerp),...dr("Bybit perp",X.dBybit,sd.bybitPerp),...dr("Binance perp",X.dPerp,sd.perp)]);
  $("depthNote").textContent="Aggregate = Binance spot + OKX perp + Bybit perp (Binance perp excluded: ~±0.15% book). Walls = largest $50 bucket within ±0.4% of the trigger, all three books. Bands beyond a book's reach are dropped; partial reach is noted.";
  const o=X.opt||D.opt,ol=!!X.opt,dv=X.dvol?.dvol??D.opt?.dvol;
  $("opt").innerHTML=o?kv([["Expiry (≥10% OI)",`${o.expiry}, ${n0(o.expiryOI)} BTC OI`],["Max pain",`${n0(o.maxPain)}${tag(ol)}`],["P/C OI (expiry)",`${o.pcrExpiry?.toFixed(2)??M}`],["P/C OI (all)",`${o.pcrAll?.toFixed(2)??M}`],
    ["ATM IV",o.atmIV!=null?`${o.atmIV.toFixed(1)}% @ ${n0(o.atmStrike)}`:M],["DVOL",typeof dv==="number"?`${dv.toFixed(1)}${tag(!!X.dvol)}`:M]]):kv([["Deribit","n/a"]]);
  const T=D.tech,P=price();
  const ma=n=>T?.["ma"+n]?`${n0(T["ma"+n])} · price ${P>=T["ma"+n]?"above":"below"} ${((P/T["ma"+n]-1)*100).toFixed(2)}%`:M;
  $("tech").innerHTML=T?kv([["RSI(14) daily",T.rsiD??M],["RSI(14) 4H",T.rsi4h??M],["MA20 daily",ma(20)],["MA50 daily",ma(50)],["MA200 daily",ma(200)],["ATR(14) daily",T.atrD?`${n0(T.atrD)} (${T.atrPct}%)`:M],["Basis",`${T.basis}, snapshot ${snapT()} SGT`]]):kv([["Technicals","n/a"]]);
  const S=D.stables;
  $("stab").innerHTML=S?kv([["USDT+USDC",`${usdS(S.totalUsd)}, ${pct(S.totalChg7d,2)} 7d (${S.totalChg7dUsd>=0?"+":"-"}${usdS(Math.abs(S.totalChg7dUsd))})`],["USDT",`${usdS(S.USDT?.usd)}, ${pct(S.USDT?.chg7d,2)} 7d`],["USDC",`${usdS(S.USDC?.usd)}, ${pct(S.USDC?.chg7d,2)} 7d`],["Source",`DefiLlama, snapshot ${snapT()} SGT`]]):kv([["Stablecoins","n/a"]]);
}
async function liveDeriv(){
  await Promise.all(Object.entries(XS).map(async([k,[u,p]])=>{try{const v=p(await j(u));if(Object.values(v).some(n=>!isFinite(n)))throw 0;X[k]=v;}catch(e){delete X[k];}}));
  if(D)renderStatic();
}
const snapT=()=>{const m=String(D?.asOf||"").match(/(\d\d:\d\d)/);return m?m[1]:"?";};
// value with provenance: live value if present, else snapshot value
function pv(lv,sv,fmt){if(typeof lv==="number")return fmt(lv)+" · live";if(typeof sv==="number")return fmt(sv)+` · snapshot ${snapT()} SGT`;return "n/a (live fetch failed, not in snapshot)";}
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
  $("pos").innerHTML=kv([["OI (all venues)",cz.oiUsd?`$${(cz.oiUsd/1e9).toFixed(2)}B, ${pct(cz.oiChg24,2)} 24h · snapshot ${snapT()} SGT`:M],["Funding avg",pct(cz.fundAvg)],["Predicted funding",pct(cz.predFundAvg)],
    ["Funding Binance",pv(X.bFund?.fund,p.fundBinance,f4)],["Funding Bybit",pv(X.bybit?.fund,p.fundBybit,f4)],["Funding OKX",pv(X.okxFund?.fund,p.fundOKX,f4)],
    ["OI Binance perp",pv(X.bOI?.oi,p.oiBinance,btc)],["OI Bybit",pv(X.bybit?.oi,p.oiBybit,btc)],["OI OKX",pv(X.okxOI?.oi,p.oiOKX,btc)],
    ["Liqs 24h long",usdM(cz.liqLongUsd24)],["Liqs 24h short",usdM(cz.liqShortUsd24)],
    ["L/S Binance",pv(X.bLS?.ls,p.lsBinance,r2)],["L/S OKX",typeof p.lsOKX==="number"?`${p.lsOKX.toFixed(2)} · snapshot ${snapT()} SGT`:M],
    ["Spot CVD",`${n0(f.spot4h)} 4h / ${n0(f.spot24h)} 24h BTC`],
    ["Perp CVD (Binance)",X.bPerpK?`${n0(X.bPerpK.p4)} 4h / ${n0(X.bPerpK.p24)} 24h BTC · live`:typeof f.perp4h==="number"?`${n0(f.perp4h)} 4h / ${n0(f.perp24h)} 24h BTC · snapshot ${snapT()} SGT`:M]]);
  $("sent").innerHTML=kv([["Fear & Greed",D.fng?`${D.fng.v}, ${D.fng.label}`:M],["Coinbase premium",typeof D.cbPremium==="number"?`${D.cbPremium>=0?"+":"-"}$${Math.abs(D.cbPremium)}`:M]]);
  const today=String(D.asOf||"").slice(0,6);
  const mv=(k,u)=>{const o=mac[k];return o?`${o.v}${u} (${o.chg>=0?"+":""}${o.chg}%)${o.date===today?"":", "+o.date}`:M;};
  $("macro").innerHTML=kv([["VIX",mv("vix","")],["DXY",mv("dxy","")],["US 10Y",mv("us10y","%")],["S&P 500",mv("spx","")],["Nasdaq",mv("ndx","")],["BTC ETF flow",D.etf?`${D.etf.usdM>=0?"+":""}$${D.etf.usdM}M, ${D.etf.date} (${D.etf.source||"metrics"})`:M]]);
  renderExtras();
  renderV3();
  renderBots();
  const LIVEMAP={bFund:"Binance funding",bLS:"Binance long/short",bOI:"Binance perp OI",bPerpK:"Binance perp klines",bybit:"Bybit ticker",dPerp:"Binance perp depth"};
  const covered=Object.keys(LIVEMAP).filter(k=>X[k]).map(k=>LIVEMAP[k]);
  const errs=(D.missing||[]).filter(m=>!covered.some(c=>m.startsWith(c)));
  const pend=Object.keys(LIVEMAP).filter(k=>!X[k]).map(k=>LIVEMAP[k]);
  $("gaps").textContent=`${C.knownGaps} CVD: ${f.asOf||M}. Price source in Actions: ${D.priceSource||M}. No free source: ${(D.noSource||[]).join("; ")||"none"}. Liq clusters are an estimate, not exchange data. Refresh errors: ${errs.length?errs.join("; "):"none"}.${pend.length?" Not available live right now: "+pend.join(", ")+".":""}`;
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
  livePrice();liveKlines();liveDeriv();liveExtra();setInterval(liveDeriv,60000);setInterval(liveExtra,30000);setInterval(livePrice,5000);setInterval(liveKlines,60000);setInterval(tick,1000);
  setInterval(async()=>{try{await loadStatic();renderStatic();renderChart();}catch(e){}},5*60000);
})();


function classifyFlow(f,T){const p=f.px4h,oi=f.oi4h,sp=f.spot4h,pp=f.perp4h,s=v=>(v>=0?"+":"")+(+v).toFixed(v!=null&&Math.abs(v)<10?2:0);
  if(p==null)return{tag:"Neutral",why:"no data"};
  if(pp!=null&&pp<=-T.cvdBigBtc&&Math.abs(p)<=T.priceFlatPct&&(sp||0)>=0)return{tag:"Bullish Absorption",why:`perp CVD ${s(pp)} BTC into flat price (${s(p)}%), spot CVD ${s(sp)}`};
  if(pp!=null&&pp>=T.cvdBigBtc&&Math.abs(p)<=T.priceFlatPct&&(sp||0)<0)return{tag:"Bearish Distribution",why:`perp CVD ${s(pp)} BTC into flat price (${s(p)}%), spot CVD ${s(sp)}`};
  if(oi!=null){const w=`price ${s(p)}%, OI ${s(oi)}%`;
    if(p>T.priceFlatPct&&oi<=-T.oiChgPct)return{tag:"Short Covering",why:w};if(p<-T.priceFlatPct&&oi<=-T.oiChgPct)return{tag:"Long Squeeze",why:w};
    if(p>T.priceFlatPct&&oi>=T.oiChgPct)return{tag:"New Longs",why:w};if(p<-T.priceFlatPct&&oi>=T.oiChgPct)return{tag:"New Shorts",why:w};}
  return{tag:"Neutral",why:`price ${s(p)}% 4h, OI ${oi!=null?s(oi)+"%":"n/a"}, spot CVD ${s(sp)}, perp CVD ${pp!=null?s(pp):"n/a"}`};}
function liveAggWalls(){const ks=["spot","okxPerp","bybitPerp"].filter(k=>BK[k]);if(!ks.length)return null;
  const agg={},W={},reach={};for(const k of ks){const d=depthCalc(BK[k][0],BK[k][1]);reach[k]=d.reachPct;
    for(const b of [1,2]){const g=agg["b"+b]=agg["b"+b]||{bid:0,ask:0,venues:[]};g.bid+=d["b"+b].bid;g.ask+=d["b"+b].ask;g.venues.push(`${k} ${d["b"+b].full?"full":"to ±"+d.reachPct.toFixed(2)+"%"}`);}
    for(const [side,L] of [["bid",BK[k][0]],["ask",BK[k][1]]])for(const [p,q] of L){const b=Math.floor(p/50)*50,key=side+b;W[key]=(W[key]||0)+p*q;}}
  for(const g of Object.values(agg))g.imb=(g.bid-g.ask)/(g.bid+g.ask)*100;
  const walls={};for(const t of [77800,78650]){let bb=null,aa=null;for(const [key,v] of Object.entries(W)){const side=key.slice(0,3),b=+key.slice(3);if(Math.abs(b+25-t)>t*0.004)continue;
    if(side==="bid"&&(!bb||v>bb.usd))bb={p:b,usd:v};if(side==="ask"&&(!aa||v>aa.usd))aa={p:b,usd:v};}walls[t]={bid:bb,ask:aa};}
  return{agg,walls};}
function renderV3(){
  const T=C.flowThresholds||{priceFlatPct:.3,oiChgPct:.5,cvdBigBtc:300},sf=D.flowRegime||{};
  const lv=X.k1hLive?{...X.k1hLive,perp4h:X.bPerpK?.p4??sf.perp4h,oi4h:X.oiHist?.oi4h??sf.oi4h}:null;
  const fr=lv?{...lv,...classifyFlow(lv,T)}:sf,frT=tag(!!lv);
  const R=D.regime||{};
  $("regime").innerHTML=kv([["Flow regime",fr.tag?`${fr.tag}${frT}`:M],["Why",fr.why||M],["Regime",R.label?`${R.label} · snapshot ${snapT()} SGT`:M],
    ["Hurst 1H / daily",`${R.h1h??M} / ${R.hD??M}`],["Var ratio 1H / daily",`${R.vr1h??M} / ${R.vrD??M}`],["Chop(14) 1H / 4H",`${R.chop1h??M} / ${R.chop4h??M}`]]);
  $("regNote").textContent=`${R.line||""} ${R.basis?"· "+R.basis:""}. Flow thresholds (config): flat ±${T.priceFlatPct}%, OI ±${T.oiChgPct}%, big perp CVD ${T.cvdBigBtc} BTC, 4H window.`;
  const V=D.vp;
  $("vp").innerHTML=V?kv([["7d POC / VAH / VAL",V["7d"]?`${n0(V["7d"].poc)} / ${n0(V["7d"].vah)} / ${n0(V["7d"].val)}`:M],["30d POC / VAH / VAL",V["30d"]?`${n0(V["30d"].poc)} / ${n0(V["30d"].vah)} / ${n0(V["30d"].val)}`:M],
    ["AVWAP 30d",n0(V.avwap30d)],[`AVWAP swing low (${n0(V.swingLow?.p)}, ${V.swingLow?myt(V.swingLow.t,{day:"2-digit",month:"short"}):""})`,n0(V.avwapSwingLow)],
    ["Bid zone 77.8-78.0k",V.zone?`${V.zone.tag} (${V.zone.ratio}x median bin)`:M],["Basis",`${V.basis}, snapshot ${snapT()} SGT`]]):kv([["Volume profile","n/a"]]);
  const v=D.vol||{},o=X.opt||D.opt,dv=X.dvol?.dvol??o?.dvol,vrp=typeof dv==="number"&&typeof v.rv7d==="number"?dv-v.rv7d:null;
  const rr=x=>x?`${x.rr>=0?"+":""}${x.rr} (C ${x.call} / P ${x.put}, ${x.expiry}, ${x.days}d)`:M;
  $("vol").innerHTML=kv([["25d RR ~7d",rr(v.rr7d)],["25d RR ~30d",rr(v.rr30d)],["RV 7d (1H, ann.)",v.rv7d!=null?v.rv7d+"%":M],["DVOL",typeof dv==="number"?dv.toFixed(1)+tag(!!X.dvol):M],
    ["VRP (DVOL − RV7d)",vrp!=null?`${vrp>=0?"+":""}${vrp.toFixed(1)} pts`:M],["Basis",(v.basis||"")+`, snapshot ${snapT()} SGT`]]);
  const E=D.etf;
  $("etf").innerHTML=E?kv([["Latest day",`${E.usdM>=0?"+":"−"}$${Math.abs(E.usdM)}M, ${E.date}`],["IBIT / FBTC",`${E.ibit??M} / ${E.fbtc??M} $M`],["Last 5 days sum",E.sum5!=null?`${E.sum5>=0?"+":"−"}$${Math.abs(E.sum5)}M`:M],
    ["Last 5",(E.last5||[]).map(x=>`${x[0].slice(0,6)} ${x[1]>=0?"+":""}${x[1]}`).join(", ")||M],["Source",`${E.source||"metrics file"}, snapshot ${snapT()} SGT`]]):kv([["ETF","n/a"]]);
}
// ---- Copy for AI ----
const tx=el=>el.textContent.replace(/\s+/g," ").trim();
function buildPacket(){
  const now=Date.now(),L=[];
  L.push(`# BTC Swing HUD packet, ${myt(now,{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false})} SGT`);
  L.push("Instruction for AI: BTC spot swing-trade data (SGT, UTC+8). Analyse the setup, levels, triggers and risks; say what would change the view. Not financial advice.");
  L.push(`Provenance: values tagged "live" were fetched in the browser just now; untagged or "snapshot HH:MM SGT" values come from the 15-min snapshot (${D?.asOf||M}). Live price source: ${live.src||"none (snapshot)"}. Liquidation levels (CoinGlass) are real levels read from the CoinGlass map; the model estimate is a backup.`);
  for(const s of document.querySelectorAll("main section.card")){
    const h=s.querySelector("h2"),title=h?tx(h):(s.id==="verdict"?"Verdict":s.querySelector("summary")?tx(s.querySelector("summary")):"");
    L.push("",`## ${title}`);
    if(s.id==="verdict"){L.push(`- ${tx(s.querySelector(".lead"))}`,`- Price: ${tx(s.querySelector(".price"))}${live.src?" · live":" · snapshot"} (${tx(s.querySelector(".price").nextElementSibling)})`);}
    if(s.querySelector("#chart")){const h=(live.h1||D?.h1||[]).map(x=>x[1]),d=(D?.d1||[]).map(x=>x[1]);
      if(h.length)L.push(`- 48h 1H closes: low ${n0(Math.min(...h))}, high ${n0(Math.max(...h))}, last ${n0(h[h.length-1])}${live.h1?" · live":" · snapshot"}`);
      if(d.length)L.push(`- 30d daily closes: low ${n0(Math.min(...d))}, high ${n0(Math.max(...d))}, last ${n0(d[d.length-1])} · snapshot`);
      L.push(`- Levels: ${C.levels.map(l=>`${n0(l.p)} ${l.label.replace(/^[\d.]+k\s*/,"")}`).join("; ")}. Bid zone ${n0(C.bidZone.lo)}-${n0(C.bidZone.hi)}.`);}
    if(s.querySelector("#bots")){C.bots.forEach(g=>g.bots.forEach(b=>L.push(`- ${b.code} ${b.name} [${g.section}]: ${b.status||"Not run this cycle"}${b.detail?" ("+b.detail+")":""}`)));continue;}
    s.querySelectorAll(".row").forEach(r=>{const t=r.querySelector(".t"),d=r.querySelector(".d"),p=r.querySelector(".pill");L.push(`- ${t?tx(t):""}${d?" ("+tx(d)+")":""}${p?": "+tx(p):""}`);});
    s.querySelectorAll("dt").forEach(dt=>L.push(`- ${tx(dt)}: ${tx(dt.nextElementSibling)}`));
    s.querySelectorAll("p.mut").forEach(p=>{const t=tx(p);if(t)L.push(`Note: ${t}`);});
  }
  return L.join("\n")+"\n";
}
function stamp(){const p=Object.fromEntries(new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Kuala_Lumpur",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).formatToParts(new Date()).map(x=>[x.type,x.value]));return `${p.year}${p.month}${p.day}-${p.hour}${p.minute}-SGT`;}
function flash(m){$("copyMsg").textContent=m;clearTimeout(flash.t);flash.t=setTimeout(()=>$("copyMsg").textContent="",3000);}
async function copyPacket(){const t=buildPacket();
  try{await navigator.clipboard.writeText(t);flash(`Copied ✓ (${t.length} chars)`);return;}catch(e){}
  const ta=document.createElement("textarea");ta.value=t;ta.setAttribute("readonly","");ta.style.cssText="position:fixed;top:0;left:0;opacity:0;font-size:16px";document.body.appendChild(ta);
  ta.focus();ta.select();ta.setSelectionRange(0,t.length);let ok=false;try{ok=document.execCommand("copy");}catch(e){}ta.remove();
  flash(ok?`Copied ✓ (${t.length} chars)`:"Copy blocked, use Download");}
function dl(name,text,type){const u=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement("a");a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),2000);}
$("bCopy").onclick=copyPacket;
$("bDl").onclick=()=>{dl(`btc-hud-${stamp()}.md`,buildPacket(),"text/markdown");flash("Downloaded .md ✓");};
$("bJson").onclick=()=>{dl(`btc-hud-${stamp()}.json`,JSON.stringify({exportedAtSGT:stamp(),live:{price:live.price,src:live.src,last1h:live.last1h,derivs:X},snapshot:D,config:C},null,1),"application/json");flash("Downloaded JSON ✓");};
window.buildPacket=buildPacket;
if(location.hash==="#packet-test")setTimeout(()=>{const p=document.createElement("pre");p.id="pkt";p.textContent=buildPacket();document.body.appendChild(p);},10000);
