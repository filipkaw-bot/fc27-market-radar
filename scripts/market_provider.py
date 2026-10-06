import os,time,json
from urllib.request import Request,urlopen

BASE="https://www.fut.gg/api/fut"
GAME="27"
PAGES_PER_RUN=int(os.getenv("FUTGG_PAGES_PER_RUN","20"))
DELAY=float(os.getenv("FUTGG_PAGE_DELAY","0.35"))

class MarketProvider:
    def __init__(self,platform="pc"):
        self.platform=(platform or "pc").lower()
        if self.platform not in ("pc","ps"): self.platform="pc"
        self.enabled=True

    def _get(self,page):
        url=f"{BASE}/players/v2/{GAME}/?page={page}&platform={self.platform}"
        req=Request(url,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
            "Accept":"application/json,text/plain,*/*","Accept-Language":"en-US,en;q=0.9",
            "Referer":"https://www.fut.gg/players/"
        })
        with urlopen(req,timeout=30) as r:
            return json.loads(r.read().decode("utf-8","ignore"))

    def players(self,**filters):
        out=[]; seen=set()
        for page in range(1,PAGES_PER_RUN+1):
            try: data=self._get(page)
            except Exception as e:
                print(f"FUT.GG PC page {page} failed: {e}"); break
            rows=data.get("players",[]) if isinstance(data,dict) else []
            if not rows: break
            for p in rows:
                cid=str(p.get("eaId") or p.get("card_id") or p.get("id") or "")
                if not cid or cid in seen: continue
                seen.add(cid)
                price=p.get("price")
                try: price=int(float(price))
                except (TypeError,ValueError): continue
                if price<200: continue
                rating=p.get("rating")
                try: rating=int(rating) if rating is not None else None
                except (TypeError,ValueError): rating=None
                pos=p.get("position")
                if isinstance(pos,dict): pos=pos.get("shortName") or pos.get("name") or pos.get("code")
                def label(v):
                    return v.get("name") if isinstance(v,dict) else v
                out.append({
                    "id":cid,"name":p.get("commonName") or p.get("name") or p.get("lastName") or "Unknown",
                    "rating":rating,"position":pos,"league":label(p.get("league")),
                    "club":label(p.get("club")),"nation":label(p.get("nation")),
                    "version":p.get("rarityName") or p.get("cardType") or p.get("rarity"),
                    "price_pc_coins":price,"price":price,
                    "trend_pc":p.get("priceTrend") or p.get("price_trend")
                })
            if page<PAGES_PER_RUN: time.sleep(DELAY)
        return {"players":out}

    def prices(self,card_id):
        raise RuntimeError("Radar uses FUT.GG PC catalogue prices.")

    def health(self):
        return {"enabled":True,"provider":"FUT.GG","platform":"pc","market":"PC",
                "endpoint":"https://www.fut.gg/api/fut/players/v2/27/",
                "pages_per_run":PAGES_PER_RUN,"mode":"live PC catalogue"}
