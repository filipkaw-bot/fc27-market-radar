import json,os,math,hashlib
from datetime import datetime,timezone
from market_provider import MarketProvider
TAX=0.05

def first(o,*keys,default=None):
    for k in keys:
        if isinstance(o,dict) and o.get(k) is not None:return o[k]
    return default

def flatten(data):
    p=first(data,"players","items","data",default=[]) or []
    if isinstance(p,dict): p=first(p,"players","items","data",default=[])
    return p if isinstance(p,list) else []

def scan_evo(provider,evo,max_pages=2):
    req=evo["requirements"]
    max_rating=req.get("overall_max")
    if not max_rating:return []
    positions=set(req.get("positions") or [])
    excluded=set(req.get("excluded_positions") or [])
    found=[]
    for page in range(1,max_pages+1):
        try:
            data=provider.players(max_rating=max_rating,sort_by="price",sort_order="asc",page=page)
        except Exception as e:
            print("query failed",e); break
        players=flatten(data)
        if not players: break
        for idx,p in enumerate(players):
            price=first(p,"price")
            if not isinstance(price,(int,float)) or price<=0: continue
            pos=first(p,"position")
            if positions and pos not in positions: continue
            if pos in excluded: continue
            rating=first(p,"rating")
            try:
                if rating is not None and int(rating)>int(max_rating): continue
            except: pass
            found.append({
                "card_id":str(first(p,"card_id","id",default="")),
                "name":first(p,"name",default="Unknown"),
                "rating":rating,"position":pos,
                "league":first(p,"league"),"club":first(p,"club"),
                "card_type":first(p,"card_type"),"price":int(price),
                "evolution":evo["name"],"page":page
            })
    return found

def run():
    provider=MarketProvider(platform=os.getenv("FC27_PLATFORM","ps"))
    if not provider.enabled: raise RuntimeError("PARSE_API_KEY missing")
    with open("data/opportunities.json",encoding="utf-8") as f: content=json.load(f)
    evos=[x for x in content if x.get("kind")=="Evolutions" and x.get("requirements")]
    fingerprint=hashlib.sha256(json.dumps(evos,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    try:
        with open("data/market.json",encoding="utf-8") as f: old=json.load(f)
    except: old={}
    if old.get("content_fingerprint")==fingerprint and old.get("opportunities"):
        print("content unchanged; keeping existing market scan"); return

    rows=[]
    for evo in evos[:6]:
        rows.extend(scan_evo(provider,evo,max_pages=2))

    # Same card can qualify for several identical Evo requirements; retain the strongest opportunity.
    dedup={}
    for x in rows:
        key=(x["card_id"],x["evolution"])
        dedup[key]=x
    rows=list(dedup.values())

    # Compare each candidate against its own qualifying pool, not against unrelated positions/Evos.
    pools={}
    for x in rows: pools.setdefault(x["evolution"],[]).append(x)

    for evo_name,pool in pools.items():
        prices=sorted(x["price"] for x in pool)
        if not prices: continue
        median=prices[len(prices)//2]
        p25=prices[max(0,int(len(prices)*0.25)-1)]
        for x in pool:
            rank=sorted(prices).index(x["price"])+1
            discount=(median-x["price"])/median if median else 0
            score=55
            score+=min(20,max(0,round(discount*40)))
            if rank<=3: score+=12
            elif rank<=7: score+=6
            # Proxy for supply scarcity: if very few qualifying cards sit near the candidate price,
            # the bottleneck is stronger. This is deliberately labelled as a proxy, not live listing count.
            near=sum(1 for p in prices if p<=x["price"]*1.15)
            if near<=2: score+=10
            elif near<=5: score+=5
            if len(prices)<=8: score+=5
            score=min(100,score)
            x["score"]=score
            x["action"]="buy" if score>=85 else ("watch" if score>=60 else "skip")
            x["net_sale"]=math.floor(x["price"]*(1-TAX))
            x["potential_vs_median"]=round(discount*100,1)
            x["qualifying_cards_found"]=len(prices)
            x["price_percentile"]=round(rank/len(prices)*100,1)
            x["supply_proxy"]=near
            x["tags"]=["EVO","ELIGIBLE"]
            if rank<=3:x["tags"].append("LOW PRICE")
            if near<=2:x["tags"].append("BOTTLENECK PROXY")
            if len(prices)<=8:x["tags"].append("LOW QUALIFIER COUNT")
            x["why"]=(f"{evo_name}: {len(prices)} kwalifikujących kart znalezionych. "
                      f"Ta karta jest #{rank} cenowo; {round(discount*100,1)}% poniżej mediany. "
                      f"W promieniu +15% ceny znaleziono {near} kart — to proxy ograniczonej podaży, nie licznik live aukcji.")

    rows.sort(key=lambda x:(x.get("score",0),x.get("potential_vs_median",0)),reverse=True)
    payload={
        "updated":datetime.now(timezone.utc).isoformat(),
        "content_fingerprint":fingerprint,
        "provider":provider.health(),
        "content_triggers":len(evos),
        "scan_pages_per_evo":2,
        "scoring_note":"Supply is a price-distribution proxy; no live auction-count claim is made.",
        "opportunities":rows[:100]
    }
    os.makedirs("data",exist_ok=True)
    with open("data/market.json","w",encoding="utf-8") as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
    print("market opportunities:",len(rows))
if __name__=="__main__": run()
