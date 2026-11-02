"""Extra HUD metrics (free sources). add(D, get, missing, oi_hist) mutates D.
get(url,name)->json|None (logs its own errors). oi_hist: {epoch_s: total_oi_usd} hourly (Coinalyze) or None."""
import time, datetime as dt
SPOTS=["https://data-api.binance.vision/api/v3","https://api.binance.com/api/v3","https://api.binance.us/api/v3"]
def _kl(get,interval,limit):
    for b in SPOTS:
        k=get(f"{b}/klines?symbol=BTCUSDT&interval={interval}&limit={limit}",f"klines {interval} ({b.split('/')[2]})")
        if k: return k
    return None
def rsi(c,n=14):
    if len(c)<=n: return None
    g=[max(0,c[i]-c[i-1]) for i in range(1,len(c))]; l=[max(0,c[i-1]-c[i]) for i in range(1,len(c))]
    ag=sum(g[:n])/n; al=sum(l[:n])/n
    for i in range(n,len(g)): ag=(ag*(n-1)+g[i])/n; al=(al*(n-1)+l[i])/n
    return round(100 if al==0 else 100-100/(1+ag/al),1)
def atr(k,n=14):
    tr=[max(float(x[2])-float(x[3]),abs(float(x[2])-float(p[4])),abs(float(x[3])-float(p[4]))) for p,x in zip(k,k[1:])]
    if len(tr)<n: return None
    a=sum(tr[:n])/n
    for t in tr[n:]: a=(a*(n-1)+t)/n
    return round(a,1)
def technicals(D,get,missing):
    kd=_kl(get,"1d",260); k4=_kl(get,"4h",120)
    if not kd: missing.append("Technicals: no daily klines"); return
    kd=kd[:-1]; c=[float(x[4]) for x in kd]; P=D.get("price") or c[-1]
    T={"rsiD":rsi(c),"atrD":atr(kd),"basis":"closed candles, Binance spot"}
    for n in (20,50,200):
        if len(c)>=n: m=sum(c[-n:])/n; T[f"ma{n}"]=round(m,1); T[f"ma{n}Pct"]=round((P/m-1)*100,2)
    if T.get("atrD"): T["atrPct"]=round(T["atrD"]/P*100,2)
    if k4: T["rsi4h"]=rsi([float(x[4]) for x in k4[:-1]])
    D["tech"]=T
def options(D,get,missing):
    r=get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option","Deribit options")
    if not r or not r.get("result"): return
    O=opt_calc(r["result"])
    v=get(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=3600&start_timestamp={int(time.time()*1000)-6*3600000}&end_timestamp={int(time.time()*1000)}","Deribit DVOL")
    if v and v.get("result",{}).get("data"): O["dvol"]=round(v["result"]["data"][-1][4],2)
    D["opt"]=O
MON={m:i+1 for i,m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
def _exp(s):  # 27NOV26 -> datetime 08:00 UTC
    return dt.datetime(2000+int(s[-2:]),MON[s[-5:-2]],int(s[:-5]),8,tzinfo=dt.timezone.utc)
def opt_calc(rows):
    ex={}; tc=tp=0; und=None
    for x in rows:
        _,e,k,cp=x["instrument_name"].split("-"); oi=x.get("open_interest") or 0
        ex.setdefault(e,[]).append((float(k),cp,oi,x.get("mark_iv"),x.get("underlying_price")))
        if cp=="C": tc+=oi
        else: tp+=oi
    now=dt.datetime.now(dt.timezone.utc); tot=tc+tp
    exps=sorted((e for e in ex if _exp(e)>now),key=_exp)
    big=next((e for e in exps if sum(o[2] for o in ex[e])>=0.10*tot),exps[0])
    L=ex[big]; strikes=sorted({o[0] for o in L})
    pain=lambda K:sum(o[2]*max(0,K-o[0]) if o[1]=="C" else o[2]*max(0,o[0]-K) for o in L)
    mp=min(strikes,key=pain); und=next((o[4] for o in L if o[4]),None)
    atm=min(strikes,key=lambda k:abs(k-(und or mp)))
    ivs=[o[3] for o in L if o[0]==atm and o[3]]
    ec=sum(o[2] for o in L if o[1]=="C"); ep=sum(o[2] for o in L if o[1]=="P")
    return {"expiry":big,"expiryOI":round(ec+ep),"maxPain":mp,"pcrExpiry":round(ep/ec,2) if ec else None,
            "pcrAll":round(tp/tc,2) if tc else None,"atmStrike":atm,"atmIV":round(sum(ivs)/len(ivs),1) if ivs else None}
def stables(D,get,missing):
    r=get("https://stablecoins.llama.fi/stablecoins?includePrices=false","DefiLlama stablecoins")
    if not r: return
    S={}
    for a in r.get("peggedAssets",[]):
        if a.get("symbol") in("USDT","USDC"):
            now=(a.get("circulating") or {}).get("peggedUSD"); wk=(a.get("circulatingPrevWeek") or {}).get("peggedUSD")
            if now: S[a["symbol"]]={"usd":round(now),"chg7d":round((now/wk-1)*100,2) if wk else None}
    if S:
        n=sum(v["usd"] for v in S.values()); w=sum(v["usd"]/(1+(v["chg7d"] or 0)/100) for v in S.values())
        D["stables"]={**S,"totalUsd":round(n),"totalChg7d":round((n/w-1)*100,2),"totalChg7dUsd":round(n-w)}
def depth_calc(bids,asks,bands=(1,2)):
    mid=(float(bids[0][0])+float(asks[0][0]))/2; out={"mid":round(mid,1)}
    reach=min(mid-float(bids[-1][0]),float(asks[-1][0])-mid)/mid*100; out["reachPct"]=round(reach,2)
    for b in bands:
        bid=sum(float(p)*float(q) for p,q,*_ in bids if float(p)>=mid*(1-b/100))
        ask=sum(float(p)*float(q) for p,q,*_ in asks if float(p)<=mid*(1+b/100))
        out[f"b{b}"]={"bid":round(bid),"ask":round(ask),"imb":round((bid-ask)/(bid+ask)*100,1) if bid+ask else None,"full":reach>=b}
    return out
def depth(D,get,missing):
    B={}
    r=get("https://data-api.binance.vision/api/v3/depth?symbol=BTCUSDT&limit=5000","Binance spot depth")
    if r: B["spot"]=depth_calc(r["bids"],r["asks"])
    r=get("https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=1000","Binance perp depth")
    if r: B["perp"]=depth_calc(r["bids"],r["asks"])
    r=get("https://www.okx.com/api/v5/market/books-full?instId=BTC-USDT-SWAP&sz=5000","OKX perp depth")
    if r and r.get("data"):  # sz in contracts of 0.01 BTC
        f=lambda L:[[p,float(q)*0.01] for p,q,*_ in L]
        B["okxPerp"]=depth_calc(f(r["data"][0]["bids"]),f(r["data"][0]["asks"]))
    if B: D["depth"]=B
def liq_est(D,get,missing,oi_hist):
    """Estimate only: hourly OI increases (Coinalyze, all venues) are treated as new positions opened at that hour's
    close, split 50/50 long/short and equally across 25x/50x/100x; liq price ~ entry*(1∓1/lev). Levels already
    traded through since entry are dropped. Bucketed in $250 bins."""
    if not oi_hist: missing.append("Liq clusters: needs Coinalyze OI history"); return
    k=_kl(get,"1h",170)
    if not k: return
    k=k[:-1]; ts=sorted(oi_hist); P=D.get("price") or float(k[-1][4]); bins={}
    bars={int(x[0])//1000:x for x in k}
    for a,b in zip(ts,ts[1:]):
        d=oi_hist[b]-oi_hist[a]
        if d<=0 or b not in bars: continue
        e=float(bars[b][4]); later=[x for t,x in bars.items() if t>b]
        lo=min([float(x[3]) for x in later],default=e); hi=max([float(x[2]) for x in later],default=e)
        for lev in (25,50,100):
            for side,lp in (("L",e*(1-1/lev)),("S",e*(1+1/lev))):
                if (side=="L" and lo<=lp) or (side=="S" and hi>=lp): continue
                kb=round(lp/250)*250; bins[kb]=bins.get(kb,0)+d/6
    up=sorted([(p,v) for p,v in bins.items() if p>P],key=lambda x:-x[1])[:3]
    dn=sorted([(p,v) for p,v in bins.items() if p<P],key=lambda x:-x[1])[:3]
    D["liqEst"]={"above":[{"p":p,"usd":round(v)} for p,v in sorted(up)],"below":[{"p":p,"usd":round(v)} for p,v in sorted(dn,reverse=True)],
      "method":"Estimate: Coinalyze 7d hourly OI increases × 25/50/100x leverage, Binance 1H closes; untouched levels only, $250 bins"}
def add(D,get,missing,oi_hist=None):
    for f in (technicals,options,stables,depth):
        try: f(D,get,missing)
        except Exception as e: missing.append(f"{f.__name__}: {type(e).__name__} {e}")
    try: liq_est(D,get,missing,oi_hist)
    except Exception as e: missing.append(f"liq_est: {type(e).__name__} {e}")
    D["noSource"]=["Exchange netflows (no free keyless API: CryptoQuant/Glassnode are paid)"]
