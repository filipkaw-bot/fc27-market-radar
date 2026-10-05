import os,re,time,random
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE_URL=os.getenv("FUTFLIPPER_BASE_URL","https://futflipper.com").rstrip("/")
MAX_PAGES=int(os.getenv("FUTFLIPPER_MAX_PAGES","20"))
DELAY=float(os.getenv("FUTFLIPPER_PAGE_DELAY","0.4"))

def _price(s):
    s=(s or "").replace(",","").replace(" ","")
    m=re.search(r"(\d+(?:\.\d+)?)([KM])?",s,re.I)
    if not m:return 0
    n=float(m.group(1)); u=(m.group(2) or "").upper()
    return int(n*(1000 if u=="K" else 1000000 if u=="M" else 1))

def _id(href):
    m=re.search(r"/players/(\d+)",href or "")
    return m.group(1) if m else ""

class _CardParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards=[]; self.href=None; self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag!="a":return
        a=dict(attrs); h=a.get("href","")
        if "/players/" in h:
            self.href=h; self.text=[]
    def handle_data(self,data):
        if self.href:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            t=" ".join(x.strip() for x in self.text if x.strip())
            if t:self.cards.append((self.href,t))
            self.href=None; self.text=[]

def _parse_card(href,text):
    cid=_id(href)
    if not cid:return None
    m=re.search(r"^(\d{2})\s*([A-Z]{2,4})\b\s*(.*)$",text)
    if not m:return None
    rating=int(m.group(1)); position=m.group(2)
    rest=m.group(3).strip()
    # Card listings end with current price and optional percentage trend.
    pm=re.search(r"([0-9][0-9.,]*\s*[KM]?)\s*([+-][0-9]+(?:\.[0-9]+)?%)?$",rest)
    if not pm:return None
    price=_price(pm.group(1))
    trend=None
    if pm.group(2):
        try:trend=float(pm.group(2).replace("%",""))
        except ValueError:trend=None
    body=rest[:pm.start()].strip()
    # Remove common stat block: six consecutive XX values before version.
    stat=re.search(r"(?:\s+\d{2}){5,7}\s+(Icon|Hero|Gold|Silver|Bronze|Team of the Week|Destined for Glory|Normal)\b",body)
    if stat:
        body=body[:stat.start()].strip()+" "+stat.group(1)
    version=""
    versions=["Destined for Glory","Team of the Week","Holographic","Icon","Hero","Gold","Silver","Bronze","Normal"]
    for v in versions:
        if body.endswith(v):
            version=v; body=body[:-len(v)].strip(); break
    # If stats are still present, take name as the first sensible token sequence.
    name=body
    # Remove leading face stats if the card text begins with them after name is already known.
    name=re.sub(r"\s+\d{2}(?:\s+\d{2}){5,7}\s*$","",name).strip()
    return {"id":cid,"name":name or "Unknown","rating":rating,"position":position,"price_ps_coins":price,"price":price,"trend_ps":trend,"version":version}

class MarketProvider:
    def __init__(self,platform="ps"):
        self.platform=platform; self.enabled=True
    def _get_page(self,page):
        url=f"{BASE_URL}/prices?page={page}&sort=price_asc"
        req=Request(url,headers={
            "User-Agent":random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
            ]),
            "Accept":"text/html,application/xhtml+xml",
            "Accept-Language":"en-US,en;q=0.9",
            "Referer":f"{BASE_URL}/prices"
        })
        with urlopen(req,timeout=45) as r:return r.read().decode("utf-8","ignore")
    def players(self,**filters):
        min_rating=int(filters.get("min_rating",40) or 40); max_rating=int(filters.get("max_rating",99) or 99)
        wanted=set((filters.get("position") or "").split(",")) if filters.get("position") else set()
        out=[]; seen=set()
        for page in range(1,MAX_PAGES+1):
            try:html=self._get_page(page)
            except (HTTPError,URLError,TimeoutError) as e:
                print(f"FUTFLIPPER page {page} failed: {e}"); break
            p=_CardParser(); p.feed(html)
            if not p.cards:
                print(f"FUTFLIPPER page {page}: no cards; bytes={len(html)} sample={html[:1000]!r}")
                break
            kept=0
            for href,text in p.cards:
                card=_parse_card(href,text)
                if not card or card["id"] in seen:continue
                seen.add(card["id"])
                if not(min_rating<=card["rating"]<=max_rating):continue
                if wanted and card["position"] not in wanted:continue
                if card["price"]<200:continue
                out.append(card); kept+=1
            print(f"FUTFLIPPER page {page}: {len(p.cards)} cards, kept {kept}, total {len(out)}")
            if page<MAX_PAGES:time.sleep(DELAY)
        return {"players":out}
    def prices(self,card_id):
        raise RuntimeError("Market provider uses FUT Flipper live FC27 price list.")
    def health(self):
        return {"enabled":True,"provider":"FUT Flipper FC27 live console prices","platform":"ps/xbox","endpoint":"https://futflipper.com/prices"}
