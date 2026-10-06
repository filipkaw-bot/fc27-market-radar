import os,time,json
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE="https://www.fut.gg/api/fut"
GAME="27"
PAGES_PER_RUN=max(1,int(os.getenv("FUTGG_PAGES_PER_RUN","20")))
DELAY=float(os.getenv("FUTGG_PAGE_DELAY","0.35"))

class MarketProvider:
    def __init__(self,platform="pc"):
        self.platform=(platform or "pc").lower()
        if self.platform not in ("pc","ps"): self.platform="pc"
        self.enabled=True
        self.last_error=None

    def _get(self,page):
        url=f"{BASE}/players/v2/{GAME}/?page={page}&platform={self.platform}"
        req=Request(url,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
            "Accept":"application/json,text/plain,*/*","Accept-Language":"en-US,en;q=0.9",
            "Referer":"https://www.fut.gg/players/","Origin":"https://www.fut.gg"
        })
        try:
            with urlopen(req,timeout=30) as r:
                return json.loads(r.read().decode("utf-8","ignore"))
        except (HTTPError,URLError,TimeoutError,ValueError) as e:
            self.last_error=f"page {page}: {e}"
            raise RuntimeError(self.last_error) from e

    @staticmethod
    def _payload(data):
        if not isinstance(data,dict): return {}
        inner=data.get("data")
        return inner if isinstance(inner,dict) else data

    @staticmethod
    def _label(v):
        if isinstance(v,dict):
            return v.get("name") or v.get("label") or v.get("shortName") or v.get("code")
        return v

    def players(self,**filters):
        out=[]; seen=set(); pages_used=0; advertised_platform=None
        for page in range(1,PAGES_PER_RUN+1):
            data=self._get(page)
            pages_used=page
            payload=self._payload(data)
            advertised_platform=str(payload.get("platform") or data.get("platform") or "").lower()
            rows=payload.get("players") or []
            if not isinstance(rows,list):
                raise RuntimeError(f"Unexpected FUT.GG schema on page {page}: players is not a list")
            if not rows: break
            for p in rows:
                if not isinstance(p,dict): continue
                cid=str(p.get("card_id") or p.get("eaId") or p.get("cardId") or p.get("id") or "")
                if not cid or cid in seen: continue
                seen.add(cid)
                price=p.get("price")
                try: price=int(float(price))
                except (TypeError,ValueError): continue
                if price<=0: continue
                rating=p.get("rating")
                try: rating=int(rating) if rating is not None else None
                except (TypeError,ValueError): rating=None
                pos=p.get("position")
                if isinstance(pos,dict): pos=pos.get("shortName") or pos.get("name") or pos.get("code")
                out.append({
                    "id":cid,"name":p.get("name") or p.get("commonName") or p.get("lastName") or "Unknown",
                    "rating":rating,"position":pos,"league":self._label(p.get("league")),
                    "club":self._label(p.get("club")),"nation":self._label(p.get("nation")),
                    "version":p.get("card_type") or p.get("rarityName") or p.get("cardType") or p.get("rarity"),
                    "price_pc_coins":price,"price":price,
                    "trend_pc":p.get("priceTrend") or p.get("price_trend"),
                    "platform":advertised_platform or self.platform
                })
            next_page=payload.get("next_page")
            if next_page is None or page>=PAGES_PER_RUN: break
            time.sleep(DELAY)
        if advertised_platform and advertised_platform!=self.platform:
            raise RuntimeError(f"FUT.GG returned platform={advertised_platform}, expected {self.platform}")
        if not out:
            raise RuntimeError(f"FUT.GG returned zero priced {self.platform.upper()} cards after {pages_used} page(s)")
        return {"players":out}

    def prices(self,card_id):
        raise RuntimeError("Radar uses FUT.GG catalogue prices.")

    def health(self):
        return {"enabled":True,"provider":"FUT.GG","platform":self.platform,"market":self.platform.upper(),
                "endpoint":f"https://www.fut.gg/api/fut/players/v2/{GAME}/","pages_per_run":PAGES_PER_RUN,
                "mode":"live PC catalogue" if self.platform=="pc" else "live PS catalogue","error":self.last_error}
