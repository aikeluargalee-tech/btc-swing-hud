#!/usr/bin/env python3
"""BTC Swing HUD refresh. Writes data/hud.json (relative to repo root).
Env: COINALYZE_API_KEY (optional; Coinalyze panels are skipped without it).
Optional: METRICS_FILE path to a btc_metrics_latest.json for CVD/ETF overrides."""
import json, os, urllib.request, urllib.error, datetime as dt, time
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SGT=dt.timezone(dt.timedelta(hours=8)); UA={"User-Agent":"Mozilla/5.0"}
missing=[]; browser_live=[]
BROWSER={"Binance perp depth","Binance futures funding","Binance long/short","Binance perp klines","Bybit ticker","Bybit perp depth"}
def get(u,name):
    try:
        with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15) as r: return json.load(r)
    except Exception as e:
        if name in BROWSER and getattr(e,'code',None) in (451,403): browser_live.append(name)
        else: missing.append(f"{name}: {type(e).__name__} {getattr(e,'code','')}".strip())
        return None
def myt(ms,f="%d %b %H:%M"): return dt.datetime.fromtimestamp(ms/1000,SGT).strftime(f)
D={"asOf":dt.datetime.now(SGT).strftime("%d %b %Y, %H:%M SGT"),"asOfMs":int(time.time()*1000)}
SPOT=["https://api.binance.com/api/v3","https://data-api.binance.vision/api/v3","https://api.binance.us/api/v3"]
src_used=None
def bget(path,name):
    global src_used
    errs=[]
    for b in ([src_used] if src_used else SPOT):
        try:
            with urllib.request.urlopen(urllib.request.Request(b+path,headers=UA),timeout=15) as r:
                j=json.load(r); src_used=b; return j
        except Exception as e: errs.append(f"{name} via {b.split('/')[2]}: {type(e).__name__} {getattr(e,'code','')}".strip())
    missing.extend(errs); return None
t=bget("/ticker/24hr?symbol=BTCUSDT","ticker")
if t: D.update(price=float(t["lastPrice"]),high24=float(t["highPrice"]),low24=float(t["lowPrice"]),chg24=float(t["priceChangePercent"]))
def okx_k(bar,n):
    r=get(f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar={bar}&limit={n}","OKX candles")
    if not r or not r.get("data"): return None
    step=3600000 if bar=="1H" else 86400000
    return [[int(x[0]),0,0,0,x[4],x[5],int(x[0])+step-1,0,0,None] for x in reversed(r["data"])]
k=bget("/klines?symbol=BTCUSDT&interval=1h&limit=49","1H klines") or okx_k("1H",49)
if k:
    D["h1"]=[[myt(x[0],"%d %H:00"),round(float(x[4]),1)] for x in k[:-1]]
    D["last1h"]=float(k[-2][4]); D["last1hAt"]=myt(k[-2][6]+1)
    if k[0][9] is not None:  # spot CVD from taker-buy volume (closed candles)
        c=[2*float(x[9])-float(x[5]) for x in k[:-1]]
        D["flow"]={"spot4h":round(sum(c[-4:]),1),"spot24h":round(sum(c[-24:]),1),"asOf":D["last1hAt"]+" SGT, est. from taker volume"}
k=bget("/klines?symbol=BTCUSDT&interval=1d&limit=31","1D klines") or okx_k("1D",31)
if k:
    D["d1"]=[[myt(x[0],"%d %b"),round(float(x[4]),1)] for x in k[:-1]]
    D["lastD"]=float(k[-2][4]); D["lastDAt"]=myt(k[-2][6]+1)
if "price" not in D:
    r=get("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT","OKX ticker")
    if r and r.get("data"):
        x=r["data"][0]; D.update(price=float(x["last"]),high24=float(x["high24h"]),low24=float(x["low24h"]),chg24=round((float(x["last"])/float(x["open24h"])-1)*100,3)); src_used=src_used or "okx"
D["priceSource"]=(src_used or "okx").split("/")[2] if src_used and "/" in src_used else "okx"
# positioning
pos={}
r=get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT","Binance futures funding")
if r: pos["fundBinance"]=float(r["lastFundingRate"])*100
r=get("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP","OKX funding")
if r and r.get("data"): pos["fundOKX"]=float(r["data"][0]["fundingRate"])*100
r=get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT","Bybit ticker")
if r and r.get("result"):
    x=r["result"]["list"][0]; pos["fundBybit"]=float(x["fundingRate"])*100; pos["oiBybit"]=float(x["openInterest"])
r=get("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT","Binance futures funding")
if r: pos["oiBinance"]=float(r["openInterest"])
r=get("https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP","OKX OI")
if r and r.get("data"): pos["oiOKX"]=float(r["data"][0]["oiCcy"])
r=get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1H","OKX long/short")
if r and r.get("data"): pos["lsOKX"]=float(r["data"][0][1]); pos["lsAt"]=myt(int(r["data"][0][0]))
r=get("https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=1","Binance long/short")
if r: pos["lsBinance"]=float(r[0]["longShortRatio"])
# OKX liquidations (recent filled prints)
r=get("https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT&state=filled&limit=100","OKX liquidations")
if r and r.get("data"):
    L=S=0.0; ts=[]
    for d in r["data"][0]["details"]:
        usd=float(d["sz"])*0.01*float(d["bkPx"]); ts.append(int(d["ts"]))
        if d["posSide"]=="long": L+=usd
        else: S+=usd
    pos.update(liqLongUsd=round(L),liqShortUsd=round(S),liqWindow=f"{myt(min(ts))} to {myt(max(ts))}")
r=get("https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1h&limit=25","Binance perp klines")
if r:
    c=[2*float(x[9])-float(x[5]) for x in r[:-1]]; D.setdefault("flow",{}).update(perp4h=round(sum(c[-4:]),1),perp24h=round(sum(c[-24:]),1))
mf=os.environ.get("METRICS_FILE")
if mf and os.path.exists(mf):
  try:
    m=json.load(open(mf)); pos["oiChg24"]=m["derivatives"]["open_interest"]["change_24h_pct"]
    D["flow"]={"spot4h":m["order_flow"]["spot_cvd_binance"]["4h"]["cvd_btc"],"spot24h":m["order_flow"]["spot_cvd_binance"]["24h"]["cvd_btc"],
      "perp4h":m["derivatives"]["perp_cvd"]["4h"]["cvd_btc"],"perp24h":m["derivatives"]["perp_cvd"]["24h"]["cvd_btc"],"asOf":m["as_of_myt"]}
    D["etf"]={"usdM":m["etf_flows"]["total_net_flow_usd_m"],"date":m["etf_flows"]["latest_date"]}
  except Exception as e: missing.append(f"metrics file: {e}")
D["pos"]=pos
# macro (Yahoo)
mac={}
for key,sym in [("vix","^VIX"),("dxy","DX-Y.NYB"),("us10y","^TNX"),("spx","^GSPC"),("ndx","^IXIC")]:
    r=get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d",f"Yahoo {sym}")
    try:
        q=r["chart"]["result"][0]; c=[x for x in q["indicators"]["quote"][0]["close"] if x is not None]
        ts=q["timestamp"]; mac[key]={"v":round(c[-1],2),"chg":round((c[-1]/c[-2]-1)*100,2),"date":myt(ts[-1]*1000,"%d %b")}
    except Exception: pass
D["macro"]=mac
# sentiment
r=get("https://api.alternative.me/fng/?limit=1","alternative.me F&G")
if r: D["fng"]={"v":int(r["data"][0]["value"]),"label":r["data"][0]["value_classification"],"date":myt(int(r["data"][0]["timestamp"])*1000,"%d %b")}
cb=get("https://api.exchange.coinbase.com/products/BTC-USD/ticker","Coinbase ticker")
if cb and D.get("price"): D["cbPremium"]=round(float(cb["price"])-D["price"],1)

# ---- Coinalyze aggregated (4 calls; key from env, never printed) ----
def _key(): return os.environ.get("COINALYZE_API_KEY") or None
CZ_SYMS="BTCUSDT_PERP.A,BTCUSD_PERP.A,BTCUSDT.6,BTCUSD.6,BTCUSDT_PERP.3,BTCUSD_PERP.3,BTC-PERPETUAL.2,BTC.H,BTC_USDT.Y,BTCUSDT_PERP.4"
CZ_NAMES={"A":"Binance","6":"Bybit","3":"OKX","2":"Deribit","H":"Hyperliquid","Y":"Gate","4":"HTX"}
def cz(path,name,**q):
    k=_key()
    if not k: missing.append(f"Coinalyze {name}: no key"); return None
    q["symbols"]=CZ_SYMS; u="https://api.coinalyze.net/v1/"+path+"?"+"&".join(f"{a}={b}" for a,b in q.items())
    for attempt in (0,1):
        time.sleep(2)
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers={"api_key":k,**UA}),timeout=20) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==429 and attempt==0:
                time.sleep(min(30,float(e.headers.get("Retry-After") or 10))); continue
            err=e; break
        except Exception as e: err=e; break
    if True:
        e=err
        missing.append(f"Coinalyze {name}: {type(e).__name__} {getattr(e,'code','')}".strip()); return None
now_s=int(time.time()); czd={"venues":", ".join(sorted(set(CZ_NAMES.values())))}
r=cz("open-interest-history","OI history",interval="1hour",convert_to_usd="true",**{"from":now_s-7*86400-3600,"to":now_s})
OI_ALL=None
if r:
    tot={}; cnt={}
    for x in r:
        for h in x.get("history",[]): tot[h["t"]]=tot.get(h["t"],0)+h["c"]; cnt[h["t"]]=cnt.get(h["t"],0)+1
    n=len(r); ts=sorted(t for t in tot if cnt[t]==n); OI_ALL={t:tot[t] for t in ts}
    if ts:
        cur=tot[ts[-1]]; old=tot[min(ts,key=lambda t:abs(t-(ts[-1]-86400)))]
        czd.update(oiUsd=round(cur),oiChg24=round((cur/old-1)*100,2),oiHist=[[myt(t*1000,"%d %H:00"),round(tot[t]/1e9,3)] for t in ts[-25:]],oiSymbols=n)
def avg(r,key):
    v=[x["value"] for x in (r or []) if x.get("value") is not None]
    return round(sum(v)/len(v),5) if v else None
r=cz("funding-rate","funding"); 
if r: czd["fundAvg"]=avg(r,"value"); czd["fundBy"]={CZ_NAMES.get(x["symbol"].split(".")[-1],"?")+" "+x["symbol"].split(".")[0]:x["value"] for x in r}
r=cz("predicted-funding-rate","predicted funding")
if r: czd["predFundAvg"]=avg(r,"value")
r=cz("liquidation-history","liquidations",interval="1hour",convert_to_usd="true",**{"from":now_s-24*3600,"to":now_s})
if r:
    L=sum(h["l"] for x in r for h in x.get("history",[])); S=sum(h["s"] for x in r for h in x.get("history",[]))
    czd.update(liqLongUsd24=round(L),liqShortUsd24=round(S))
D["cz"]=czd
import sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import extras
extras.add(D,get,missing,OI_ALL)
try: _c=json.load(open(os.path.join(ROOT,'config','levels.json'))); _cfg=dict(_c.get("flowThresholds",{})); _cfg["bidZone"]=_c.get("bidZone")
except Exception: _cfg=None
extras.add_v3(D,get,missing,OI_ALL,_cfg)
D["missing"]=missing; D["browserLive"]=sorted(set(browser_live))
os.makedirs(os.path.join(ROOT,"data"),exist_ok=True)
try:
    import news; D["news"]=news.get_news(os.path.join(ROOT,"data","news_items.json"))
except Exception: D["news"]=None
json.dump(D,open(os.path.join(ROOT,"data","hud.json"),"w"),indent=1)
print("price",D.get("price"),"source",D.get("priceSource"),"h1",len(D.get("h1",[])),"d1",len(D.get("d1",[])),"missing",len(missing))
for x in missing: print(" -",x)
