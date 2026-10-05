import os,json
from urllib.request import Request,urlopen

API_KEY=os.getenv("PARSE_API_KEY","").strip()
BASE_URL=os.getenv("PARSE_FUTGG_BASE_URL","https://api.parse.bot/marketplace/21627d36-0117-4b4e-9528-0a138ddc3f31/fut-gg-api").rstrip("/")

class MarketProvider:
    def __init__(self,platform="ps"):
        self.platform=platform
        self.enabled=bool(API_KEY)
    def _get(self,endpoint,params):
        if not self.enabled:return None
        q="&".join(f"{k}={str(v).replace(' ','%20')}" for k,v in params.items() if v is not None)
        req=Request(f"{BASE_URL}/{endpoint}?{q}",headers={"X-API-Key":API_KEY,"Accept":"application/json","User-Agent":"FC27-Market-Radar/1.0"})
        with urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
    def players(self,**filters):
        return self._get("list_players",{**filters,"platform":self.platform,"page":filters.get("page",1)})
    def prices(self,card_id):
        return self._get("get_card_prices",{"card_id":card_id,"platform":self.platform})
