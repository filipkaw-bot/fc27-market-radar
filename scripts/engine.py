import json,os,math,hashlib
from datetime import datetime,timezone
from market_provider import MarketProvider

TAX=0.05

def flatten(data):
    p=data.get("players",[]) if isinstance(data,dict) else []
    return p if isinstance(p,list) else []

def qualifies(p,req):
    r=p.get("rating")
    if req.get("overall_min") is not None and (r is None or r<int(req["overall_min"])): return False
    if req.get("overall_max") is not None and (r is None or r>int(req["overall_max"])): return False
    positions=set(req.get("positions") or [])
    excluded=set(req.get("excluded_positions") or [])
    pos=p.get("position")
    if positions and pos not in positions: return False
    if pos in excluded: return False
    return True

def score_pool(pool,evo):
    if not pool: return []
    prices=sorted(x["price"] for x in pool)
    median=prices[len(prices)//2]
    out=[]
    for x0 in pool:
        x=dict(x0)
        rank=1+sum(p<x["price"] for p in prices)
        ties=sum(p==x["price"] for p in prices)
        near=sum(p<=x["price"]*1.15 for p in prices)
        discount=(median-x["price"])/median if median else 0
        score=35
        if ties<=1: score+=12
        elif ties<=3: score+=8
        elif ties<=7: score+=4
        if rank<=3: score+=12
        elif rank<=7: score+=6
        if near<=1: score+=20
        elif near<=3: score+=15
        elif near<=5: score+=10
        elif near<=10: score+=5
        if ties<=3: score+=min(10,max(0,round(discount*15)))
        elif ties<=10: score+=min(5,max(0,round(discount*8)))
        if len(prices)<=8: score+=5

        momentum=None
        trend=x.get("trend_pc")
        if isinstance(trend,dict): momentum=trend.get("momentum_pct")
        try: momentum=float(momentum) if momentum is not None else None
        except (TypeError,ValueError): momentum=None
        if momentum is not None and momentum>10: score+=5
        score=min(100,score)

        target=math.floor(median*0.98)
        max_buy=math.floor((target*(1-TAX))/1.10)
        action="buy" if score>=85 and x["price"]<=max_buy else "watch" if score>=60 else "skip"
        x.update({
            "card_id":x["id"],"evolution":evo,"score":score,"action":action,
            "net_sale":math.floor(x["price"]*(1-TAX)),"target_sell":target,"max_buy_price":max_buy,
            "potential_vs_median":round(discount*100,1),
            "qualifying_cards_found":len(prices),"price_rank":rank,"price_tie_count":ties,
            "price_percentile":round(rank/len(prices)*100,1),"supply_proxy":near,
            "tags":["EVO","PC"],"source":("FUTBIN PC" if x.get("source_market")=="FUTBIN PC" else "FUT.GG PC"),
            "updated":datetime.now(timezone.utc).isoformat(),
            "why":f"{evo}: {len(prices)} kandydatów po OVR/pozycji w katalogu PC. Cena {x['price']} coins; {ties} po tej samej cenie, {near} w +15%; pozycja #{rank}. {round(discount*100,1)}% poniżej mediany."
        })
        if rank<=3: x["tags"].append("LOW PRICE")
        if ties<=3: x["tags"].append("LOW SAME-PRICE SUPPLY")
        if near<=3: x["tags"].append("BOTTLENECK PROXY")
        if len(prices)<=8: x["tags"].append("LOW CANDIDATE COUNT")
        if momentum is not None and momentum>10: x["tags"].append("UPTREND")
        out.append(x)
    return out

def run():
    provider=MarketProvider(platform=os.getenv("FC27_PLATFORM","pc"))
    with open("data/opportunities.json",encoding="utf-8") as f: content=json.load(f)
    evos=[x for x in content if x.get("kind")=="Evolutions" and x.get("requirements")]
    fingerprint=hashlib.sha256(json.dumps(evos,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    snapshot=flatten(provider.players())
    all_ids={p["id"] for p in snapshot}
    print("FUT.GG PC market rows:",len(snapshot))
    rows=[]
    for evo in evos:
        req=evo["requirements"]
        pool=[dict(p) for p in snapshot if qualifies(p,req)]
        print("FUT.GG PC candidates",evo["name"],len(pool))
        rows.extend(score_pool(pool,evo["name"]))

    dedup={(x["card_id"],x["evolution"]):x for x in rows}
    rows=list(dedup.values())
    rows.sort(key=lambda x:(x.get("score",0),x.get("potential_vs_median",0)),reverse=True)

    payload={
        "updated":datetime.now(timezone.utc).isoformat(),
        "content_fingerprint":fingerprint,
        "provider":provider.health(),
        "content_triggers":len(evos),
        "market_rows_scanned":len(all_ids),
        "platform":"PC","source":("FUTBIN PC fallback" if any(x.get("source_market")=="FUTBIN PC" for x in snapshot) else "FUT.GG"),"status":"ok",
        "scoring_note":("PC market prices from FUTBIN PC fallback because FUT.GG PC price feed was blocked. No PlayStation prices are mixed in." if any(x.get("source_market")=="FUTBIN PC" for x in snapshot) else "PC market prices come from FUT.GG FC27. No PlayStation prices are mixed in."),
        "opportunities":rows[:3]
    }
    os.makedirs("data",exist_ok=True)
    with open("data/market.json","w",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,indent=2)
    print("published TOP 3:",len(rows[:3]))

if __name__=="__main__":
    run()
