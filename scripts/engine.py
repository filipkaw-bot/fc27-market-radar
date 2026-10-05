import json,os,math
from datetime import datetime,timezone
from market_provider import MarketProvider

TAX=0.05

def first(obj,*keys,default=None):
    for k in keys:
        if isinstance(obj,dict) and obj.get(k) is not None:return obj[k]
    return default

def price_snapshot(raw):
    if not isinstance(raw,dict): return {}
    p=first(raw,"price_trend","priceTrend",default={}) or {}
    return {
        "bin":first(p,"lowest_bin","lowestBin","current_lowest_bin",default=first(raw,"lowest_bin","lowestBin")),
        "avg":first(p,"average","avg"),
        "yesterday":first(p,"yesterday_average_bin","yesterdayAverageBin"),
        "change":first(p,"change_vs_yesterday_pct","changeVsYesterdayPct","momentum_pct"),
        "momentum":first(p,"momentum_pct","momentumPct"),
        "updated":first(raw,"updated_at","updatedAt"),
        "extinct":bool(first(raw,"extinct","is_extinct",default=False)),
        "auctions":first(raw,"live_auctions","liveAuctions",default=[]) or []
    }

def net_sale(price):
    return math.floor(float(price)*0.95)

def opportunity(card, snap, trigger="market"):
    price=snap.get("bin")
    if not price:return None
    change=float(snap.get("change") or 0)
    extinct=snap.get("extinct",False)
    auctions=snap.get("auctions") or []
    score=35
    tags=["MARKET"]
    if change>=10:score+=20;tags.append("MOMENTUM")
    elif change>=5:score+=10;tags.append("RISING")
    if extinct:score+=20;tags.append("LOW SUPPLY")
    if not auctions:score+=8;tags.append("THIN MARKET")
    if trigger!="market":score+=10;tags.append("CONTENT TRIGGER")
    score=min(100,score)
    action="buy" if score>=85 else "watch" if score>=60 else "skip"
    return {
        "card_id":first(card,"card_id","id"),
        "name":first(card,"name",default="Unknown"),
        "rating":first(card,"rating"),
        "position":first(card,"position"),
        "league":first(card,"league"),
        "club":first(card,"club"),
        "price":price,
        "net_sale":net_sale(price),
        "change":change,
        "extinct":extinct,
        "auction_count":len(auctions),
        "score":score,
        "action":action,
        "tags":tags,
        "why":"Wzrost ceny/podaży jest sygnałem rynku; radar nie kupuje automatycznie.",
        "updated":snap.get("updated") or datetime.now(timezone.utc).isoformat()
    }

def run():
    provider=MarketProvider(platform=os.getenv("FC27_PLATFORM","ps"))
    if not provider.enabled:
        raise RuntimeError("PARSE_API_KEY missing")
    rows=[]
    # Broad but credit-aware scan: cheap cards first, then a small sample for price details.
    for page in range(1,4):
        data=provider.players(page=page,sort_by="price",sort_order="asc")
        players=first(data,"players","items","data",default=[]) or []
        if isinstance(players,dict):players=players.get("items",[])
        for card in players:
            cid=first(card,"card_id","id")
            if not cid:continue
            try:
                snap=price_snapshot(provider.prices(cid))
                item=opportunity(card,snap)
                if item and item["action"]!="skip":rows.append(item)
            except Exception as e:
                print("price failed",cid,e)
    rows.sort(key=lambda x:x["score"],reverse=True)
    os.makedirs("data",exist_ok=True)
    with open("data/market.json","w",encoding="utf-8") as f:
        json.dump({"updated":datetime.now(timezone.utc).isoformat(),"provider":provider.health(),"opportunities":rows[:100]},f,ensure_ascii=False,indent=2)
    return rows

if __name__=="__main__":
    print("market opportunities:",len(run()))
