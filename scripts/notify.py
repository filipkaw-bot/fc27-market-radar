import json,os,urllib.parse
from urllib.request import Request,urlopen
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip(); CHAT=os.getenv("TELEGRAM_CHAT_ID","").strip()
def send(msg):
    if not TOKEN or not CHAT: print("Telegram not configured; skipping"); return False
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body=urllib.parse.urlencode({"chat_id":CHAT,"text":msg}).encode()
    with urlopen(Request(url,data=body,headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=20) as r: return True
def main():
    if not TOKEN or not CHAT: return
    try: data=json.load(open("data/market.json",encoding="utf-8"))
    except: return
    alerts=[x for x in data.get("opportunities",[]) if x.get("score",0)>=85 and x.get("action")=="buy"]
    try: state=json.load(open("data/telegram_state.json",encoding="utf-8"))
    except: state={"sent":[]}
    sent=set(state.get("sent",[]))
    for x in alerts[:5]:
        key=f'{x.get("evolution")}::{x.get("card_id")}::{x.get("price")}'
        if key in sent: continue
        msg=(f"🟢 FC27 MARKET RADAR — {x.get('score')}/100\n\n"
             f"KARTA: {x.get('name')} ({x.get('rating')} {x.get('position')})\n"
             f"EVO: {x.get('evolution')}\nBIN: {x.get('price'):,} coins\n"
             f"Po podatku: {x.get('net_sale'):,} coins\n"
             f"Różnica vs mediana: {x.get('potential_vs_median')}%\n\n{x.get('why')}")
        if send(msg): sent.add(key)
    with open("data/telegram_state.json","w",encoding="utf-8") as f: json.dump({"sent":list(sent)[-200:]},f)
if __name__=="__main__": main()
