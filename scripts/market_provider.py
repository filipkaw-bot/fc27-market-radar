import os,re,time
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE_URL=os.getenv("FUTBIN_BASE_URL","https://www.futbin.com").rstrip("/")
MAX_PAGES=int(os.getenv("FUTBIN_MAX_PAGES","20"))
DELAY=float(os.getenv("FUTBIN_PAGE_DELAY","0.8"))

class _RowParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[]
        self.in_row=False
        self.in_td=False
        self.text=[]
        self.cells=[]
        self.href=""
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="tr" and "player-row" in a.get("class",""):
            self.in_row=True
            self.cells=[]
        elif self.in_row and tag=="td":
            self.in_td=True
            self.text=[]
            self.href=""
        elif self.in_row and self.in_td and tag=="a":
            self.href=a.get("href","")
    def handle_data(self,data):
        if self.in_row and self.in_td:
            self.text.append(data)
    def handle_endtag(self,tag):
        if not self.in_row:return
        if tag=="td":
            self.cells.append((" ".join(x.strip() for x in self.text if x.strip()),self.href))
            self.in_td=False
        elif tag=="tr":
            if self.cells:self.rows.append(self.cells)
            self.in_row=False

def _num(s):
    m=re.search(r"\d[\d,.]*",s or "")
    if not m:return 0
    try:return int(float(m.group(0).replace(",","").replace(".","")))
    except ValueError:return 0

def _price(s):
    s=(s or "").strip().replace("K","000").replace("k","000")
    if "M" in s.upper():
        s=s.upper().replace("M","000000")
    return _num(s)

def _id(href):
    m=re.search(r"/player/(\d+)",href or "")
    return m.group(1) if m else ""

def _name(href):
    slug=(href or "").rstrip("/").rsplit("/",1)[-1]
    return slug.replace("-"," ").title() if slug and slug!="player" else "Unknown"

class MarketProvider:
    def __init__(self,platform="ps"):
        self.platform=platform
        self.enabled=True

    def _get_page(self,page):
        url=f"{BASE_URL}/27/players"
        if page>1:url+=f"?page={page}"
        req=Request(url,headers={
            "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/136 Safari/537.36",
            "Accept":"text/html,application/xhtml+xml",
            "Accept-Language":"en-US,en;q=0.9",
            "Referer":f"{BASE_URL}/27/players"
        })
        with urlopen(req,timeout=45) as r:
            return r.read().decode("utf-8","ignore")

    def players(self,**filters):
        min_rating=int(filters.get("min_rating",40) or 40)
        max_rating=int(filters.get("max_rating",99) or 99)
        wanted=set((filters.get("position") or "").split(",")) if filters.get("position") else set()
        out=[]
        for page in range(1,MAX_PAGES+1):
            try:
                html=self._get_page(page)
            except (HTTPError,URLError,TimeoutError) as e:
                print(f"FUTBIN page {page} failed: {e}")
                break
            p=_RowParser()
            p.feed(html)
            if not p.rows:
                print(f"FUTBIN page {page}: no player rows")
                break
            page_ratings=[]
            for cells in p.rows:
                texts=[c[0] for c in cells]
                rating=_num(texts[1]) if len(texts)>1 else 0
                position=texts[3].split()[0] if len(texts)>3 else ""
                price_ps=_price(texts[4]) if len(texts)>4 else 0
                href=next((c[1] for c in cells if "/player/" in c[1]),"")
                cid=_id(href)
                if not cid or not rating:continue
                page_ratings.append(rating)
                if rating<min_rating or rating>max_rating:continue
                if wanted and position not in wanted:continue
                out.append({
                    "id":cid,
                    "name":_name(href),
                    "rating":rating,
                    "position":position,
                    "price_ps_coins":price_ps,
                    "price":price_ps
                })
            print(f"FUTBIN page {page}: {len(p.rows)} rows, kept {len(out)}")
            if page_ratings and min(page_ratings)<min_rating:
                break
            if page<MAX_PAGES:
                time.sleep(DELAY)
        return {"players":out}

    def prices(self,card_id):
        raise RuntimeError("Direct FUTBIN provider uses the live FC27 players table; per-card calls are not needed.")

    def health(self):
        return {
            "enabled":True,
            "provider":"FUTBIN FC27 web player table",
            "platform":self.platform,
            "endpoint":"https://www.futbin.com/27/players"
        }
