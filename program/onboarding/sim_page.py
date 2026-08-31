# -*- coding: utf-8 -*-
"""시뮬레이터 화면. 내용은 build_trace_sim.py 에 있고 여기는 껍데기다."""
import html
import json
import os

CSS = """
:root{--bg:#f5f6fa;--card:#fff;--line:#dde2ec;--ink:#151b27;--dim:#606b80;--faint:#98a2b6;
--red:#b8442f;--blue:#2f5bd8;--green:#0d7a4d;--purple:#6b3fa0;--grey:#606b80;
--code-bg:#0f141f;--code-ink:#dbe3f0}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#11141b;--card:#181c25;--line:#2a303d;--ink:#e7eaf2;--dim:#98a2b8;--faint:#6d778c;
--red:#e08063;--blue:#7fa1f7;--green:#4bb489;--purple:#a888e0;--grey:#98a2b8}}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.65;
font-family:"Malgun Gothic",system-ui,sans-serif}
code,pre{font-family:Consolas,"D2Coding",monospace}
.wrap{max-width:1560px;margin:0 auto;padding:26px 22px 70px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--dim);font-size:15px;margin:0 0 18px}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--card);
border:1px solid var(--line);border-radius:12px;padding:11px 14px;position:sticky;top:0;z-index:20}
button{font:inherit;font-size:14px;padding:8px 15px;border-radius:9px;cursor:pointer;
border:1px solid var(--line);background:var(--card);color:var(--ink)}
button:hover{border-color:var(--blue);color:var(--blue)}
button.primary{background:var(--blue);border-color:var(--blue);color:#fff}
button.primary:hover{opacity:.9;color:#fff}
button:disabled{opacity:.4;cursor:not-allowed}
.tick{margin-left:auto;color:var(--dim);font-size:13.5px}
.cols{display:grid;grid-template-columns:1fr 640px;gap:18px;margin-top:18px;align-items:start}
@media(max-width:1180px){.cols{grid-template-columns:1fr}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.panel h2{font-size:15px;margin:0 0 3px}
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
.why{margin-top:16px;border-left:4px solid var(--line);padding:2px 0 2px 14px;min-height:64px}
.why .h{font-size:14px;font-weight:700;margin-bottom:3px}
.why .b{font-size:14px;color:var(--dim)}
.stream{max-height:620px;overflow-y:auto}
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
.ov{position:fixed;inset:0;background:rgba(8,11,18,.72);display:none;z-index:60;padding:36px 24px;
overflow-y:auto}
.ov.on{display:block}
.ovbox{max-width:1080px;margin:0 auto;background:var(--card);border:1px solid var(--line);
border-radius:14px;overflow:hidden}
.ovhead{display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line)}
.ovhead h3{margin:0;font-size:17px}
.ovhead .x{margin-left:auto}
.src{border-top:1px solid var(--line)}
.src .path{padding:9px 18px;font-family:Consolas,monospace;font-size:12.5px;color:var(--dim);
background:rgba(127,140,170,.09)}
.src pre{margin:0;padding:15px 18px;background:var(--code-bg);color:var(--code-ink);font-size:13px;
line-height:1.66;overflow-x:auto;white-space:pre}
.foot{margin-top:26px;color:var(--dim);font-size:13px}
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
    : '<div class="b">아래 <b>다음</b>이나 <b>자동 재생</b>을 누르면 1번부터 시작합니다.'
      +' 칸을 직접 눌러 그 지점으로 갈 수도 있습니다.</div>';

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
    : 'Case 상태 <span style="color:var(--faint)">아직 Case 가 없다</span>';

  $('tick').textContent = cur<0 ? '시작 전' : (cur+1)+' / '+STEPS.length;
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
function showCode(){
  if(cur<0) return;
  const s = STEPS[cur];
  $('ovtitle').textContent = s.n+'. '+s.title+' 을 실제로 하는 코드';
  $('ovbody').innerHTML = s.code.map(c =>
    '<div class="src"><div class="path">'+esc(c[0])+'</div><pre>'+esc(c[2])+'</pre></div>').join('');
  $('ov').classList.add('on');
}
function hideCode(){ $('ov').classList.remove('on'); }
document.addEventListener('keydown', e=>{
  if(e.key==='Escape') hideCode();
  else if(e.key==='ArrowRight'){ e.preventDefault(); go(cur+1); }
  else if(e.key==='ArrowLeft'){ e.preventDefault(); go(cur-1); }
});
render();
"""

PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>취소·환불 케이스 시뮬레이터</title><style>%(css)s</style></head><body>
<div class="wrap">
<h1>취소·환불 한 건이 지나는 길</h1>
<p class="sub">고객이 "어제 주문한 거 취소하고 환불받고 싶어요. 아직 안 왔어요." 를 보냈습니다.
1번부터 12번까지 진행하면 오른쪽에 값이 한 덩어리씩 쌓입니다.
각 덩어리 왼쪽에 <b>무슨 형식인지</b>가 적혀 있습니다.</p>

<div class="bar">
  <button id="prev" onclick="go(cur-1)">이전</button>
  <button id="next" class="primary" onclick="go(cur+1)">다음</button>
  <button id="play" onclick="play()">자동 재생</button>
  <button onclick="go(-1)">처음으로</button>
  <button id="code" onclick="showCode()">이 단계 코드 보기</button>
  <span class="tick" id="tick">시작 전</span>
</div>

<div class="cols">
  <div class="panel">
    <h2>열두 단계</h2>
    <p class="note">칸을 직접 눌러 그 지점으로 갈 수 있습니다. 좌우 화살표 키도 됩니다.</p>
    <div class="map">%(stations)s</div>
    <div class="why" id="why"></div>
    <div class="files">%(files)s</div>
  </div>
  <div class="panel">
    <h2>지금까지 만들어진 것</h2>
    <p class="note">단계를 지날 때마다 아래로 쌓입니다. 왼쪽 꼬리표가 형식입니다.</p>
    <div class="stream" id="stream"></div>
    <div class="badge" id="badge"></div>
  </div>
</div>

<div class="foot">코드는 <code>final_project_cs</code> 에서 줄 번호로 잘라 온 실제 코드입니다.
손으로 옮겨 적지 않았습니다. 이 파일은
<code>program/onboarding/build_trace_sim.py</code> 가 만듭니다.</div>
</div>

<div class="ov" id="ov" onclick="if(event.target===this)hideCode()">
  <div class="ovbox">
    <div class="ovhead"><h3 id="ovtitle"></h3>
      <button class="x" onclick="hideCode()">닫기 (Esc)</button></div>
    <div id="ovbody"></div>
  </div>
</div>

<script>%(js)s</script></body></html>
"""


def build(steps, files_note, out):
    data = [{"n": s["n"], "title": s["title"], "owner": s["owner"], "why": s["why"],
             "add": [[k, n, lines] for k, n, lines in s["add"]],
             "state": list(s["state"]) if s.get("state") else None,
             "code": [[w, lang, c] for w, lang, c in s["code"]]}
            for s in steps]

    stations = "".join(
        '<button class="st %s" onclick="go(%d)"><div class="n">%d</div>'
        '<div class="t">%s</div><div class="o">%s</div></button>'
        % (s["color"], i, s["n"], html.escape(s["title"]),
           html.escape(s["owner"].split(" · ")[0]))
        for i, s in enumerate(steps))

    files = "".join("<div><b>%s</b> %s</div>" % (h, b) for h, b in files_note)

    page = PAGE % {
        "css": CSS, "stations": stations, "files": files,
        "js": JS.replace("__DATA__", json.dumps(data, ensure_ascii=False)),
    }
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("만듦: %s  (%.0f KB, 단계 %d개, 코드 %d조각)"
          % (out, os.path.getsize(out) / 1024, len(steps),
             sum(len(s["code"]) for s in steps)))
