
const key='tripilot-wiki-review-v2-selections';
const confirmed={W04:'B',W06:'A',W07:'A',W08:'C',W09:'A',W13:'C',W15:'A'};
const form=[...document.querySelectorAll('input[type=radio]')];
const defaults=()=>Object.fromEntries([...new Set(form.map(x=>x.name))].map(k=>[k,confirmed[k]||'A']));
function selected(){return Object.fromEntries(form.filter(x=>x.checked).map(x=>[x.name,x.value]));}
function notify(){document.getElementById('selection-status').textContent='이전 댓글 9개 + 추가 댓글 6개 지시·문서 반영 완료. 확정 선택은 유지하며, 코드 구현·배포는 항목별 상태를 확인합니다.';document.getElementById('export-panel').hidden=true;}
try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved)form.filter(x=>!confirmed[x.name]).forEach(x=>{if(['A','B','C'].includes(saved[x.name]))x.checked=saved[x.name]===x.value;});}catch(e){}
form.filter(x=>confirmed[x.name]).forEach(x=>{x.checked=confirmed[x.name]===x.value;x.disabled=true;});
form.forEach(x=>x.addEventListener('change',()=>{try{localStorage.setItem(key,JSON.stringify(selected()));}catch(e){}notify();}));
document.getElementById('reset').addEventListener('click',()=>{form.filter(x=>!confirmed[x.name]).forEach(x=>x.checked=x.value==='A');try{localStorage.setItem(key,JSON.stringify(selected()));}catch(e){}notify();});
document.getElementById('export').addEventListener('click',()=>{const data={document:'guguroute wiki review v2 updated',confirmed,selections:selected(),deferred:{W11:'v11 보존; 전체 정리 후 v12 신규 작성'},scope:'instruction and document updates; implementation status is separate'};document.getElementById('export-panel').hidden=false;const text=document.getElementById('export-text');text.value=JSON.stringify(data,null,2);text.focus();text.select();});
document.getElementById('print').addEventListener('click',()=>{document.querySelectorAll('details').forEach(d=>d.open=true);window.print();});
notify();
