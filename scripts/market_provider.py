import os,json,urllib.parse
from urllib.request import Request,urlopen

API_KEY=os.getenv("PARSE_API_KEY","").strip()
BASE_URL=os.getenv("PARSE_FUTGG_BASE_URL","https://api.parse.bot/scraper/a1271aad-bcbf-4464-8762-47f1d15efa81").rstrip("/")

class MarketProvider:
    def __init__(self,platform="ps"):
        self.platform=platform
        self.enabled=bool(API_KEY)

    def _get(self,endpoint,params):
        if not self.enabled:
            raise RuntimeError("PARSE_API_KEY is not configured")
        clean={k:v for k,v in params.items() if v is not None}
        url=f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(clean)}"
        req=Request(url,headers={
            "X-API-Key":API_KEY,
            "Accept":"application/json",
            "User-Agent":"FC27-Market-Radar/1.0"
        })
        with urlopen(req,timeout=30) as r:
            return json.loads(r.read().decode())

    def players(self,**filters):
        filters={**filters,"platform":self.platform}
        filters.setdefault("page",1)
        return self._get("list_players",filters)

    def prices(self,card_id):
        return self._get("get_card_prices",{
            "card_id":card_id,
            "platform":self.platform
        })

    def health(self):
        return {"enabled":self.enabled,"provider":"Parse / FUT.GG data wrapper","platform":self.platform}
