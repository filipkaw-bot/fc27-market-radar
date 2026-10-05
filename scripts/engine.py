import json,os,math
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
def run():
    provider=MarketProvider(platform=os.getenv("FC27_PLATFORM","ps"))
    if not provider.enabled: raise RuntimeError("PARSE_API_KEY missing")
    with open("data/opportunities.json",encoding="utf-8") as f: content=json.load(f)
    evos=[x for x in content if x.get("kind")=="Evolutions" and x.get("requirements")]
    rows=[]
    for evo in evos[:4]:
        req=evo["requirements"]; max_rating=req.get("overall_max"); positions=req.get("positions") or []
        if not max_rating or not positions: continue
        for pos in positions[:3]:
            try: data=provider.players(position=pos,max_rating=max_rating,sort_by="price",sort_order="asc",page=1)
            except Exception as e:
                print("query failed",e); continue
            for idx,p in enumerate(flatten(data)[:20]):
                price=first(p,"price")
                if not isinstance(price,(int,float)) or price<=0: continue
                rating=first(p,"rating")
                if rating and int(rating)>int(max_rating): continue
                rows.append({"card_id":str(first(p,"card_id","id")),"name":first(p,"name",default="Unknown"),"rating":rating,"position":first(p,"position"),"league":first(p,"league"),"club":first(p,"club"),"card_type":first(p,"card_type"),"price":int(price),"evolution":evo["name"],"position_query":pos,"rank_in_query":idx+1})
    uniq={x["card_id"]:x for x in rows}; rows=list(uniq.values())
    prices=sorted(x["price"] for x in rows); median=prices[len(prices)//2] if prices else None
    for x in rows:
        rank=sorted(prices).index(x["price"])+1
        score=63
        if median and x["price"]<median*.75: score+=18
        elif median and x["price"]<median*.9: score+=10
        if rank<=3: score+=12
        x["score"]=min(100,score); x["action"]="buy" if score>=85 else "watch"
        x["net_sale"]=math.floor(x["price"]*(1-TAX))
        x["potential_vs_median"]=None if not median else round((median-x["price"])/median*100,1)
        x["tags"]=["EVO","ELIGIBLE"]+([ "LOW PRICE" ] if rank<=3 else [])
        x["why"]=f"Spełnia wymagania {x['evolution']}; cena {x['price']:,}. Pozycja {rank} wśród znalezionych kwalifikujących kart."
    os.makedirs("data",exist_ok=True)
    with open("data/market.json","w",encoding="utf-8") as f:
        json.dump({"updated":datetime.now(timezone.utc).isoformat(),"provider":provider.health(),"content_triggers":len(evos),"opportunities":sorted(rows,key=lambda x:x["score"],reverse=True)[:100]},f,ensure_ascii=False,indent=2)
    print("targeted opportunities:",len(rows))
if __name__=="__main__": run()
