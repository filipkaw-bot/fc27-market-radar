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
        self._html_driver=None

    def _browser_html(self,url):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        if self._html_driver is None:
            opts=Options()
            opts.add_argument("--headless=new"); opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage"); opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1440,1400")
            self._html_driver=webdriver.Chrome(options=opts)
            self._html_driver.set_page_load_timeout(30)
        self._html_driver.get(url)
        time.sleep(2.0)
        return self._html_driver.page_source

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
        if len(out)<50 and self.platform=="pc":
            fallback=self._futbin_fallback()
            if fallback:
                return {"players":fallback}
        if not out:
            raise RuntimeError(f"FUT.GG/FUTBIN returned zero priced {self.platform.upper()} cards after {pages_used} page(s)")
        return {"players":out}

    def _futbin_fallback(self):
        # Last-resort PC feed. FUTBIN publishes FC27 PC prices directly in its
        # year-scoped player table. We use this only when FUT.GG's PC price index
        # is blocked/empty, and label the resulting cards explicitly as FUTBIN PC.
        from html.parser import HTMLParser
        import re

        class RowParser(HTMLParser):
            def __init__(self):
                super().__init__(); self.in_row=False; self.in_td=False; self.href=""
                self.cells=[]; self.cur=""
            def handle_starttag(self,tag,attrs):
                a=dict(attrs)
                if tag=="tr" and "player-row" in a.get("class",""):
                    self.in_row=True; self.cells=[]; self.href=""
                elif self.in_row and tag=="td": self.in_td=True; self.cur=""
                elif self.in_row and tag=="a" and "/27/player/" in a.get("href",""):
                    self.href=a.get("href","")
            def handle_data(self,data):
                if self.in_row and self.in_td: self.cur+=data
            def handle_endtag(self,tag):
                if self.in_row and tag=="td":
                    self.cells.append(" ".join(self.cur.split())); self.in_td=False
                elif self.in_row and tag=="tr":
                    self.in_row=False

        result=[]
        for page in range(1,min(PAGES_PER_RUN,20)+1):
            url=f"https://www.futbin.com/27/players?page={page}"
            req=Request(url,headers={
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
                "Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9",
                "Referer":"https://www.futbin.com/27/players"
            })
            try:
                if os.getenv("FUTBIN_BROWSER","1")=="1":
                    html=self._browser_html(url)
                else:
                    with urlopen(req,timeout=30) as r: html=r.read().decode("utf-8","ignore")
            except Exception as e:
                self.last_error=f"FUTBIN fallback failed: {e}"; break
            # Parse the rendered FUTBIN table.
            try:
                from bs4 import BeautifulSoup
                soup=BeautifulSoup(html,"html.parser")
                rows=soup.select("tr.player-row")
                if not rows:
                    rows=soup.select("tr[data-player-id], tr[class*='player-row']")
                if not rows:
                    # FUTBIN's current FC27 table does not always expose the
                    # player-row class; recover rows from player links instead.
                    seen=set()
                    for link in soup.select("a[href*='/27/player/']"):
                        row=link.find_parent("tr")
                        if row is not None and id(row) not in seen:
                            seen.add(id(row)); rows.append(row)
            except Exception as e:
                self.last_error=f"FUTBIN parser failed: {e}"
                break
            if not rows:
                # Last-resort text mirror. FUTBIN sometimes serves an anti-bot shell
                # to headless browsers; r.jina.ai can expose the same public table as
                # readable markdown without changing the data source.
                try:
                    mirror=f"https://r.jina.ai/http://www.futbin.com/27/players?page={page}"
                    mreq=Request(mirror,headers={"User-Agent":"Mozilla/5.0","Accept":"text/plain"})
                    with urlopen(mreq,timeout=30) as mr:
                        md=mr.read().decode("utf-8","ignore")
                    for line in md.splitlines():
                        if "/27/player/" not in line or "|" not in line:
                            continue
                        mm=re.search(r"/27/player/(\\d+)",line)
                        if not mm:
                            continue
                        cells=[x.strip() for x in line.strip().strip("|").split("|")]
                        if len(cells)<6:
                            continue
                        def num2(s):
                            s=re.sub(r"[^0-9KM.]", "", s.upper()).strip()
                            try:
                                if s.endswith("K"): return int(float(s[:-1])*1000)
                                if s.endswith("M"): return int(float(s[:-1])*1000000)
                                return int(float(s))
                            except: return 0
                        price=num2(cells[5])
                        if price<=0:
                            continue
                        nm=re.sub(r"\\[([^]]+)\\]\\([^)]*\\)", r"\\1", cells[0])
                        result.append({
                            "id":mm.group(1),"name":nm or "Unknown",
                            "rating":num2(cells[1]),"position":cells[2].split()[0] if len(cells)>2 else "",
                            "price":price,"price_pc_coins":price,
                            "league":"","club":"","nation":"","version":"",
                            "platform":"pc","source_market":"FUTBIN PC","trend_pc":None
                        })
                    if result:
                        continue
                except Exception as e:
                    self.last_error=f"FUTBIN browser+mirror fallback failed: {e}"
                self.last_error=f"FUTBIN returned no player rows on page {page} (HTML {len(html)} bytes)"
                break
            for row in rows:
                link=row.select_one("a[href*='/27/player/']")
                if not link: continue
                href=str(link.get("href","")); m=re.search(r"/27/player/(\d+)",href)
                if not m: continue
                cells=[c.get_text(" ",strip=True) for c in row.find_all("td")]
                if len(cells)<6: continue
                def num(s):
                    s=s.upper().replace(",","").strip()
                    try:
                        if s.endswith("K"): return int(float(s[:-1])*1000)
                        if s.endswith("M"): return int(float(s[:-1])*1000000)
                        return int(float(s))
                    except: return 0
                price=num(cells[5])
                if price<=0: continue
                result.append({
                    "id":m.group(1),"name":link.get_text(" ",strip=True) or "Unknown",
                    "rating":num(cells[1]),"position":cells[3].split()[0] if len(cells)>3 else "",
                    "price":price,"price_pc_coins":price,
                    "league":"","club":"","nation":"","version":"",
                    "platform":"pc","source_market":"FUTBIN PC","trend_pc":None
                })
        if result:
            self.last_error="FUT.GG PC price index blocked; using FUTBIN PC fallback"
        return result

    def prices(self,card_id):
        raise RuntimeError("Radar uses FUT.GG catalogue prices.")

    def health(self):
        return {"enabled":True,"provider":"FUT.GG","platform":self.platform,"market":self.platform.upper(),
                "endpoint":f"https://www.fut.gg/api/fut/players/v2/{GAME}/","pages_per_run":PAGES_PER_RUN,
                "mode":"live PC catalogue" if self.platform=="pc" else "live PS catalogue","error":self.last_error}
