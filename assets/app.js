let data={opportunities:[],market:[],totw:[]},filter="all";
const RAW="./data/";
async function getJson(name){const r=await fetch(RAW+name+"?t="+Date.now(),{cache:"no-store"});if(!r.ok)throw new Error(r.status);return r.json()}
async function load(){
 try{data.opportunities=await getJson("opportunities.json")}catch{}
 try{data.market=(await getJson("market.json")).opportunities||[]}catch{}
 try{data.totw=await getJson("totw.json")}catch{}
 render()
}
const esc=v=>String(v??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const coins=v=>v==null?"—":Number(v).toLocaleString("pl-PL")+" coins";
function render(){
 const o=[...data.market].sort((a,b)=>(b.score??0)-(a.score??0)).slice(0,3);
 document.querySelector("#opps").textContent=o.length;
 document.querySelector("#buy").textContent=o.filter(x=>x.action==="buy").length;
 document.querySelector("#watch").textContent=o.filter(x=>x.action==="watch").length;
 const stamp=o[0]?.updated;
 document.querySelector("#updated").textContent=stamp?new Date(stamp).toLocaleString("pl-PL",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"brak skanu";
 document.querySelector("#age").textContent=stamp?Math.max(0,Math.round((Date.now()-new Date(stamp))/60000))+"m":"—";
 const v=o.filter(x=>filter==="all"||filter===x.action||filter===x.kind);
 document.querySelector("#shown").textContent=v.length+" kart";
 document.querySelector("#cards").innerHTML=v.map((x,i)=>'<article class="card '+(x.action==="buy"?"buy":x.action==="watch"?"watch":"")+'"><div><div class="cardtop"><div><div class="rank">#'+(i+1)+'</div><div class="title">'+esc(x.name)+'</div><div class="sub">'+esc(x.evolution||"Catalyst")+" • "+esc(x.position||"")+" • "+esc(x.source||"FUT.GG PC")+'</div></div></div><div class="why"><b>Ocena inwestycji</b></div></div><div class="scorebox"><div class="score '+(x.action==="buy"?"buy":x.action==="watch"?"watch":"")+'">'+esc(x.score)+'/100</div><div class="price"><span>KUP DO</span><strong>'+coins(x.price)+'</strong></div></div></article>').join("")||'<div class="empty"><b>Brak potwierdzonych okazji</b>Radar nie ma aktualnej ceny PC z FUT.GG.</div>';
}

document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("nav button").forEach(x=>x.classList.remove("active"));b.classList.add("active");filter=b.dataset.filter;render()});
load();setInterval(load,30000);
