"""Regime Radar (rules from A4.3 BTC Regime Radar, configs A-J), computed by HUD. compute(D)->dict. Fail-soft."""
import datetime as dt
SGT=dt.timezone(dt.timedelta(hours=8))
PRIO="EGJCABDHFI"
NAMES={"A":"Healthy Bull","B":"Leveraged Bull (fragile)","C":"Bullish Absorption","D":"Masked Fragility","E":"Liquidation Cascade",
 "F":"Re-Accumulation","G":"Short Squeeze","H":"Distribution Top","I":"Bear Trend","J":"Bear Trap (capitulation absorption)"}
STATUS={"A":"Healthy","B":"Alert","C":"Watch","D":"Cash","E":"Cascade","F":"Watch","G":"Alert","H":"Cash","I":"Cash","J":"Watch"}
TONE={"A":"good","C":"good","F":"good","J":"good","B":"warn","G":"warn","D":"bad","E":"bad","H":"bad","I":"bad"}
ACT={"A":"Full spot long 1.0x; 60% breakout / 40% VWAP retest; stop 4H swing low -0.6%",
 "B":"Stand aside 0.0x; no new buys; harvest 33% into perp pump",
 "C":"Build spot 0.75x; 50% on 1H range reclaim / 50% limit at low; stop sweep low -0.5%",
 "D":"Defensive cash; sell 50% on 1H close below VWAP",
 "E":"Wait 0.0x, don't catch the knife; deploy 0.5x ladder only after liqs fade + OI flat + 15m hammer",
 "F":"Re-accumulate 0.75x; 50% on 4H close above base POC / 50% limit; stop base floor -0.5%",
 "G":"Harvest only 0.0x; never buy the squeeze peak",
 "H":"Defensive cash; sell 70% on 4H rejection",
 "I":"Strict cash; treat relief bounces as exit liquidity; invalidation 1D close > 50D MA with positive spot CVD",
 "J":"Reclaim buy 0.9-1.0x on 4H close back above broken support; stop wick low -0.6%"}
MISSING_ALWAYS=["Daily/Weekly VWAP","Spot volume vs 20D MA","Futures basis (annualized)","Whale exchange inflows / CDD","ATR compression history","Spot CVD 7D/14D slope"]
def _g(d,*ks):
    for k in ks:
        if not isinstance(d,dict): return None
        d=d.get(k)
    return d if isinstance(d,(int,float)) and not isinstance(d,bool) else None
def _metrics(D):
    m={}; P=_g(D,"price"); m["price"]=P
    h=[x[1] for x in (D.get("h1") or []) if isinstance(x,(list,tuple)) and len(x)>1]
    d=[x[1] for x in (D.get("d1") or []) if isinstance(x,(list,tuple)) and len(x)>1]
    if P and len(h)>=4: m["chg1h"]=(P/h[-1]-1)*100; m["chg4h"]=(P/h[-4]-1)*100
    m["chg24"]=_g(D,"chg24")
    if P and len(h)>=24: w=h[-48:]+[P]; m["range48"]=(max(w)-min(w))/P*100
    if P and len(d)>=10: m["hi30"]=max(d); m["lo30"]=min(d[:-2]) if len(d)>2 else min(d); m["low48"]=min(h[-48:]) if h else None
    for k in ("ma20Pct","ma50Pct","ma200Pct","atrPct"): m[k]=_g(D,"tech",k)
    m["spot24"]=_g(D,"flow","spot24h"); m["spot4"]=_g(D,"flow","spot4h"); m["perp4"]=_g(D,"flow","perp4h")
    fa=_g(D,"flow","asOfMs")
    if fa is None or dt.datetime.now(dt.timezone.utc).timestamp()*1000-fa>3600e3:  # stale (>1h) or untimestamped CVD excluded
        m["spot24"]=m["spot4"]=m["perp4"]=None; m["_staleCVD"]=True
    m["oi24"]=_g(D,"cz","oiChg24") if _g(D,"cz","oiChg24") is not None else _g(D,"pos","oiChg24")
    oh=[x[1] for x in ((D.get("cz") or {}).get("oiHist") or []) if isinstance(x,(list,tuple))]
    if len(oh)>=5: m["oi1h"]=(oh[-1]/oh[-2]-1)*100; m["oi4h"]=(oh[-1]/oh[-5]-1)*100
    f=[_g(D,"cz","fundAvg"),_g(D,"pos","fundBinance"),_g(D,"pos","fundOKX"),_g(D,"pos","fundBybit")]
    m["fund"]=next((x for x in f if x is not None),None)
    m["etf"]=_g(D,"etf","usdM"); m["liqL"]=_g(D,"cz","liqLongUsd24"); m["liqS"]=_g(D,"cz","liqShortUsd24")
    m["imb"]=_g(D,"depth","agg","b1","imb")
    n=D.get("news") or {}; m["newsHigh"]=(n.get("risk")=="HIGH") if n.get("ok") else None
    return m
def _rules(m):
    def c(label,keys,fn):
        if any(m.get(k) is None for k in keys): return (label,None)
        try: return (label,bool(fn(*[m[k] for k in keys])))
        except Exception: return (label,None)
    return {
    "A":[c("Price rising 4h & 24h",["chg4h","chg24"],lambda a,b:a>0 and b>0),c("Above 20D MA",["ma20Pct"],lambda a:a>0),
         c("Spot CVD 24h positive",["spot24"],lambda a:a>0),c("ETF net > +$150M",["etf"],lambda a:a>150),
         c("OI 24h -1%..+4%",["oi24"],lambda a:-1<=a<=4),c("Funding +0.002..+0.010%",["fund"],lambda a:0.002<=a<=0.010),
         c("Perp CVD positive, not > spot",["perp4","spot4"],lambda p,s:p>0 and p<=abs(s)*1.5)],
    "B":[c("Vertical move (24h > 2.5x ATR%)",["chg24","atrPct"],lambda a,b:a>2.5*b),c("Spot CVD 24h flat/negative",["spot24"],lambda a:a<=0),
         c("Perp CVD aggressive vs spot",["perp4","spot4"],lambda p,s:p>0 and p>2*max(s,0)),c("OI 24h > +7%",["oi24"],lambda a:a>7),
         c("Funding >= +0.025%",["fund"],lambda a:a>=0.025)],
    "C":[c("Negative headline risk",["newsHigh"],lambda a:a),c("Testing 200D MA / 30d low",["ma200Pct","price","lo30"],lambda a,p,l:abs(a)<=3 or p<=l*1.02),
         c("Spot CVD 24h strongly positive (>500 BTC)",["spot24"],lambda a:a>500),c("Perp CVD 4h negative",["perp4"],lambda a:a<0),
         c("OI 24h flat/dropping (<=+1%)",["oi24"],lambda a:a<=1),c("Funding -0.008..+0.002%",["fund"],lambda a:-0.008<=a<=0.002),
         c("Book bids/asks >= 1.4 (imb >= +16.7%)",["imb"],lambda a:a>=16.7)],
    "D":[c("Churning near 30d high (within 2%)",["price","hi30"],lambda p,h:p>=h*0.98),c("Spot CVD 24h negative",["spot24"],lambda a:a<0),
         c("Perp CVD positive",["perp4"],lambda a:a>0),c("OI rising + funding > +0.015%",["oi24","fund"],lambda o,f:o>0 and f>0.015),
         c("Below 20D MA (VWAP-break proxy)",["ma20Pct"],lambda a:a<0)],
    "E":[c("Price -4% in 1h",["chg1h"],lambda a:a<=-4),c("Long liqs 24h > $100M",["liqL"],lambda a:a>100e6),
         c("OI <= -5% 1h or <= -10% 4h",["oi1h","oi4h"],lambda a,b:a<=-5 or b<=-10),c("Funding deeply negative (< -0.01%)",["fund"],lambda a:a<-0.01)],
    "F":[c("Tight 48h range < 2.5%",["range48"],lambda a:a<2.5),c("OI 24h -1.5..+2%",["oi24"],lambda a:-1.5<=a<=2),
         c("Funding reset 0..+0.004%",["fund"],lambda a:0<=a<=0.004),c("Spot CVD 24h flat/green",["spot24"],lambda a:a>=0)],
    "G":[c("Pump +3% in 4h",["chg4h"],lambda a:a>=3),c("Funding <= -0.015%",["fund"],lambda a:a<=-0.015),
         c("OI 1h <= -3%",["oi1h"],lambda a:a<=-3),c("Short liqs 24h > $50M",["liqS"],lambda a:a>50e6),
         c("Perp CVD > spot CVD",["perp4","spot4"],lambda p,s:p>0 and p>s)],
    "H":[c("At 30d high (within 1%)",["price","hi30"],lambda p,h:p>=h*0.99),c("Spot CVD 24h negative",["spot24"],lambda a:a<0),
         c("Funding > +0.020%",["fund"],lambda a:a>0.020)],
    "I":[c("Below 20D MA",["ma20Pct"],lambda a:a<0),c("Below 50D MA",["ma50Pct"],lambda a:a<0),c("Spot CVD 24h negative",["spot24"],lambda a:a<0),
         c("Funding neutral/positive (trapped longs)",["fund"],lambda a:a>=0),c("OI not clearing (24h >= -1%)",["oi24"],lambda a:a>=-1)],
    "J":[c("Swept below 30d low",["low48","lo30"],lambda a,b:a<b),c("Funding <= -0.020%",["fund"],lambda a:a<=-0.020),
         c("OI surging into lows (24h > +3%)",["oi24"],lambda a:a>3),c("Spot CVD 24h flat/rising",["spot24"],lambda a:a>=0),
         c("Reclaimed 30d low",["price","lo30"],lambda p,l:p>l),c("Panic headline",["newsHigh"],lambda a:a)]}
def _fmt(m):
    f=lambda k,s:(s.format(m[k]) if m.get(k) is not None else None)
    return [x for x in [f("ma20Pct","Price vs 20D MA {:+.2f}%"),f("ma50Pct","vs 50D MA {:+.2f}%"),f("spot24","Spot CVD 24h {:+.0f} BTC"),
      f("perp4","Perp CVD 4h {:+.0f} BTC"),f("oi24","OI 24h {:+.2f}%"),f("fund","Funding {:+.4f}%"),f("range48","48h range {:.2f}%"),f("imb","Book imbalance ±1% {:+.1f}%")] if x]
def compute(D):
    try:
        m=_metrics(D); R=_rules(m); sc={}
        for k,rs in R.items():
            av=[r for r in rs if r[1] is not None]; met=[r for r in av if r[1]]
            sc[k]={"met":len(met),"avail":len(av),"total":len(rs),"ratio":len(met)/len(av) if av else 0,
                   "hits":[r[0] for r in met],"miss":[r[0] for r in rs if r[1] is None],"fail":[r[0] for r in av if not r[1]]}
        active=[k for k in PRIO if sc[k]["avail"]>=3 and sc[k]["met"]*2>sc[k]["avail"]]
        rank=sorted(sc,key=lambda k:(-sc[k]["ratio"],-sc[k]["met"],PRIO.index(k)))
        if active: best=active[0]; second=next((k for k in active[1:]),next(k for k in rank if k!=best))
        else: best=None; second=rank[0]
        nd=dt.datetime.now(SGT); now=nd.strftime("%d %b %H:%M SGT"); nms=int(nd.timestamp()*1000)
        stale=["Spot/Perp CVD (stale >1h or untimestamped)"] if m.get("_staleCVD") else []
        ev=lambda k:sc[k]["hits"][:5]
        if best is None:
            return {"ok":True,"config":None,"label":"No clear config (mixed)","status":"Watch","tone":"warn","confidence":0,"confLabel":"Low",
              "runnerUp":f'{second} {NAMES[second]} ({sc[second]["met"]}/{sc[second]["avail"]})',"evidence":_fmt(m)[:5],
              "implication":"Stand aside / follow A3.1 plan triggers only; no regime edge","missing":MISSING_ALWAYS+stale,"asOfMs":nms,"scores":{k:f'{v["met"]}/{v["avail"]}' for k,v in sc.items()},"asOf":now}
        s=sc[best]; n=s["met"]
        return {"ok":True,"config":best,"label":f"{best} — {NAMES[best]}","status":STATUS[best],"tone":TONE[best],
          "confidence":round(100*s["ratio"]),"confLabel":"High" if n>=5 else "Medium" if n>=3 else "Low",
          "matched":f'{n}/{s["avail"]} available ({s["total"]} listed)',
          "runnerUp":f'{second} {NAMES[second]} ({sc[second]["met"]}/{sc[second]["avail"]})',
          "evidence":ev(best),"metrics":_fmt(m)[:6],"implication":ACT[best],"notMet":s["fail"],
          "missing":sorted(set(MISSING_ALWAYS+s["miss"]+stale)),"asOfMs":nms,"scores":{k:f'{v["met"]}/{v["avail"]}' for k,v in sc.items()},"asOf":now}
    except Exception as e:
        return {"ok":False,"label":"n/a","err":str(e)[:120]}
