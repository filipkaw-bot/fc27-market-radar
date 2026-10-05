let data={opportunities:[],market:[],totw:[]},filter="all";
async function load(){
 try{data.opportunities=await(await fetch("data/opportunities.json")).json()}catch{}
 try{data.market=(await(await fetch("data/market.json")).json()).opportunities||[]}catch{}
 try{data.totw=await(await fetch("data/totw.json")).json()}catch{}
 render()
}
const esc=v=>String(v??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function render(){
 const o=data.market.length?data.market:data.opportunities;
 document.querySelector("#opps").textContent=o.length;
 document.querySelector("#buy").textContent=o.filter(x=>x.action==="buy").length;
 document.querySelector("#watch").textContent=o.filter(x=>x.action==="watch").length;
 document.querySelector("#updated").textContent="Ostatnia aktualizacja: "+(o[0]?.updated||"dane z ostatniego skanu");
 const v=o.filter(x=>filter==="all"||filter===x.action||filter===x.kind);
 document.querySelector("#cards").innerHTML=v.map(x=>'<article class="card"><div><div class="title">'+esc(x.name)+'</div><div class="meta">'+esc(x.evolution||x.kind||"Market")+' • '+esc(x.league||"")+' • '+(x.price?Number(x.price).toLocaleString()+" coins":"cena: —")+'</div><div>'+(x.tags||[]).map(t=>'<span class="tag">'+esc(t)+'</span>').join("")+'</div><div class="why"><b>Dlaczego:</b> '+esc(x.why||"Wykryto sygnał.")+'</div></div><div><div class="score '+esc(x.action)+'">'+esc(x.score)+'/100</div><div class="meta">'+(x.action==="buy"?"KUP TERAZ":"OBSERWUJ")+'</div></div></article>').join("")||'<div class="card">Brak potwierdzonych okazji.</div>';
 document.querySelector("#totw").innerHTML=data.totw.map(x=>'<div class="totw"><strong>'+esc(x.player)+'</strong><span class="prob">'+esc(x.probability)+'%</span><div class="meta">'+esc(x.club)+' • '+esc(x.position)+'</div><div class="risk">'+esc(x.reason)+'</div></div>').join("")||'<div class="totw">TOTW Radar — następny moduł.</div>'
}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("nav button").forEach(x=>x.classList.remove("active"));b.classList.add("active");filter=b.dataset.filter;render()});
load();