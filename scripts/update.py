import json,re,os
from datetime import datetime,timezone
from urllib.request import Request,urlopen

HEAD={"User-Agent":"Mozilla/5.0 FC27-Market-Radar/1.0"}
SOURCES={
 "whats_new":"https://www.fut.gg/whats-new/",
 "whats_hot":"https://www.fut.gg/whats-hot/",
 "expiring":"https://www.fut.gg/expiring-soon/",
 "sbc":"https://www.fut.gg/sbc/",
 "objectives":"https://www.fut.gg/objectives/",
 "evolutions":"https://www.fut.gg/evolutions/"
}

def fetch(url):
    req=Request(url,headers=HEAD)
    with urlopen(req,timeout=25) as r:return r.read().decode("utf-8","ignore")

def clean(s):
    return re.sub(r"\s+"," ",re.sub("<[^>]+>"," ",s)).strip()

def page_text(html):
    return clean(html)

def extract_blocks(html):
    # Conservative text extraction: only create candidates from visible page content.
    text=page_text(html)
    return text[:120000]

def detect(page,kind):
    patterns=[]
    if kind=="Evolutions":
        patterns=re.findall(r"([A-Z][A-Za-zÀ-ÿ'’.-]{2,30})[^.]{0,160}(?:Requirements|Overall Max\.)",page)
    elif kind=="SBC":
        patterns=re.findall(r"(?:New\s+)?([A-Z][A-Za-zÀ-ÿ'’.-]{2,35})\s+(\d[\d,.]*K?)",page)
    elif kind=="Objectives":
        patterns=re.findall(r"(?:New\s+)([A-Z][A-Za-zÀ-ÿ'’0-9:.-]{3,60})",page)
    return patterns[:40]

def score(name,kind,page):
    s=45
    tags=[kind]
    if "New" in page:s+=15;tags.append("NEW")
    if "Expiring" in page:s+=8;tags.append("EXPIRING")
    if kind=="Evolutions":
        s+=10;tags.append("REQUIREMENTS")
    if kind=="SBC":
        s+=5;tags.append("SBC")
    return min(100,s),tags

now=datetime.now(timezone.utc).isoformat()
opps=[]
for key,url in SOURCES.items():
    try:
        html=fetch(url); text=extract_blocks(html)
        kind={"whats_new":"Content","whats_hot":"Content","expiring":"Expiring","sbc":"SBC","objectives":"Objectives","evolutions":"Evolutions"}[key]
        for item in detect(text,kind):
            name=item[0] if isinstance(item,tuple) else item
            if len(name)<3:continue
            score_v,tags=score(name,kind,text)
            action="buy" if score_v>=85 else "watch"
            opps.append({"name":name,"kind":kind,"score":score_v,"action":action,"tags":tags,"why":"Wykryto zmianę lub aktywny element contentu. Cena i ograniczenie podaży wymagają potwierdzenia przez provider rynku.","source":url,"updated":now})
    except Exception as e:
        print("source failed",key,e)

# Deduplicate conservatively.
seen=set();out=[]
for x in opps:
    k=(x["name"].lower(),x["kind"])
    if k not in seen:
        seen.add(k);out.append(x)
out.sort(key=lambda x:x["score"],reverse=True)
os.makedirs("data",exist_ok=True)
with open("data/opportunities.json","w",encoding="utf-8") as f:json.dump(out[:100],f,ensure_ascii=False,indent=2)
with open("data/totw.json","w",encoding="utf-8") as f:json.dump([],f)
print("generated",len(out))
