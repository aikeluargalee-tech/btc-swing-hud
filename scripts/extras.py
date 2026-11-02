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

# ===================== v3 additions =====================
import math, re, html as _html, urllib.request
def _f(x): return float(x)
def vol_profile(k,P,binw=50):
    """k: klines (closed). Volume spread evenly across each candle's high-low in $binw bins."""
    bins={}
    for x in k:
        h,l,v=_f(x[2]),_f(x[3]),_f(x[5]); a=int(l//binw); b=int(h//binw); n=b-a+1
        for i in range(a,b+1): bins[i]=bins.get(i,0)+v/n
    if not bins: return None
    tot=sum(bins.values()); poc=max(bins,key=bins.get); lo=hi=poc; acc=bins[poc]
    while acc<0.7*tot:
        up=bins.get(hi+1,0); dn=bins.get(lo-1,0)
        if up==0 and dn==0: break
        if up>=dn: hi+=1; acc+=up
        else: lo-=1; acc+=dn
    return {"poc":poc*binw+binw/2,"vah":(hi+1)*binw,"val":lo*binw},bins
def avwap(k):
    pv=sum((_f(x[2])+_f(x[3])+_f(x[4]))/3*_f(x[5]) for x in k); v=sum(_f(x[5]) for x in k)
    return round(pv/v,1) if v else None
def volume_profile(D,k1h,zone):
    k30=k1h[-720:]; k7=k1h[-168:]; P=D.get("price") or _f(k1h[-1][4]); out={"basis":"Computed by HUD from Binance spot 1H klines ($50 bins, 70% VA), not the A5.1 bot"}
    for name,kk in (("7d",k7),("30d",k30)):
        r=vol_profile(kk,P)
        if r: out[name]={a:round(b) for a,b in r[0].items()}
        if name=="30d" and r:
            bins=r[1]; vals=sorted(bins.values()); med=vals[len(vals)//2]
            zb=[bins.get(i,0) for i in range(int(zone["lo"]//50),int(zone["hi"]//50))]
            zv=sum(zb)/len(zb) if zb else 0; ratio=zv/med if med else None
            out["zone"]={"ratio":round(ratio,2) if ratio else None,"tag":"High-volume node" if ratio and ratio>=1.3 else "Air pocket (low-volume)" if ratio and ratio<=0.7 else "Average volume"}
    out["avwap30d"]=avwap(k30)
    i=min(range(len(k30)),key=lambda j:_f(k30[j][3])); out["swingLow"]={"p":_f(k30[i][3]),"t":int(k30[i][0])}
    out["avwapSwingLow"]=avwap(k30[i:])
    D["vp"]=out
def hurst_rs(x):
    n=len(x)
    if n<64: return None
    sizes=[s for s in (8,16,32,64,128,256) if s<=n//2]; pts=[]
    for s in sizes:
        rs=[]
        for i in range(0,n-s+1,s):
            seg=x[i:i+s]; m=sum(seg)/s; y=0; mx=-1e18; mn=1e18
            for v in seg: y+=v-m; mx=max(mx,y); mn=min(mn,y)
            sd=(sum((v-m)**2 for v in seg)/s)**.5
            if sd>0: rs.append((mx-mn)/sd)
        if rs: pts.append((math.log(s),math.log(sum(rs)/len(rs))))
    if len(pts)<3: return None
    mx=sum(p[0] for p in pts)/len(pts); my=sum(p[1] for p in pts)/len(pts)
    return round(sum((p[0]-mx)*(p[1]-my) for p in pts)/sum((p[0]-mx)**2 for p in pts),2)
def var_ratio(r,q):
    n=len(r); m=sum(r)/n; v1=sum((x-m)**2 for x in r)/(n-1)
    rq=[sum(r[i:i+q]) for i in range(n-q+1)]; vq=sum((x-q*m)**2 for x in rq)/len(rq)
    return round(vq/(q*v1),2) if v1 else None
def chop(k,n=14):
    k=k[-(n+1):]; tr=sum(max(_f(x[2])-_f(x[3]),abs(_f(x[2])-_f(p[4])),abs(_f(x[3])-_f(p[4]))) for p,x in zip(k,k[1:]))
    hh=max(_f(x[2]) for x in k[1:]); ll=min(_f(x[3]) for x in k[1:])
    return round(100*math.log10(tr/(hh-ll))/math.log10(n),1) if hh>ll else None
def regime(D,k1h,k4h,kd):
    c=[_f(x[4]) for x in k1h[-501:]]; r=[math.log(b/a) for a,b in zip(c,c[1:])]
    cd=[_f(x[4]) for x in kd]; rd=[math.log(b/a) for a,b in zip(cd,cd[1:])]
    R={"h1h":hurst_rs(r),"hD":hurst_rs(rd),"vr1h":var_ratio(r,4),"vrD":var_ratio(rd,5),"chop1h":chop(k1h),"chop4h":chop(k4h) if k4h else None,
       "basis":"Computed by HUD (R/S Hurst on last 500 1H and ~260 daily log returns; VR(4) 1H, VR(5) daily; Choppiness(14)), not the A4.2 bot"}
    h=R["h1h"]; ch=R["chop1h"]
    if h is None or ch is None: lab,adv="Unclear",""
    elif h<0.45 and ch>=55: lab,adv="Mean-reverting","favour limit bids/fades over breakouts"
    elif h>0.55 and ch<=45: lab,adv="Trending","favour breakouts/continuation over fading"
    elif ch>=61.8: lab,adv="Choppy range","favour limit bids at edges; avoid breakout chasing"
    else: lab,adv="Mixed/transition","no strong edge; wait for trigger confirmation"
    R["label"]=lab; R["line"]=f"Regime: {lab} (H1h={h}, HD={R['hD']}, VR1h={R['vr1h']}, Chop1h={ch}, Chop4h={R['chop4h']})"+(f" -> {adv}" if adv else "")
    D["regime"]=R
    rv=r[-168:]; m=sum(rv)/len(rv); D.setdefault("vol",{})["rv7d"]=round((sum((x-m)**2 for x in rv)/(len(rv)-1))**.5*math.sqrt(24*365)*100,1)
def _ncdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def rr25(rows,days_targets=(7,30)):
    now=dt.datetime.now(dt.timezone.utc); ex={}
    for x in rows:
        _,e,kk,cp=x["instrument_name"].split("-")
        if x.get("mark_iv") and x.get("underlying_price"): ex.setdefault(e,[]).append((float(kk),cp,x["mark_iv"],x["underlying_price"]))
    out={}
    for tgt in days_targets:
        cand=[e for e in ex if (_exp(e)-now).total_seconds()>86400]
        if not cand: continue
        e=min(cand,key=lambda e:abs((_exp(e)-now).total_seconds()/86400-tgt)); T=(_exp(e)-now).total_seconds()/(365*86400)
        pts={"C":[],"P":[]}
        for K,cp,iv,F in ex[e]:
            s=iv/100; d1=(math.log(F/K)+0.5*s*s*T)/(s*math.sqrt(T)); dl=_ncdf(d1) if cp=="C" else _ncdf(d1)-1
            pts[cp].append((abs(dl),iv))
        def at25(p):
            p=sorted(p); 
            for (d0,i0),(d1_,i1) in zip(p,p[1:]):
                if d0<=0.25<=d1_ and d1_>d0: return i0+(i1-i0)*(0.25-d0)/(d1_-d0)
            return None
        c=at25(pts["C"]); pu=at25(pts["P"])
        if c and pu: out[f"rr{tgt}d"]={"rr":round(c-pu,2),"call":round(c,1),"put":round(pu,1),"expiry":e,"days":round(T*365,1)}
    return out
def options_v3(D,get):
    r=get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option","Deribit options")
    if not r or not r.get("result"): return
    rr=rr25(r["result"]); v=D.setdefault("vol",{}); v.update(rr)
    dv=(D.get("opt") or {}).get("dvol")
    if dv and v.get("rv7d"): v["vrp"]=round(dv-v["rv7d"],1)
    v["basis"]="25d RR = call IV - put IV at |delta|=0.25 (Black-Scholes delta from Deribit mark_iv, nearest expiry to 7d/30d); RV7d from 1H closes, annualised"
def etf_farside(D,missing):
    try:
        req=urllib.request.Request("https://farside.co.uk/btc/",headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36","Accept":"text/html","Accept-Language":"en-US,en;q=0.9"})
        s=urllib.request.urlopen(req,timeout=20).read().decode("utf-8","replace")
    except Exception as e: missing.append(f"Farside ETF: {type(e).__name__} {getattr(e,'code','')}".strip()); return
    rows=[[_html.unescape(re.sub(r'<[^>]+>','',c)).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',r,re.S)] for r in re.findall(r'<tr[^>]*>(.*?)</tr>',s,re.S)]
    hdr=next((r for r in rows if "IBIT" in r),None)
    num=lambda t:None if t in("","-") else -float(t.strip("()").replace(",","")) if t.startswith("(") else float(t.replace(",",""))
    days=[r for r in rows if r and re.match(r"\d{2} \w{3} \d{4}$",r[0]) and len(r)>=3]
    days=[r for r in days if num(r[-1]) is not None]
    if not days or not hdr: missing.append("Farside ETF: table not parsed"); return
    last=days[-1]; i=hdr.index("IBIT"); j=hdr.index("FBTC")
    D["etf"]={"usdM":num(last[-1]),"date":last[0],"ibit":num(last[i]),"fbtc":num(last[j]),"last5":[[d[0],num(d[-1])] for d in days[-5:]],"sum5":round(sum(num(d[-1]) for d in days[-5:]),1),"source":"Farside (farside.co.uk/btc), US$m"}
def depth_v3(D,get):
    books={}
    r=get("https://data-api.binance.vision/api/v3/depth?symbol=BTCUSDT&limit=5000","Binance spot depth")
    if r: books["spot"]=(r["bids"],r["asks"])
    r=get("https://www.okx.com/api/v5/market/books-full?instId=BTC-USDT-SWAP&sz=5000","OKX perp depth")
    if r and r.get("data"): f=lambda L:[[p,float(q)*0.01] for p,q,*_ in L]; books["okxPerp"]=(f(r["data"][0]["bids"]),f(r["data"][0]["asks"]))
    r=get("https://api.bybit.com/v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=1000","Bybit perp depth")
    if r and r.get("result"): books["bybitPerp"]=(r["result"]["b"],r["result"]["a"])
    r=get("https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=1000","Binance perp depth")
    if r: books["perp"]=(r["bids"],r["asks"])
    dd=D.setdefault("depth",{})
    for k,(b,a) in books.items(): dd[k]=depth_calc(b,a)
    agg={}; mid=None
    for k in ("spot","okxPerp","bybitPerp"):
        if k in dd:
            mid=mid or dd[k]["mid"]
            for bnd in (1,2):
                x=dd[k][f"b{bnd}"]; g=agg.setdefault(f"b{bnd}",{"bid":0,"ask":0,"venues":[]})
                g["bid"]+=x["bid"]; g["ask"]+=x["ask"]; g["venues"].append(f"{k} {'full' if x['full'] else 'to ±'+str(dd[k]['reachPct'])+'%'}")
    for g in agg.values(): g["imb"]=round((g["bid"]-g["ask"])/(g["bid"]+g["ask"])*100,1) if g["bid"]+g["ask"] else None; g["bid"]=round(g["bid"]); g["ask"]=round(g["ask"])
    dd["agg"]=agg
    # walls: $50 buckets across spot+okx+bybit, within ±0.4% of each trigger
    W={}
    for k in ("spot","okxPerp","bybitPerp"):
        if k not in books: continue
        for side,L in (("bid",books[k][0]),("ask",books[k][1])):
            for p,q,*_ in L:
                b=int(float(p)//50)*50; W[(side,b)]=W.get((side,b),0)+float(p)*float(q)
    dd["walls"]={}
    for t in (77800,78650):
        near=[(s,b,v) for (s,b),v in W.items() if abs(b+25-t)<=t*0.004]
        bb=max([x for x in near if x[0]=="bid"],key=lambda x:x[2],default=None); aa=max([x for x in near if x[0]=="ask"],key=lambda x:x[2],default=None)
        dd["walls"][str(t)]={"bid":{"p":bb[1],"usd":round(bb[2])} if bb else None,"ask":{"p":aa[1],"usd":round(aa[2])} if aa else None}
def flow_regime(D,k1h,cfg):
    """Spot CVD + price change from Binance spot 1H; perp CVD from D.flow if present; OI delta 4h from Coinalyze OI_ALL."""
    c=[_f(x[4]) for x in k1h]; sc=[2*_f(x[9])-_f(x[5]) for x in k1h]
    f={"px1h":round((c[-1]/c[-2]-1)*100,3),"px4h":round((c[-1]/c[-5]-1)*100,3),"spot1h":round(sc[-1],1),"spot4h":round(sum(sc[-4:]),1)}
    fl=D.get("flow") or {}
    if "perp4h" in fl: f["perp4h"]=fl["perp4h"]
    if D.get("_oi4h") is not None: f["oi4h"]=D["_oi4h"]
    f.update(classify_flow(f,cfg)); D["flowRegime"]=f
def classify_flow(f,cfg):
    p=f.get("px4h"); oi=f.get("oi4h"); sp=f.get("spot4h"); pp=f.get("perp4h"); T=cfg
    flat=T["priceFlatPct"]; oiT=T["oiChgPct"]; big=T["cvdBigBtc"]
    if p is None: return {"tag":"Neutral","why":"no data"}
    if pp is not None and pp<=-big and abs(p)<=flat and (sp or 0)>=0: return {"tag":"Bullish Absorption","why":f"perp CVD {pp:+.0f} BTC sold into flat price ({p:+.2f}%), spot CVD {sp:+.0f}"}
    if pp is not None and pp>=big and abs(p)<=flat and (sp or 0)<0: return {"tag":"Bearish Distribution","why":f"perp CVD {pp:+.0f} bought into flat price ({p:+.2f}%), spot CVD {sp:+.0f}"}
    if oi is not None:
        if p>flat and oi<=-oiT: return {"tag":"Short Covering","why":f"price {p:+.2f}%, OI {oi:+.2f}%"}
        if p<-flat and oi<=-oiT: return {"tag":"Long Squeeze","why":f"price {p:+.2f}%, OI {oi:+.2f}%"}
        if p>flat and oi>=oiT: return {"tag":"New Longs","why":f"price {p:+.2f}%, OI {oi:+.2f}%"}
        if p<-flat and oi>=oiT: return {"tag":"New Shorts","why":f"price {p:+.2f}%, OI {oi:+.2f}%"}
    return {"tag":"Neutral","why":f"price {p:+.2f}% 4h, OI {oi if oi is not None else 'n/a'}%, spot CVD {sp:+.0f}, perp CVD {pp if pp is not None else 'n/a'}"}
def add_v3(D,get,missing,oi_hist=None,cfg=None):
    cfg=cfg or {"priceFlatPct":0.3,"oiChgPct":0.5,"cvdBigBtc":300}; zone=(cfg.get("bidZone") or {"lo":77800,"hi":78000})
    if oi_hist:
        ts=sorted(oi_hist)
        if len(ts)>=5: D["_oi4h"]=round((oi_hist[ts[-1]]/oi_hist[ts[-5]]-1)*100,2)
    k1=_kl(get,"1h",1000); k4=_kl(get,"4h",120); kd=_kl(get,"1d",260)
    steps=[]
    if k1: k1=k1[:-1]; steps+= [lambda:volume_profile(D,k1,zone), lambda:flow_regime(D,k1,cfg["flow"] if "flow" in cfg else cfg)]
    if k1 and kd: steps.append(lambda:regime(D,k1,k4[:-1] if k4 else None,kd[:-1]))
    steps+=[lambda:options_v3(D,get), lambda:etf_farside(D,missing), lambda:depth_v3(D,get)]
    for s in steps:
        try: s()
        except Exception as e: missing.append(f"v3: {type(e).__name__} {e}")
    D.pop("_oi4h",None)
