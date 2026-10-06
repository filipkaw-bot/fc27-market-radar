let data={opportunities:[],market:[],totw:[],health:{}},filter="all";
const RAW="./data/";
async function getJson(name){const r=await fetch(RAW+name+"?t="+Date.now(),{cache:"no-store"});if(!r.ok)throw new Error(r.status);return r.json()}
async function load(){
  try{data.opportunities=await getJson("opportunities.json")}catch{}
  try{const m=await getJson("market.json");data.market=m.opportunities||[];data.health=m}catch{data.market=[];data.health={}}
  try{data.totw=await getJson("totw.json")}catch{}
  render()
}
const esc=v=>String(v??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const coins=v=>v==null?"—":Number(v).toLocaleString("pl-PL")+" coins";
function render(){
  const all=[...data.market].sort((a,b)=>(b.score??0)-(a.score??0));
  const top=all.slice(0,3);
  const shown=filter==="all"?top:all.filter(x=>filter===x.action||filter===x.kind).slice(0,3);
  const stamp=data.health.updated||top[0]?.updated;
  document.querySelector("#opps").textContent=top.length;
  document.querySelector("#buy").textContent=top.filter(x=>x.action==="buy").length;
  document.querySelector("#watch").textContent=top.filter(x=>x.action==="watch").length;
  document.querySelector("#updated").textContent=stamp?new Date(stamp).toLocaleString("pl-PL",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"brak skanu";
  document.querySelector("#age").textContent=stamp?Math.max(0,Math.round((Date.now()-new Date(stamp))/60000))+"m":"—";
  document.querySelector("#shown").textContent=shown.length+" kart";
  const feedOk=data.health.status==="ok"&&Number(data.health.market_rows_scanned)>0;
  document.querySelector(".live b").textContent=feedOk?"RADAR ONLINE":"RADAR OSTRZEGA";
  document.querySelector(".live small").textContent=feedOk?"FUT.GG PC • automatyczny skan":"brak potwierdzonego feedu PC";
  document.querySelector("#cards").innerHTML=shown.map((x,i)=>'<article class="card '+(x.action==="buy"?"buy":x.action==="watch"?"watch":"")+'"><div><div class="cardtop"><div><div class="rank">#'+(i+1)+'</div><div class="title">'+esc(x.name)+'</div><div class="sub">'+esc(x.evolution||"Catalyst")+" • "+esc(x.position||"")+" • "+esc(x.source||"FUT.GG PC")+'</div></div></div><div class="why"><b>Ocena inwestycji</b><br>Rynek: '+coins(x.price)+' • Cel: '+coins(x.target_sell)+' • Maks. zakup: '+coins(x.max_buy_price)+'</div></div><div class="scorebox"><div class="score '+(x.action==="buy"?"buy":x.action==="watch"?"watch":"")+'">'+esc(x.score)+'/100</div><div class="price"><span>KUP DO</span><strong>'+coins(x.max_buy_price??x.price)+'</strong></div></div></article>').join("")||'<div class="empty"><b>Brak potwierdzonych okazji</b>Radar nie pokaże BUY bez aktualnej ceny PC z FUT.GG.</div>';
}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("nav button").forEach(x=>x.classList.remove("active"));b.classList.add("active");filter=b.dataset.filter;render()});
load();setInterval(load,30000);
