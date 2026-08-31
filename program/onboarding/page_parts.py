# -*- coding: utf-8 -*-
"""한 파일짜리 화면의 CSS 와 JS 와 뼈대. 내용은 trace_data.py 에 있다."""

CSS = """
:root{--bg:#f5f6fa;--card:#fff;--line:#dde2ec;--ink:#151b27;--dim:#5f6a80;--faint:#98a2b6;
--red:#b8442f;--blue:#2f5bd8;--green:#0d7a4d;--purple:#6b3fa0;--grey:#5f6a80;
--code-bg:#0f141f;--code-ink:#dbe3f0}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#11141b;--card:#181c25;--line:#2a303d;--ink:#e7eaf2;--dim:#98a2b8;--faint:#6d778c;
--red:#e08063;--blue:#7fa1f7;--green:#4bb489;--purple:#a888e0;--grey:#98a2b8}}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.65;
font-family:"Malgun Gothic",system-ui,sans-serif}
code,pre{font-family:Consolas,"D2Coding",monospace}
.wrap{max-width:1560px;margin:0 auto;padding:26px 22px 80px}
h1{font-size:29px;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--dim);font-size:15px;margin:0 0 20px;max-width:88ch}
h2.sec{font-size:20px;margin:52px 0 4px;padding-left:13px;border-left:5px solid var(--blue)}
h2.sec + p{color:var(--dim);font-size:14.5px;margin:0 0 16px;padding-left:18px}
button{font:inherit;font-size:14px;padding:8px 15px;border-radius:9px;cursor:pointer;
border:1px solid var(--line);background:var(--card);color:var(--ink)}
button:hover{border-color:var(--blue);color:var(--blue)}
button.primary{background:var(--blue);border-color:var(--blue);color:#fff}
button.primary:hover{opacity:.9;color:#fff}
button:disabled{opacity:.4;cursor:not-allowed}
.dock{position:fixed;right:22px;bottom:22px;z-index:40;display:flex;flex-direction:column;
align-items:flex-end;gap:11px}
.dock .menu{display:none;flex-direction:column;gap:7px;background:var(--card);
border:1px solid var(--line);border-radius:15px;padding:12px;min-width:216px;
box-shadow:0 16px 44px rgba(8,12,22,.26);animation:pop .18s ease both}
.dock.on .menu{display:flex}
@keyframes pop{from{opacity:0;transform:translateY(12px) scale(.96)}to{opacity:1;transform:none}}
.dock .menu button{width:100%;text-align:left}
.dock .tick{font-size:12.5px;color:var(--dim);text-align:center;padding-top:8px;margin-top:2px;
border-top:1px solid var(--line)}
.fab{width:66px;height:66px;border-radius:50%;padding:0;background:var(--blue);border:none;
color:#fff;box-shadow:0 9px 26px rgba(47,91,216,.44);display:flex;flex-direction:column;
align-items:center;justify-content:center;line-height:1.12;transition:.2s}
.fab:hover{color:#fff;border:none;transform:scale(1.07)}
.fab .big{font-size:19px;font-weight:700}
.fab .small{font-size:10.5px;opacity:.86}
.dock.on .fab{background:var(--ink);box-shadow:0 9px 26px rgba(8,12,22,.4)}
.dock.on .fab .big{font-size:15px}
.cols{display:grid;grid-template-columns:1fr 620px;gap:18px;margin-top:16px;align-items:start}
@media(max-width:1180px){.cols{grid-template-columns:1fr}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.panel h3{font-size:15px;margin:0 0 3px}
.panel .note{color:var(--dim);font-size:13px;margin:0 0 14px}
.map{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.st{border:2px solid var(--line);border-radius:12px;padding:11px 12px;background:transparent;
text-align:left;transition:.22s;opacity:.5;cursor:pointer}
.st .n{font-size:12px;color:var(--faint);font-weight:700}
.st .t{font-size:14.5px;font-weight:700;margin:1px 0 2px;color:var(--ink)}
.st .o{font-size:11.5px;color:var(--faint)}
.st.done{opacity:1;border-color:currentColor}
.st.now{opacity:1;transform:scale(1.045)}
.st.red{color:var(--red)}.st.blue{color:var(--blue)}.st.green{color:var(--green)}
.st.purple{color:var(--purple)}.st.grey{color:var(--grey)}
.st.red.now{background:var(--red);border-color:var(--red)}
.st.blue.now{background:var(--blue);border-color:var(--blue)}
.st.green.now{background:var(--green);border-color:var(--green)}
.st.purple.now{background:var(--purple);border-color:var(--purple)}
.st.grey.now{background:var(--grey);border-color:var(--grey)}
.st.now .n,.st.now .o{color:rgba(255,255,255,.82)}
.st.now .t{color:#fff}
.why{margin-top:16px;border-left:4px solid var(--line);padding:2px 0 2px 14px;min-height:66px}
.why .h{font-size:14px;font-weight:700;margin-bottom:3px}
.why .b{font-size:14px;color:var(--dim)}
.stream{max-height:600px;overflow-y:auto}
.chunk{border:1px solid var(--line);border-radius:10px;margin:0 0 9px;overflow:hidden;
animation:slide .34s ease both}
@keyframes slide{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.chunk .head{display:flex;gap:8px;align-items:baseline;padding:7px 12px;
background:rgba(127,140,170,.09);border-bottom:1px solid var(--line)}
.chunk .kind{font-size:11px;font-weight:700;padding:1px 7px;border-radius:5px;background:var(--bg);
border:1px solid var(--line);color:var(--dim);white-space:nowrap}
.chunk .name{font-size:13.5px;font-weight:700;font-family:Consolas,monospace}
.chunk .from{margin-left:auto;font-size:11.5px;color:var(--faint)}
.chunk pre{margin:0;padding:9px 12px;font-size:12.9px;line-height:1.62;white-space:pre;
overflow-x:auto;color:var(--ink)}
.badge{display:flex;gap:9px;align-items:center;margin-top:13px;font-size:13px;color:var(--dim)}
.badge b{font-family:Consolas,monospace;font-size:15.5px;padding:5px 13px;border-radius:8px;
border:2px solid var(--blue);color:var(--blue)}
.badge b.done{border-color:var(--green);color:var(--green)}
.files{margin-top:16px;font-size:13px}
.files div{margin:6px 0;color:var(--dim)}
.files b{color:var(--ink)}
figure{margin:20px 0 0;background:var(--card);border:1px solid var(--line);border-radius:14px;
overflow:hidden}
figure img{display:block;width:100%;height:auto}
figcaption{padding:15px 20px 18px;border-top:1px solid var(--line)}
figcaption b{display:block;font-size:16px;margin-bottom:4px}
figcaption span{color:var(--dim);font-size:14px}
nav.jump{background:var(--bg);border-bottom:1px solid var(--line);padding:10px 0;margin:16px 0 0;
overflow-x:auto;white-space:nowrap}
nav.jump a{display:inline-block;padding:5px 11px;margin-right:3px;font-size:12.5px;
color:var(--dim);text-decoration:none;border:1px solid var(--line);border-radius:99px}
nav.jump a:hover{color:var(--blue);border-color:var(--blue)}
.ov{position:fixed;inset:0;background:rgba(8,11,18,.74);display:none;z-index:60;padding:34px 22px;
overflow-y:auto}
.ov.on{display:block}
.ovbox{max-width:1080px;margin:0 auto;background:var(--card);border:1px solid var(--line);
border-radius:14px;overflow:hidden}
.ovhead{display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line);
position:sticky;top:0;background:var(--card);z-index:2}
.ovhead h3{margin:0;font-size:17px}
.ovhead .x{margin-left:auto}
.src{border-top:1px solid var(--line)}
.src .path{padding:9px 18px;font-family:Consolas,monospace;font-size:12.5px;color:var(--dim);
background:rgba(127,140,170,.09)}
.src pre{margin:0;padding:15px 18px;background:var(--code-bg);color:var(--code-ink);font-size:13px;
line-height:1.66;overflow-x:auto;white-space:pre}
.plain{padding:15px 20px 19px;font-size:14.3px;line-height:1.82;
border-top:3px solid var(--blue);background:rgba(47,91,216,.055)}
.plain .lbl{display:inline-block;font-size:11.5px;font-weight:700;color:var(--blue);
border:1px solid var(--blue);border-radius:5px;padding:1px 8px;margin-bottom:9px}
.plain p{margin:0 0 11px}
.plain p:last-child{margin-bottom:0}
.plain code{background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:1px 5px;
font-size:12.8px}
.foot{margin-top:40px;padding-top:20px;border-top:1px solid var(--line);color:var(--dim);
font-size:13px}
"""

JS = r"""
const STEPS = __DATA__;
let cur = -1, timer = null;
const $ = id => document.getElementById(id);
const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function render(){
  document.querySelectorAll('.st').forEach((el,i)=>{
    el.classList.toggle('now', i===cur);
    el.classList.toggle('done', i<cur);
  });
  const s = cur>=0 ? STEPS[cur] : null;
  $('why').innerHTML = s
    ? '<div class="h">'+s.n+'. '+esc(s.title)
      +' <span style="color:var(--faint);font-weight:400">'+esc(s.owner)+'</span></div>'
      +'<div class="b">'+esc(s.why)+'</div>'
    : '<div class="b">오른쪽 아래 동그란 단추를 눌러 조작판을 펼치고 <b>다음 단계</b>나'
      +' <b>자동 재생</b>을 누르면 1번부터 시작합니다.'
      +' 아래 칸을 직접 눌러 그 지점으로 갈 수도 있습니다.</div>';

  let out = '';
  for(let i=0;i<=cur;i++){
    for(const part of STEPS[i].add){
      out += '<div class="chunk"><div class="head"><span class="kind">'+esc(part[0])+'</span>'
          +  '<span class="name">'+esc(part[1])+'</span>'
          +  '<span class="from">'+STEPS[i].n+'번 단계</span></div><pre>'
          +  esc(part[2].join('\n'))+'</pre></div>';
    }
  }
  $('stream').innerHTML = out
    || '<div style="color:var(--faint);font-size:13.5px">아직 아무것도 안 만들어졌습니다.</div>';
  $('stream').scrollTop = $('stream').scrollHeight;

  let st = null;
  for(let i=0;i<=cur;i++) if(STEPS[i].state) st = STEPS[i].state;
  $('badge').innerHTML = st
    ? 'Case 상태 <b class="'+(st[0]==='resolved'?'done':'')+'">'+st[0]+'  v'+st[1]+'</b>'
    : 'Case 상태 <span style="color:var(--faint)">아직 Case 가 없습니다</span>';

  $('tick').textContent = cur<0 ? '아직 시작 안 함' : (cur+1)+' / '+STEPS.length+' 단계';
  $('fabn').textContent = cur<0 ? '시작' : String(cur+1);
  $('fabs').textContent = cur<0 ? '1~'+STEPS.length : '/ '+STEPS.length;
  $('prev').disabled = cur<0;
  $('next').disabled = cur>=STEPS.length-1;
  $('code').disabled = cur<0;
}

function go(i){ cur = Math.max(-1, Math.min(STEPS.length-1, i)); render(); }
function play(){
  if(timer){ clearInterval(timer); timer=null; $('play').textContent='자동 재생'; return; }
  if(cur>=STEPS.length-1) cur=-1;
  $('play').textContent='멈춤';
  timer = setInterval(()=>{ if(cur>=STEPS.length-1){ play(); return; } go(cur+1); }, 2600);
}
function dock(e){
  if(e) e.stopPropagation();
  $('dock').classList.toggle('on');
}
document.addEventListener('click', e=>{
  const d = $('dock');
  if(d.classList.contains('on') && !d.contains(e.target)) d.classList.remove('on');
});

function showCode(){
  if(cur<0) return;
  $('dock').classList.remove('on');
  const s = STEPS[cur];
  $('ovtitle').textContent = s.n+'번 단계 · '+s.title+' · 이 일을 실제로 하는 코드';
  $('ovbody').innerHTML = s.code.map(c =>
    '<div class="src"><div class="path">'+esc(c.path)+'</div>'
    +'<pre>'+esc(c.code)+'</pre>'
    +'<div class="plain"><span class="lbl">쉬운 풀이</span>'
    + c.plain.split('\n\n').map(p=>'<p>'+p+'</p>').join('')
    +'</div></div>').join('');
  $('ov').classList.add('on');
  $('ov').scrollTop = 0;
}
function hideCode(){ $('ov').classList.remove('on'); }
document.addEventListener('keydown', e=>{
  if(e.key==='Escape') hideCode();
  else if($('ov').classList.contains('on')) return;
  else if(e.key==='ArrowRight'){ e.preventDefault(); go(cur+1); }
  else if(e.key==='ArrowLeft'){ e.preventDefault(); go(cur-1); }
});
render();
"""

PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>취소·환불 한 건이 지나는 길</title><style>%(css)s</style></head><body>
<div class="wrap">
<h1>취소·환불 한 건이 지나는 길</h1>
<p class="sub">고객이 "어제 주문한 거 취소하고 환불받고 싶어요. 아직 안 왔어요." 를 보낸 순간부터
답이 돌아갈 때까지, 어떤 코드를 지나 무엇이 어디에 기록되는지 한 건으로 따라갑니다.
위쪽은 직접 돌려 보는 시뮬레이터이고, 아래쪽은 같은 내용을 그림 열아홉 장으로 편 것입니다.</p>

<h2 class="sec">직접 돌려 보기</h2>
<p>1번부터 12번까지 진행하면 오른쪽에 값이 한 덩어리씩 쌓입니다.
각 덩어리 왼쪽 꼬리표가 <b>무슨 형식인지</b>를 말합니다.
오른쪽 아래 동그란 단추를 누르면 조작판이 펼쳐집니다. 거기 있는
<b>이 단계 코드 보기</b>가 실제 코드와 그 코드의 쉬운 풀이를 띄웁니다.</p>

<div class="cols">
  <div class="panel">
    <h3>열두 단계</h3>
    <p class="note">칸을 직접 눌러 그 지점으로 갈 수 있습니다. 좌우 화살표 키도 됩니다.</p>
    <div class="map">%(stations)s</div>
    <div class="why" id="why"></div>
    <div class="files">%(files)s</div>
  </div>
  <div class="panel">
    <h3>지금까지 만들어진 것</h3>
    <p class="note">단계를 지날 때마다 아래로 쌓입니다.</p>
    <div class="stream" id="stream"></div>
    <div class="badge" id="badge"></div>
  </div>
</div>

<h2 class="sec">그림으로 펴 보기</h2>
<p>같은 내용을 한 장씩 펼친 것입니다. 각 장 위쪽 진행바가 지금 어디인지 알려 줍니다.</p>
<nav class="jump">%(links)s</nav>
%(figures)s

<div class="foot">코드는 <code>final_project_cs</code> 에서 줄 번호로 잘라 온 실제 코드입니다.
손으로 옮겨 적지 않았습니다. 흐름은 <code>program/onboarding/trace_refund_case.html</code>,
구조 분류는 <code>final_project_cs/docs/handoff/08_모듈_컴포넌트_목록.md</code>,
담당은 <code>program/plan/A-COP_스프린트_에픽_설계.md</code> 를 따랐습니다.<br>
이 파일은 <code>program/onboarding/build_trace_html.py</code> 가 만듭니다.
내용은 <code>program/onboarding/trace_data.py</code> 에 있습니다. 손으로 고치지 마세요.</div>
</div>

<div class="ov" id="ov" onclick="if(event.target===this)hideCode()">
  <div class="ovbox">
    <div class="ovhead"><h3 id="ovtitle"></h3>
      <button class="x" onclick="hideCode()">닫기 (Esc)</button></div>
    <div id="ovbody"></div>
  </div>
</div>

<div class="dock" id="dock">
  <div class="menu">
    <button id="prev" onclick="go(cur-1)">이전 단계</button>
    <button id="next" class="primary" onclick="go(cur+1)">다음 단계</button>
    <button id="play" onclick="play()">자동 재생</button>
    <button onclick="go(-1)">처음으로</button>
    <button id="code" onclick="showCode()">이 단계 코드 보기</button>
    <div class="tick" id="tick">시작 전</div>
  </div>
  <button class="fab" onclick="dock(event)" title="시뮬레이터 조작">
    <span class="big" id="fabn">시작</span><span class="small" id="fabs">1~12</span>
  </button>
</div>

<script>%(js)s</script></body></html>
"""
