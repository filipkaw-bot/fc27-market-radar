import json, os, math, hashlib
from datetime import datetime, timezone
from market_provider import MarketProvider

TAX=0.05

def first(o,*keys,default=None):
    for k in keys:
        if isinstance(o,dict) and o.get(k) is not None:return o[k]
    return default

def number(v):
    if isinstance(v,(int,float)):return v
    if isinstance(v,str):
        try:return float(v.replace(",","").replace(" ","").strip())
        except ValueError:return None
    return None

def flatten(data):
    p=first(data,"players","results","items","data",default=[]) or []
    if isinstance(p,dict):p=first(p,"players","results","items","data",default=[])
    return p if isinstance(p,list) else []

def market_snapshot(provider,evos):
    positions=sorted({pos for evo in evos for pos in (evo.get("requirements",{}).get("positions") or [])})
    mins=[evo.get("requirements",{}).get("overall_min") for evo in evos if evo.get("requirements",{}).get("overall_min") is not None]
    maxs=[evo.get("requirements",{}).get("overall_max") for evo in evos if evo.get("requirements",{}).get("overall_max") is not None]
    params={
        "sort_by_price":"asc",
        "min_price":200,
        "min_rating":int(min(mins)) if mins else 40,
        "max_rating":int(max(maxs)) if maxs else 99,
    }
    if positions:
        params["position"]=",".join(positions)
        params["position_type"]="any"
    data=provider.players(**params)
    players=flatten(data)
    out=[]
    for p in players:
        cid=str(first(p,"id","card_id",default=""))
        price=number(first(p,"price_ps_coins","price","price_ps"))
        if not cid or price is None or price<200:continue
        rating=number(first(p,"rating"))
        out.append({
            "card_id":cid,
            "name":first(p,"name",default="Unknown"),
            "rating":int(rating) if rating is not None else None,
            "position":first(p,"position"),
            "league":first(p,"league"),
            "club":first(p,"club"),
            "nation":first(p,"nation"),
            "card_type":first(p,"version","card_type"),
            "price":int(price),
            "trend":number(first(p,"trend_ps","trend"))
        })
    return out,params

def qualifies(p,req):
    r=p.get("rating")
    if req.get("overall_min") is not None and (r is None or r<int(req["overall_min"])):return False
    if req.get("overall_max") is not None and (r is None or r>int(req["overall_max"])):return False
    positions=set(req.get("positions") or [])
    excluded=set(req.get("excluded_positions") or [])
    pos=p.get("position")
    if positions and pos not in positions:return False
    if pos in excluded:return False
    return True

def score_pool(pool,evo):
    if not pool:return []
    prices=sorted(x["price"] for x in pool); median=prices[len(prices)//2]; out=[]
    for x0 in pool:
        x=dict(x0); rank=sum(p<=x["price"] for p in prices)
        discount=(median-x["price"])/median if median else 0
        near=sum(p<=x["price"]*1.15 for p in prices)
        score=50+min(20,max(0,round(discount*40)))
        score+=12 if rank<=3 else 6 if rank<=7 else 0
        score+=10 if near<=2 else 5 if near<=5 else 0
        score+=5 if len(prices)<=8 else 0
        if x.get("trend") is not None and x["trend"]>10:score+=5
        score=min(100,score)
        x.update({
            "evolution":evo,"score":score,
            "action":"buy" if score>=85 else "watch" if score>=60 else "skip",
            "net_sale":math.floor(x["price"]*(1-TAX)),
            "potential_vs_median":round(discount*100,1),
            "qualifying_cards_found":len(prices),
            "price_rank":rank,
            "price_percentile":round(rank/len(prices)*100,1),
            "supply_proxy":near,
            "tags":["EVO","ELIGIBLE"],
            "why":f"{evo}: {len(prices)} kwalifikujących kart znalezionych w skanie rynku. Karta #{rank} cenowo, {round(discount*100,1)}% poniżej mediany; {near} kart w +15% ceny."
        })
        if rank<=3:x["tags"].append("LOW PRICE")
        if near<=2:x["tags"].append("BOTTLENECK PROXY")
        if len(prices)<=8:x["tags"].append("LOW QUALIFIER COUNT")
        if x.get("trend") is not None and x["trend"]>10:x["tags"].append("UPTREND")
        out.append(x)
    return out

def run():
    provider=MarketProvider(platform=os.getenv("FC27_PLATFORM","ps"))
    if not provider.enabled:raise RuntimeError("PARSE_API_KEY missing")
    with open("data/opportunities.json",encoding="utf-8") as f:content=json.load(f)
    evos=[x for x in content if x.get("kind")=="Evolutions" and x.get("requirements")]
    fingerprint=hashlib.sha256(json.dumps(evos,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    try:
        with open("data/market.json",encoding="utf-8") as f:old=json.load(f)
    except Exception:old={}
    if old.get("content_fingerprint")==fingerprint and old.get("opportunities"):
        print("content unchanged; keeping existing market scan");return
    try:
        snapshot,params=market_snapshot(provider,evos[:12])
        print("market request filters:",params)
        print("market rows:",len(snapshot))
        rows=[]
        for evo in evos[:12]:
            req=evo["requirements"]
            rows.extend(score_pool([dict(p) for p in snapshot if qualifies(p,req)],evo["name"]))
    except Exception as e:
        print("market scan failed:",e)
        snapshot=[]; rows=[]; params={}
    dedup={(x["card_id"],x["evolution"]):x for x in rows}
    rows=list(dedup.values()); rows.sort(key=lambda x:(x.get("score",0),x.get("potential_vs_median",0)),reverse=True)
    payload={
        "updated":datetime.now(timezone.utc).isoformat(),
        "content_fingerprint":fingerprint,
        "provider":provider.health(),
        "content_triggers":len(evos),
        "market_request_filters":params,
        "market_rows_scanned":len(snapshot),
        "scoring_note":"Supply is a price-distribution proxy from the cheapest qualifying market cards; no live auction-count claim is made.",
        "opportunities":rows[:150]
    }
    os.makedirs("data",exist_ok=True)
    with open("data/market.json","w",encoding="utf-8") as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print("market opportunities:",len(rows))

if __name__=="__main__":run()
