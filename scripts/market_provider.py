import os,re,time,random
from html.parser import HTMLParser
from urllib.parse import quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE_URL=os.getenv("FUTBIN_BASE_URL","https://www.futbin.com").rstrip("/")
MAX_PAGES=int(os.getenv("FUTBIN_MAX_PAGES","20"))
DELAY=float(os.getenv("FUTBIN_PAGE_DELAY","0.8"))
READER_PROXY=os.getenv("FUTBIN_READER_PROXY","https://r.jina.ai/").rstrip("/") + "/"

class _RowParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[]; self.in_row=False; self.in_td=False; self.text=[]; self.cells=[]; self.href=""
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="tr":
            self.in_row=True; self.cells=[]
        elif self.in_row and tag=="td":
            self.in_td=True; self.text=[]; self.href=""
        elif self.in_row and self.in_td and tag=="a":
            href=a.get("href","")
            if "/player/" in href:self.href=href
    def handle_data(self,data):
        if self.in_row and self.in_td:self.text.append(data)
    def handle_endtag(self,tag):
        if not self.in_row:return
        if tag=="td":
            self.cells.append((" ".join(x.strip() for x in self.text if x.strip()),self.href)); self.in_td=False
        elif tag=="tr":
            if any("/player/" in c[1] for c in self.cells):self.rows.append(self.cells)
            self.in_row=False

def _price(s):
    s=(s or "").strip().replace(",","").replace(" ","")
    m=re.search(r"(\d+(?:\.\d+)?)\s*([KM])?",s,re.I)
    if not m:return 0
    n=float(m.group(1)); unit=(m.group(2) or "").upper()
    if unit=="K":n*=1000
    elif unit=="M":n*=1000000
    return int(round(n))

def _id(href):
    m=re.search(r"/player/(\d+)",href or "")
    return m.group(1) if m else ""

def _name(href):
    slug=(href or "").rstrip("/").rsplit("/",1)[-1]
    return slug.replace("-"," ").title() if slug and slug!="player" else "Unknown"

def _markdown_rows(text):
    rows=[]
    for line in text.splitlines():
        if "/player/" not in line or "|" not in line:continue
        parts=[x.strip() for x in line.strip().strip("|").split("|")]
        href_match=re.search(r"https?://[^ )]+/27/player/[^ )]+|/27/player/[^ )]+",line)
        if not href_match:continue
        href=href_match.group(0)
        if href.startswith("/"):href=BASE_URL+href
        rows.append([(re.sub(r"\[([^]]+)\]\([^)]*\)",r"\1",x),href if "/player/" in x else "") for x in parts])
    return rows

class MarketProvider:
    def __init__(self,platform="ps"):
        self.platform=platform; self.enabled=True; self.last_source=""

    def _get_page(self,page):
        url=f"{BASE_URL}/27/players"
        if page>1:url+=f"?page={page}"
        headers={
            "User-Agent":random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.6 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
            ]),
            "Accept":"text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language":"en-US,en;q=0.9",
            "Referer":f"{BASE_URL}/",
            "Origin":BASE_URL,
        }
        try:
            req=Request(url,headers=headers)
            with urlopen(req,timeout=45) as r:
                self.last_source="direct"
                return r.read().decode("utf-8","ignore")
        except (HTTPError,URLError,TimeoutError) as e:
            code=getattr(e,"code",None)
            if code not in (403,429):raise
            proxy_url=READER_PROXY+url
            req=Request(proxy_url,headers={"User-Agent":headers["User-Agent"],"Accept":"text/plain,text/html;q=0.9,*/*;q=0.8"})
            with urlopen(req,timeout=60) as r:
                self.last_source="reader_proxy"
                return r.read().decode("utf-8","ignore")

    def players(self,**filters):
        min_rating=int(filters.get("min_rating",40) or 40)
        max_rating=int(filters.get("max_rating",99) or 99)
        wanted=set((filters.get("position") or "").split(",")) if filters.get("position") else set()
        out=[]
        for page in range(1,MAX_PAGES+1):
            try: text=self._get_page(page)
            except (HTTPError,URLError,TimeoutError) as e:
                print(f"FUTBIN page {page} failed: {e}"); break
            p=_RowParser(); p.feed(text)
            rows=p.rows or _markdown_rows(text)
            if not rows:
                print(f"FUTBIN page {page}: no player rows; source={self.last_source}; bytes={len(text)}")
                print("FUTBIN sample:", repr(text[:1200]))
                break
            page_ratings=[]
            for cells in rows:
                texts=[c[0] for c in cells]
                href=next((c[1] for c in cells if "/player/" in c[1]),"")
                cid=_id(href)
                if not cid:continue
                rating=0
                for t in texts[:3]:
                    m=re.fullmatch(r"\d{2}",t.strip())
                    if m:rating=int(t);break
                position=""
                for t in texts[:5]:
                    m=re.search(r"\b(GK|LB|CB|RB|CDM|CM|CAM|RM|LM|RW|LW|ST)\b",t)
                    if m:position=m.group(1);break
                price_ps=0
                for t in texts[3:7]:
                    v=_price(t)
                    if v>=200:price_ps=v;break
                if not rating:continue
                page_ratings.append(rating)
                if rating<min_rating or rating>max_rating:continue
                if wanted and position not in wanted:continue
                out.append({"id":cid,"name":_name(href),"rating":rating,"position":position,"price_ps_coins":price_ps,"price":price_ps})
            print(f"FUTBIN page {page}: {len(rows)} rows, kept {len(out)}, source={self.last_source}")
            if page_ratings and min(page_ratings)<min_rating:break
            if page<MAX_PAGES:time.sleep(DELAY)
        return {"players":out}

    def prices(self,card_id):
        raise RuntimeError("Direct FUTBIN provider uses the FC27 player table; per-card calls are not needed.")

    def health(self):
        return {"enabled":True,"provider":"FUTBIN FC27 web player table","platform":self.platform,"endpoint":"https://www.futbin.com/27/players","reader_proxy":bool(READER_PROXY)}
