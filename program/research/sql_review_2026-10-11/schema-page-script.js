
const env=document.getElementById('env'),input=document.getElementById('filter'),rows=[...document.querySelectorAll('.relation')];
function filter(){let n=0;rows.forEach(r=>{const show=r.dataset.env===env.value&&r.textContent.toLowerCase().includes(input.value.toLowerCase());r.hidden=!show;if(show)n++;});document.getElementById('count').textContent='현재 검색 결과 '+n+'개 · 조회 당시 구조';}
env.addEventListener('change',filter);input.addEventListener('input',filter);document.getElementById('expand').addEventListener('click',()=>rows.filter(r=>!r.hidden).forEach(r=>r.open=true));document.getElementById('collapse').addEventListener('click',()=>rows.forEach(r=>r.open=false));filter();
