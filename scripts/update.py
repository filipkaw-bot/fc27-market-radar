import json,re,os
from datetime import datetime,timezone
from urllib.request import Request,urlopen
HEAD={"User-Agent":"Mozilla/5.0 FC27-Market-Radar/2.0"}
SOURCES={"whats_new":"https://www.fut.gg/whats-new/","whats_hot":"https://www.fut.gg/whats-hot/","expiring":"https://www.fut.gg/expiring-soon/","sbc":"https://www.fut.gg/sbc/","objectives":"https://www.fut.gg/objectives/","evolutions":"https://www.fut.gg/evolutions/"}
POS=r"(?:GK|LB|RB|CB|CDM|CM|CAM|LM|RM|LW|RW|ST)"
WORD=r"[A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9'’&+.-]*"
def fetch(url):
    with urlopen(Request(url,headers=HEAD),timeout=25) as r:return r.read().decode("utf-8","ignore")
def clean(s):
    s=re.sub(r"<script[^>]*>.*?</script>"," ",s,flags=re.S|re.I); s=re.sub(r"<style[^>]*>.*?</style>"," ",s,flags=re.S|re.I); s=re.sub(r"<[^>]+>"," ",s); return re.sub(r"\s+"," ",s).strip()
def parse_evos(text):
    out=[]
    for m in re.finditer(r"Requirements\s+(.{0,420})",text):
        before=text[max(0,m.start()-700):m.start()]; tail=m.group(1)
        cards=list(re.finditer(rf"(({WORD})(?:\s+{WORD}){{0,3}})\s+(\d{{2}})\s+({POS})\s",before))
        if not cards: continue
        c=cards[-1]; player=c.group(1); rating=int(c.group(3)); mainpos=c.group(4)
        # The EVO heading is normally immediately before its descriptive sentence.
        chunks=re.findall(r"((?:[A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9'’&+.-]*\s+){1,6})(?:New)?(?:Boost|Sharpen|Elevate|Build|Send|Unlock|Explore|Upgrade|Complete|Give|Control|Welcome|Discover)\b",before[:c.start()])
        if not chunks: continue
        title=chunks[-1].strip()
        req={"overall_max":None,"positions":[],"excluded_positions":[],"max_playstyles":None,"pace_max":None}
        z=re.search(r"Overall Max\.\s*(\d+)",tail,re.I)
        if z:req["overall_max"]=int(z.group(1))
        z=re.search(r"Position\s+(.{1,50}?)(?:\s+Excluded Position|\s+Max PS|\s+Pace Max\.|$)",tail,re.I)
        if z:req["positions"]=re.findall(POS,z.group(1))
        z=re.search(r"Excluded Position\s+(.{1,50}?)(?:\s+Max PS|\s+Pace Max\.|$)",tail,re.I)
        if z:req["excluded_positions"]=re.findall(POS,z.group(1))
        z=re.search(r"Max PS\s*(\d+)",tail,re.I)
        if z:req["max_playstyles"]=int(z.group(1))
        z=re.search(r"Pace Max\.\s*(\d+)",tail,re.I)
        if z:req["pace_max"]=int(z.group(1))
        out.append({"name":title,"kind":"Evolutions","requirements":req,"example_player":player,"example_rating":rating,"example_position":mainpos})
    seen=set(); result=[]
    for x in out:
        k=(x["name"].lower(),json.dumps(x["requirements"],sort_keys=True))
        if k not in seen: seen.add(k); result.append(x)
    return result
def generic(text,kind):
    names=[]
    if kind=="SBC":
        for p in [r"New\s+([A-ZÀ-ÖØ-öø-ÿ][^.!?]{2,60}?)\s+(?:\d[\d,.]*K)",r"Earn\s+(?:a\s+special\s+)?([A-ZÀ-ÖØ-öø-ÿ][^.!?]{2,60}?)\."]:
            names += [m.group(1).strip() for m in re.finditer(p,text)]
    elif kind=="Objectives":
        names += [m.group(1).strip() for m in re.finditer(r"New\s+([A-Z][^.!?]{3,70})",text)]
    return [{"name":n,"kind":kind} for n in names[:20]]
now=datetime.now(timezone.utc).isoformat(); out=[]
for key,url in SOURCES.items():
    try:
        text=clean(fetch(url)); kind={"whats_new":"Content","whats_hot":"Content","expiring":"Expiring","sbc":"SBC","objectives":"Objectives","evolutions":"Evolutions"}[key]
        items=parse_evos(text) if kind=="Evolutions" else generic(text,kind)
        for x in items:
            x.update({"score":55 if kind=="Evolutions" else 45,"action":"watch","tags":[kind,"REQUIREMENTS"] if kind=="Evolutions" else [kind],"why":"Wykryto aktywny element contentu; wymagania zapisane do analizy rynku.","source":url,"updated":now})
            out.append(x)
    except Exception as e: print("source failed",key,e)
seen=set(); final=[]
for x in out:
    k=(x["kind"],x["name"].lower(),json.dumps(x.get("requirements",{}),sort_keys=True))
    if k not in seen: seen.add(k); final.append(x)
os.makedirs("data",exist_ok=True)
with open("data/opportunities.json","w",encoding="utf-8") as f: json.dump(final[:100],f,ensure_ascii=False,indent=2)
print("generated",len(final))
