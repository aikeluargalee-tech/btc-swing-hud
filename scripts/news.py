"""News & events module (fail-soft). get_news(extra_path=None) -> dict."""
import json, re, urllib.request, datetime as dt, email.utils, xml.etree.ElementTree as ET
SGT=dt.timezone(dt.timedelta(hours=8))
FEEDS=[("CoinDesk","https://www.coindesk.com/arc/outboundfeeds/rss/"),("Cointelegraph","https://cointelegraph.com/rss"),
       ("The Block","https://www.theblock.co/rss.xml"),("Decrypt","https://decrypt.co/feed")]
KEEP=re.compile(r"\b(bitcoin|btc|crypto|etf|sec|fed|fomc|powell|rate|inflation|cpi|pce|jobs|payroll|treasury|tariff|regulat|stablecoin|liquidat|hack|exploit|strategy|saylor|blackrock|macro|dollar)",re.I)
HIGH=re.compile(r"\b(etf|sec|fed|fomc|powell|hack|exploit|liquidat|tariff|cpi|pce|payroll|rate (cut|hike)|ban)",re.I)
UA={"User-Agent":"Mozilla/5.0 btc-swing-hud"}
def _get(u,t=12): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read()
def _fmt(d): return d.astimezone(SGT).strftime("%d %b %H:%M")
def _headlines(now,extra_path):
    items=[]
    for src,u in FEEDS:
        try:
            root=ET.fromstring(_get(u))
            for it in root.iter("item"):
                t=(it.findtext("title") or "").strip(); l=(it.findtext("link") or "").strip(); p=it.findtext("pubDate")
                if not t or not p: continue
                d=email.utils.parsedate_to_datetime(p)
                if d.tzinfo is None: d=d.replace(tzinfo=dt.timezone.utc)
                items.append((d,t,src,l))
        except Exception: pass
    if extra_path:
        try:
            for x in json.load(open(extra_path)):
                d=dt.datetime.fromisoformat(x["time"]); d=d if d.tzinfo else d.replace(tzinfo=SGT)
                items.append((d,x["title"],x.get("source","A7.1"),x.get("link","")))
        except Exception: pass
    out,seen=[],set()
    for d,t,src,l in sorted(items,reverse=True):
        k=re.sub(r"\W+","",t.lower())[:60]
        if k in seen or (now-d).total_seconds()>12*3600 or d>now+dt.timedelta(minutes=10) or not KEEP.search(t): continue
        seen.add(k); out.append({"title":t,"source":src,"time":_fmt(d),"ageH":round((now-d).total_seconds()/3600,1),"link":l,"high":bool(HIGH.search(t))})
        if len(out)>=5: break
    return out
def _events(now):
    ev=[]
    for u in ("https://nfs.faireconomy.media/ff_calendar_thisweek.json","https://nfs.faireconomy.media/ff_calendar_nextweek.json"):
        try:
            for e in json.loads(_get(u)):
                if e.get("country")!="USD" or e.get("impact")!="High": continue
                d=dt.datetime.fromisoformat(e["date"])
                h=(d-now).total_seconds()/3600
                if -1<h<=7*24: ev.append({"title":e.get("title"),"time":_fmt(d),"inH":round(h,1),"forecast":e.get("forecast") or "","previous":e.get("previous") or ""})
        except Exception: pass
    seen=set(); res=[]
    for e in sorted(ev,key=lambda x:x["inH"]):
        k=(e["title"],e["time"])
        if k not in seen: seen.add(k); res.append(e)
    return res[:8]
def get_news(extra_path=None):
    try:
        now=dt.datetime.now(dt.timezone.utc)
        h=_headlines(now,extra_path); e=_events(now)
        hi=any(x["inH"]<=24 for x in e) or any(x["high"] and x["ageH"]<=3 for x in h)
        why=[f'{x["title"]} in {x["inH"]}h' for x in e if x["inH"]<=24]+[f'flagged headline {x["ageH"]}h ago' for x in h if x["high"] and x["ageH"]<=3]
        return {"asOf":_fmt(now)+" SGT","risk":"HIGH" if hi else "normal","why":"; ".join(why[:3]),"headlines":h,"events":e,
                "ok":bool(h or e)}
    except Exception as ex:
        return {"asOf":None,"risk":"n/a","why":"","headlines":[],"events":[],"ok":False,"err":str(ex)[:120]}
if __name__=="__main__": print(json.dumps(get_news("/workspace/hud/news_items.json"),indent=1))
