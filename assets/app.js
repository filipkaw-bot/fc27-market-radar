let data={opportunities:[],market:[],totw:[]},filter="all";
async function load(){
 try{data.opportunities=await(await fetch("data/opportunities.json")).json()}catch{}
 try{data.market=(await(await fetch("data/market.json")).json()).opportunities||[]}catch{}
 try{data.totw=await(await fetch("data/totw.json")).json()}catch{}
 render()
}
const esc=v=>String(v??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const coins=v=>v==null?"—":Number(v).toLocaleString("pl-PL")+" coins";
function render(){
 const o=data.market.length?data.market:data.opportunities;
 document.querySelector("#opps").textContent=o.length;
 document.querySelector("#buy").textContent=o.filter(x=>x.action==="buy").length;
 document.querySelector("#watch").textContent=o.filter(x=>x.action==="watch").length;
 const stamp=o[0]?.updated;
 document.querySelector("#updated").textContent=stamp?new Date(stamp).toLocaleString("pl-PL",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"brak skanu";
 document.querySelector("#age").textContent=stamp?Math.max(0,Math.round((Date.now()-new Date(stamp))/60000))+"m":"—";
 const v=o.filter(x=>filter==="all"||filter===x.action||filter===x.kind);
 document.querySelector("#shown").textContent=v.length+" sygnałów";
 document.querySelector("#cards").innerHTML=v.map(x=>{
  const cls=x.action==="buy"?"buy":x.action==="watch"?"watch":"";
  return '<article class="card '+cls+'"><div><div class="cardtop"><div><div class="title">'+esc(x.name)+'</div><div class="sub">'+esc(x.evolution||x.kind||"Market")+' '+(x.league?"• "+esc(x.league):"")+(x.position?" • "+esc(x.position):"")+'</div></div></div><div class="chips">'+(x.tags||[]).map(t=>'<span class="tag">'+esc(t)+'</span>').join("")+'</div><div class="why"><b>Dlaczego:</b> '+esc(x.why||"Wykryto sygnał rynkowy.")+'</div><div class="metrics">'+(x.qualifying_cards_found!=null?'<div class="metric"><b>'+esc(x.qualifying_cards_found)+'</b><span>kwalifikujących</span></div>':"")+(x.supply_proxy!=null?'<div class="metric"><b>'+esc(x.supply_proxy)+'</b><span>blisko ceny</span></div>':"")+(x.potential_vs_median!=null?'<div class="metric"><b>'+esc(x.potential_vs_median)+'%</b><span>vs mediana</span></div>':"")+'</div></div><div class="scorebox"><div class="score '+cls+'">'+esc(x.score)+'/100</div><div class="action">'+(x.action==="buy"?"KUP TERAZ":x.action==="watch"?"OBSERWUJ":"POMIŃ")+'</div><div class="price"><span>BIN</span><strong>'+coins(x.price)+'</strong></div></div></article>'
 }).join("")||'<div class="empty"><b>Brak sygnałów</b>Radar nie potwierdził obecnie okazji dla tego filtra.</div>';
 document.querySelector("#totw").innerHTML=data.totw.map(x=>'<div class="totw"><strong>'+esc(x.player)+'</strong><span class="prob">'+esc(x.probability)+'%</span><div class="sub">'+esc(x.club)+' • '+esc(x.position)+'</div><div class="risk">'+esc(x.reason)+'</div></div>').join("")||'<div class="empty"><b>TOTW Radar</b><span class="muted">Moduł predykcji będzie zasilony kolejnym etapem.</span></div>'
}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("nav button").forEach(x=>x.classList.remove("active"));b.classList.add("active");filter=b.dataset.filter;render()});
load();