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
        self._driver=None

    def _browser_get(self,url):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts=Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1440,1000")
        if self._driver is None:
            self._driver=webdriver.Chrome(options=opts)
            self._driver.set_script_timeout(30)
            self._driver.get("https://www.fut.gg/players/")
        return self._driver.execute_async_script("""
            const url=arguments[0], done=arguments[arguments.length-1];
            fetch(url,{credentials:'include',headers:{'Accept':'application/json'}})
              .then(r=>r.text().then(t=>done({status:r.status,text:t})))
              .catch(e=>done({status:0,text:String(e)}));
        """,url)

    def _get(self,page=None,ids=None,params=None):
        if ids:
            query="ids="+",".join(ids)+"&platform="+self.platform
        else:
            q={"page":str(page),"platform":self.platform}
            if params:
                q.update({k:str(v) for k,v in params.items() if v is not None})
            query="&".join(k+"="+v for k,v in q.items())
        url=f"{BASE}/players/v2/{GAME}/?{query}"
        req=Request(url,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
            "Accept":"application/json,text/plain,*/*","Accept-Language":"en-US,en;q=0.9",
            "Referer":"https://www.fut.gg/players/","Origin":"https://www.fut.gg"
        })
        try:
            if os.getenv("FUTGG_BROWSER","1")=="1":
                browser=self._browser_get(url)
                if browser.get("status")!=200:
                    raise RuntimeError("browser HTTP "+str(browser.get("status")))
                return json.loads(browser.get("text",""))
            with urlopen(req,timeout=30) as r:
                return json.loads(r.read().decode("utf-8","ignore"))
        except (HTTPError,URLError,TimeoutError,ValueError,RuntimeError) as e:
            self.last_error=f"request failed: {e}"
            raise RuntimeError(self.last_error) from e

    def _get_prices(self,ids):
        query="ids="+",".join(ids)+"&platform="+self.platform
        url=f"{BASE}/player-prices/{GAME}/?{query}"
        req=Request(url,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
            "Accept":"application/json,text/plain,*/*","Accept-Language":"en-US,en;q=0.9",
            "Referer":"https://www.fut.gg/players/","Origin":"https://www.fut.gg"
        })
        try:
            if os.getenv("FUTGG_BROWSER","1")=="1":
                browser=self._browser_get(url)
                if browser.get("status")!=200:
                    raise RuntimeError("browser HTTP "+str(browser.get("status")))
                return json.loads(browser.get("text",""))
            with urlopen(req,timeout=30) as r:
                return json.loads(r.read().decode("utf-8","ignore"))
        except Exception as e:
            self.last_error=f"price endpoint failed: {e}"
            return None

    @staticmethod
    def _payload(data):
        if not isinstance(data,dict): return {}
        inner=data.get("data")
        if isinstance(inner,dict):
            return inner
        if isinstance(inner,list):
            # Current FUT.GG FC27 response shape:
            # {currentPage, data:[cards], next, total}
            return {"players":inner,"next_page":data.get("next"),"platform":data.get("platform")}
        return data

    @staticmethod
    def _label(v):
        if isinstance(v,dict):
            return v.get("name") or v.get("label") or v.get("shortName") or v.get("code")
        return v

    @staticmethod
    def _price(p):
        raw=p.get("price")
        if isinstance(raw,dict):
            for key in ("pc","PC","price_pc","pc_price","current","value"):
                if raw.get(key) is not None: raw=raw.get(key); break
        if raw is None:
            for key in ("price_pc","pc_price","pricePc","pcPrice"):
                if p.get(key) is not None: raw=p.get(key); break
        try: return int(float(raw))
        except (TypeError,ValueError): return 0

    def _normalize(self,rows,advertised_platform):
        out=[]
        for p in rows:
            if not isinstance(p,dict): continue
            cid=str(p.get("card_id") or p.get("eaId") or p.get("cardId") or p.get("id") or "")
            if not cid: continue
            pos=p.get("position")
            if isinstance(pos,dict): pos=pos.get("shortName") or pos.get("name") or pos.get("code")
            price=self._price(p)
            rating=p.get("rating")
            try: rating=int(rating) if rating is not None else None
            except (TypeError,ValueError): rating=None
            out.append({
                "id":cid,"name":p.get("name") or p.get("commonName") or p.get("lastName") or "Unknown",
                "rating":rating,"position":pos,"league":self._label(p.get("league")),
                "club":self._label(p.get("club")),"nation":self._label(p.get("nation")),
                "version":p.get("card_type") or p.get("rarityName") or p.get("cardType") or p.get("rarity"),
                "price_pc_coins":price,"price":price,
                "trend_pc":p.get("priceTrend") or p.get("price_trend"),
                "platform":advertised_platform or self.platform
            })
        return out

    def players(self,**filters):
        out=[]; seen=set(); pages_used=0; advertised_platform=None
        for page in range(1,PAGES_PER_RUN+1):
            data=self._get(page=page,params={})
            pages_used=page
            payload=self._payload(data)
            advertised_platform=str(payload.get("platform") or data.get("platform") or "").lower()
            rows=payload.get("players") or []
            if not isinstance(rows,list): raise RuntimeError("Unexpected FUT.GG schema: players is not a list")
            if not rows: break

            normalized=self._normalize(rows,advertised_platform)
            # The catalogue currently exposes many cards with price=0. Refresh every
            # catalogue page through FUT.GG's direct player-prices index, in batches
            # of 30. This recovers PC prices for cards whose catalogue snapshot is blank.
            ids=[p["id"] for p in normalized if p["id"]]
            price_by_id={}
            if ids:
                priced=self._get_prices(ids)
                raw=(priced or {}).get("data") if isinstance(priced,dict) else None
                if isinstance(raw,list):
                    for item in raw:
                        if not isinstance(item,dict): continue
                        cid=str(item.get("id") or item.get("eaId") or item.get("card_id") or item.get("item_id") or "")
                        val=item.get("price")
                        if isinstance(val,dict):
                            val=val.get("pc") or val.get("PC") or val.get("current") or val.get("value")
                        if val is None:
                            val=item.get("pc") or item.get("pc_price") or item.get("price_pc")
                        try: val=int(float(val))
                        except (TypeError,ValueError): continue
                        if cid and val>0: price_by_id[cid]=val
            for p in normalized:
                p["price"]=price_by_id.get(p["id"],p["price"])
                p["price_pc_coins"]=p["price"]
                if p["id"] in seen or p["price"]<=0: continue
                seen.add(p["id"]); out.append(p)

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
