# -*- coding: utf-8 -*-
"""한 파일짜리 화면의 CSS 와 JS 와 뼈대.

★낱장을 PNG 로 붙이지 않는다. 같은 내용을 HTML 로 다시 그린다.
  글자를 긁을 수 있어야 하고, 검색이 되어야 하고, 화면 크기에 맞아야 한다.

★낱장 오른쪽에 누적 패킷 칸을 붙인다. 낱장 하나만 보면 그 단계에서 무엇이
  나왔는지는 알아도 지금까지 쌓인 것이 무엇인지는 모른다.

★열두 칸 지도는 늘 펴 두지 않는다. 위쪽 진행바를 누를 때만 덮어서 띄운다.
  자리를 계속 차지하면 정작 봐야 할 낱장이 밀린다.
"""

CSS = """
:root{--bg:#f5f6fa;--card:#fff;--soft:#fbfcfe;--line:#dbe0ea;--ink:#161c28;--dim:#6b7488;
--faint:#98a1b4;--warm:#fffdf6;
--red:#b8442f;--blue:#2f5bd8;--green:#0d7a4d;--purple:#6b3fa0;--grey:#6b7488;
--code-bg:#0f141f;--code-ink:#dbe3f0;--done:#e2e6ee;--todo:#f2f4f8}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#11141b;--card:#181c25;--soft:#1d222c;--line:#2a303d;--ink:#e7eaf2;--dim:#98a2b8;
--faint:#6d778c;--warm:#211d14;
--red:#e08063;--blue:#7fa1f7;--green:#4bb489;--purple:#a888e0;--grey:#98a2b8;
--done:#2b3140;--todo:#20252f}}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.6;
font-family:"Malgun Gothic",system-ui,sans-serif}
code,pre,.mono{font-family:Consolas,"D2Coding",monospace}
.wrap{max-width:1720px;margin:0 auto;padding:24px 20px 90px}
h1{font-size:28px;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--dim);font-size:15px;margin:0 0 20px;max-width:90ch}
h2.sec{font-size:20px;margin:46px 0 4px;padding-left:13px;border-left:5px solid var(--blue)}
h2.sec + p{color:var(--dim);font-size:14.5px;margin:0 0 14px;padding-left:18px}

button{font:inherit;font-size:14px;padding:8px 15px;border-radius:9px;cursor:pointer;
border:1px solid var(--line);background:var(--card);color:var(--ink)}
button:hover{border-color:var(--blue);color:var(--blue)}
button.primary{background:var(--blue);border-color:var(--blue);color:#fff}
button.primary:hover{opacity:.9;color:#fff}
button:disabled{opacity:.4;cursor:not-allowed}

/* 진행바. 그림 위쪽에 있던 것과 같은 열두 칸이다. */
.barwrap{background:var(--card);border:1px solid var(--line);border-radius:13px;
padding:12px 15px 9px;position:sticky;top:0;z-index:25}
.barwrap .top{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.barwrap .top .t{font-size:12.5px;color:var(--faint)}
.barwrap .top .r{margin-left:auto;display:flex;gap:8px;align-items:center}
.keys{font-size:11.5px;color:var(--faint);display:flex;gap:5px;align-items:center;
margin-right:4px}
.keys kbd{font-family:Consolas,monospace;font-size:11px;border:1px solid var(--line);
border-bottom-width:2px;border-radius:4px;padding:1px 5px;background:var(--bg);color:var(--dim)}
.barwrap .top button{font-size:12.5px;padding:5px 11px;border-radius:7px}
.bar{display:flex;gap:5px;align-items:flex-end}
.bar .cell{flex:1;border:none;padding:0;background:none;cursor:pointer;text-align:center}
.bar .cell .box{height:19px;border-radius:5px;background:var(--todo);display:flex;
align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#bcc3d0;
transition:.24s}
.bar .cell .nm{font-size:11.5px;color:#aab2c1;margin-top:3px;transition:.2s}
.bar .cell.done .box{background:var(--done);color:#8f97a8}
.bar .cell.now .box{color:#fff}
.bar .cell.now .nm{font-weight:700}
.bar .cell:hover .nm{color:var(--ink)}

/* 낱장 + 누적 패킷 */
.stage{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:16px;margin-top:14px;
align-items:start}
@media(max-width:1240px){.stage{grid-template-columns:minmax(0,1fr)}}
.sheet{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:18px 20px 20px}
.sheet.anim{animation:sheetin .32s ease both}
@keyframes sheetin{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.sheet .head{display:flex;align-items:flex-start;gap:14px;margin-bottom:16px}
.sheet .no{font-size:34px;font-weight:700;line-height:1;letter-spacing:-.03em}
.sheet .ttl{font-size:21px;font-weight:700;padding-top:5px;letter-spacing:-.02em}
.sheet .act{margin-left:auto;text-align:right;padding-top:3px;max-width:44ch}
.sheet .act div{font-size:13.5px;color:var(--dim)}
.sheet .act div:first-child{font-size:14px;color:var(--ink);font-weight:700}

.body{display:grid;grid-template-columns:214px minmax(0,1fr) 26px minmax(0,1fr);
gap:0 12px;align-items:stretch}
/* ★rotate 를 그냥 주면 push 애니메이션의 transform 이 덮어 버려 안 돈다.
   좁은 화면에서는 애니메이션을 끄고 방향만 바꾼다. */
@media(max-width:900px){.body{grid-template-columns:minmax(0,1fr)}
.body .arrow{animation:none;transform:rotate(90deg);height:30px}}
.coord{border:1px solid;border-radius:11px;background:var(--soft);padding:12px 13px}
.coord h4{margin:0 0 10px;font-size:13px}
.coord .row{margin-bottom:13px}
.coord .row:last-child{margin-bottom:0}
.coord .k{font-size:11.5px;color:var(--faint);margin-bottom:1px}
.coord .v{font-size:13px;line-height:1.45}
.doc{border:1px solid var(--line);border-radius:11px;background:var(--soft);
padding:11px 13px 13px;min-width:0}
.doc h4{margin:0 0 8px;font-size:13px;color:var(--dim);display:flex;
align-items:center;gap:7px}
.doc h4 .q{border:1px solid currentColor;border-radius:50%;width:17px;height:17px;
font-size:11px;line-height:15px;text-align:center;cursor:help;opacity:.65;
flex:none;background:none;padding:0;color:inherit}
.doc h4 .q:hover{opacity:1;background:currentColor;color:var(--card)}
.doc .say{display:none;margin:0 0 10px;padding:9px 11px;border-radius:8px;
background:rgba(47,91,216,.08);border-left:3px solid currentColor;
font-size:13px;line-height:1.68;color:var(--ink)}
.doc.open .say{display:block;animation:sheetin .24s ease both}
.doc.out{border-color:currentColor}
.doc.out h4{color:currentColor}
.doc pre{margin:0;font-size:12.8px;line-height:1.72;white-space:pre-wrap;word-break:break-word;
color:var(--ink)}
.doc pre b{font-weight:700;color:currentColor;display:inline-block;
animation:mark .5s ease both;animation-delay:var(--d,0s)}
@keyframes mark{from{opacity:.25;transform:translateX(-5px)}to{opacity:1;transform:none}}
.arrow{display:flex;align-items:center;justify-content:center;font-size:21px;font-weight:700;
color:currentColor;animation:push 1.5s ease-in-out infinite}
@keyframes push{0%,100%{transform:translateX(-3px)}50%{transform:translateX(3px)}}

.states{display:flex;gap:9px;flex-wrap:wrap;margin-top:15px}
.states .chip{border:2px solid;border-radius:9px;padding:6px 15px;font-size:13.5px;
font-weight:700;font-family:Consolas,monospace}
.codeline{margin-top:14px;font-size:12.8px;color:var(--dim);display:flex;gap:9px;
align-items:baseline;flex-wrap:wrap}
.codeline .k{font-size:11.5px;color:var(--faint);font-weight:700}
.codeline .p{font-family:Consolas,monospace}
.why{margin-top:12px;border:1px solid;border-radius:11px;background:var(--warm);
padding:12px 15px;font-size:14.5px}
.files{margin-top:12px;border:1px solid var(--line);border-radius:11px;padding:12px 15px;
font-size:13px}
.files > div{margin:5px 0;color:var(--dim)}
.files b{color:var(--ink)}

/* 누적 패킷 */
.pack{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 17px;
position:sticky;top:98px}
.pack h3{font-size:15px;margin:0 0 3px}
.pack .note{color:var(--dim);font-size:12.5px;margin:0 0 13px}
/* ★scroll-behavior:smooth 를 주면 안 된다. 내용을 갈아 끼운 직후에 scrollTop 을
   넣으면 브라우저가 그 부드러운 스크롤을 취소해 버려서 0 에 그대로 머문다.
   부드러움보다 실제로 내려가는 것이 먼저다. */
.stream{max-height:calc(100vh - 250px);overflow-y:auto;position:relative}
@media(max-width:1240px){.pack{position:static}.stream{max-height:520px}}
.chunk{border:1px solid var(--line);border-radius:10px;margin:0 0 9px;overflow:hidden;
transition:opacity .3s}
.chunk.old{opacity:.62}
.chunk.old:hover{opacity:1}
/* ★이번 단계에서 생긴 것만 도드라지게. 무엇이 새로 붙었는지가 이 칸의 요점이다. */
.chunk.new{border:2px solid currentColor;animation:pop2 .42s ease both}
.chunk.new .h{background:currentColor}
.chunk.new .kind{background:rgba(255,255,255,.9);border-color:transparent;color:#1a2030}
.chunk.new .nm,.chunk.new .fr{color:#fff}
.chunk.new .tag{font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:5px;
background:rgba(255,255,255,.9);color:#1a2030;white-space:nowrap}
@keyframes pop2{0%{opacity:0;transform:translateY(16px) scale(.98)}
60%{transform:translateY(0) scale(1.015)}100%{opacity:1;transform:none}}
.chunk .h{display:flex;gap:8px;align-items:baseline;padding:6px 11px;
background:rgba(127,140,170,.09);border-bottom:1px solid var(--line)}
.chunk .kind{font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:5px;
background:var(--bg);border:1px solid var(--line);color:var(--dim);white-space:nowrap}
.chunk .nm{font-size:12.8px;font-weight:700;font-family:Consolas,monospace}
.chunk .fr{margin-left:auto;font-size:11px;color:var(--faint);white-space:nowrap}
.chunk pre{margin:0;padding:8px 11px;font-size:12.2px;line-height:1.6;white-space:pre-wrap;
word-break:break-word;color:var(--ink)}

/* 줄마다 주석. 마우스를 올린 줄에만 뜬다. */
.ln{display:block;position:relative;border-radius:4px;padding:0 3px;margin:0 -3px}
.ln.has{cursor:help}
.ln.has:hover{background:rgba(47,91,216,.12)}
.ln.has:hover::after{content:attr(data-note);position:absolute;left:0;bottom:calc(100% + 5px);
z-index:70;white-space:normal;width:max-content;max-width:min(430px,88vw);
background:var(--ink);color:#fff;font-family:"Malgun Gothic",system-ui,sans-serif;
font-size:12.5px;line-height:1.5;padding:6px 10px;border-radius:7px;
box-shadow:0 8px 22px rgba(8,12,22,.34);pointer-events:none}
.ln.has:hover::before{content:"";position:absolute;left:14px;bottom:calc(100% + 1px);
z-index:70;border:5px solid transparent;border-top-color:var(--ink);pointer-events:none}
/* 위쪽 줄은 말풍선이 잘리므로 아래로 편다. */
.ln.has.down:hover::after{bottom:auto;top:calc(100% + 5px)}
.ln.has.down:hover::before{bottom:auto;top:calc(100% + 1px);
border-top-color:transparent;border-bottom-color:var(--ink)}
.src pre .ln.has:hover{background:rgba(255,255,255,.14)}
.notehint{font-size:11.5px;color:var(--faint);padding:0 11px 7px}
.src .notehint{padding:7px 18px 0}
.badge{display:flex;gap:9px;align-items:center;margin-top:12px;font-size:13px;color:var(--dim)}
.badge b{font-family:Consolas,monospace;font-size:15px;padding:4px 12px;border-radius:8px;
border:2px solid var(--blue);color:var(--blue)}
.badge b.done{border-color:var(--green);color:var(--green)}

/* 덮어 띄우는 것들 */
.ov{position:fixed;inset:0;background:rgba(8,11,18,.76);display:none;z-index:60;
padding:30px 20px;overflow-y:auto}
.ov.on{display:block}
.ovbox{max-width:1180px;margin:0 auto;background:var(--card);border:1px solid var(--line);
border-radius:14px;overflow:hidden}
.ovhead{display:flex;align-items:center;gap:12px;padding:13px 18px;
border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--card);z-index:2}
.ovhead h3{margin:0;font-size:17px}
.ovhead .x{margin-left:auto}
.src{border-top:1px solid var(--line)}
.src .path{padding:8px 18px;font-family:Consolas,monospace;font-size:12.5px;color:var(--dim);
background:rgba(127,140,170,.09)}
.src pre{margin:0;padding:14px 18px;background:var(--code-bg);color:var(--code-ink);
font-size:13px;line-height:1.66;overflow-x:auto;white-space:pre}
.plain{padding:14px 20px 18px;font-size:14.3px;line-height:1.82;
border-top:3px solid var(--blue);background:rgba(47,91,216,.055)}
.plain .lbl{display:inline-block;font-size:11.5px;font-weight:700;color:var(--blue);
border:1px solid var(--blue);border-radius:5px;padding:1px 8px;margin-bottom:9px}
.plain p{margin:0 0 11px}
.plain p:last-child{margin-bottom:0}
.plain code{background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:1px 5px;
font-size:12.8px}

/* 열두 칸 지도. 진행바를 눌러야 뜬다. */
.map{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:18px}
@media(max-width:820px){.map{grid-template-columns:repeat(2,1fr)}}
.st{border:2px solid var(--line);border-radius:12px;padding:11px 12px;background:transparent;
text-align:left;transition:.2s;opacity:.55;cursor:pointer}
.st .n{font-size:12px;color:var(--faint);font-weight:700}
.st .t{font-size:14.5px;font-weight:700;margin:1px 0 2px;color:var(--ink)}
.st .o{font-size:11.5px;color:var(--faint)}
.st.done{opacity:1;border-color:currentColor}
.st.now{opacity:1;background:currentColor;border-color:currentColor}
.st.now .n,.st.now .o{color:rgba(255,255,255,.82)}
.st.now .t{color:#fff}

/* 그림 열아홉 장 */
figure{margin:18px 0 0;background:var(--card);border:1px solid var(--line);border-radius:14px;
overflow:hidden}
figure img{display:block;width:100%;height:auto}
figcaption{padding:14px 20px 17px;border-top:1px solid var(--line)}
figcaption b{display:block;font-size:16px;margin-bottom:4px}
figcaption span{color:var(--dim);font-size:14px}
nav.jump{background:var(--bg);border-bottom:1px solid var(--line);padding:10px 0;
overflow-x:auto;white-space:nowrap}
nav.jump a{display:inline-block;padding:5px 11px;margin-right:3px;font-size:12.5px;
color:var(--dim);text-decoration:none;border:1px solid var(--line);border-radius:99px}
nav.jump a:hover{color:var(--blue);border-color:var(--blue)}

/* 떠 있는 조작 단추 */
.dock{position:fixed;right:20px;bottom:20px;z-index:40;display:flex;flex-direction:column;
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

figure{scroll-margin-top:120px}   /* ★위에 붙은 진행바가 제목을 덮지 않게 */
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms !important;
    animation-iteration-count:1 !important;transition-duration:.01ms !important}
}
.foot{margin-top:38px;padding-top:20px;border-top:1px solid var(--line);color:var(--dim);
font-size:13px}
"""

JS = r"""
const BAR = __BAR__, SHEETS = __SHEETS__, PACK = __PACK__, NOTE = __NOTE__;
let cur = 0, timer = null;
const $ = id => document.getElementById(id);
// ★title="..." 안에도 들어간다. 따옴표를 안 막으면 제목에 " 하나로 속성이 깨진다.
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');

function drawBar(){
  $('bar').innerHTML = BAR.map((b,i) =>
    '<button class="cell '+(i===cur?'now':(i<cur?'done':''))+'" onclick="go('+i+')"'
    + ' title="'+esc(SHEETS[i].head)+'">'
    + '<div class="box"'+(i===cur?' style="background:'+b.color+'"':'')+'>'+(i+1)+'</div>'
    + '<div class="nm"'+(i===cur?' style="color:'+b.color+'"':'')+'>'+esc(b.name)+'</div>'
    + '</button>').join('');
}

// ★pre 안의 글을 줄 단위 span 으로 쪼갠다. 주석이 있는 줄만 has 를 붙인다.
//   위에서 두 줄 안쪽은 말풍선이 잘리므로 아래로 펴게 down 을 준다.
function lined(lines, notes){
  return lines.map((l,i) => {
    const t = esc(l) || ' ';
    const n = notes && notes[i];
    if(!n) return '<span class="ln">'+t+'</span>';
    return '<span class="ln has'+(i<2?' down':'')+'" data-note="'+esc(n)+'">'+t+'</span>';
  }).join('');
}

// 문서 칸 하나. 제목 옆 물음표를 누르면 이 칸이 무엇인지 펼쳐진다.
function oneDoc(cls, label, lines, mark, say){
  return '<div class="doc'+cls+(say?' open':'')+'">'
    + '<h4>'+esc(label)
    + (say?'<button class="q" onclick="tellDoc(this)" title="이 칸이 무엇인지">?</button>':'')
    + '</h4>'
    + (say?'<div class="say">'+esc(say)+'</div>':'')
    + '<pre>'+docLines(lines, mark)+'</pre></div>';
}
function tellDoc(el){ el.closest('.doc').classList.toggle('open'); }

function docLines(lines, mark){
  return lines.map((l,i) => {
    const t = esc(l) || ' ';
    if(!mark.includes(i)) return t;
    const d = (mark.indexOf(i) * 0.09 + 0.16).toFixed(2);
    return '<b style="--d:'+d+'s">'+t+'</b>';
  }).join('\n');
}

function drawSheet(){
  const s = SHEETS[cur];
  const coord = s.coord.map(r =>
    '<div class="row"><div class="k">'+esc(r[0])+'</div>'
    + r[1].map(v=>'<div class="v">'+esc(v)+'</div>').join('') + '</div>').join('');
  const el = $('sheet');
  el.style.color = s.color;
  el.innerHTML =
    '<div class="head"><div class="no" style="color:'+s.color+'">'
    + String(s.n).padStart(2,'0')+'</div><div class="ttl">'+esc(s.head)+'</div>'
    + '<div class="act">'+s.action.map(a=>'<div>'+esc(a)+'</div>').join('')+'</div></div>'
    + '<div class="body">'
    +   '<div class="coord" style="border-color:'+s.color+'">'
    +     '<h4 style="color:'+s.color+'">구조 좌표</h4>'+coord+'</div>'
    +   oneDoc('', s.in_label, s.in_lines, [], s.in_say)
    +   '<div class="arrow">&#10142;</div>'
    +   oneDoc(' out', s.out_label, s.out_lines, s.mark, s.out_say)
    + '</div>'
    + '<div class="states">'+s.states.map(c =>
        '<span class="chip" style="color:'+c[1]+'">'+esc(c[0])+'</span>').join('')+'</div>'
    + '<div class="codeline"><span class="k">코드</span>'
    +   '<span class="p">'+esc(s.code)+'</span></div>'
    + '<div class="why" style="border-color:'+s.color+'">'+esc(s.why)+'</div>'
    + '<div class="files">'+NOTE.map(x =>
        '<div><b>'+esc(x[0])+'</b> '+esc(x[1])+'</div>').join('')+'</div>';
  el.classList.remove('anim');
  void el.offsetWidth;
  el.classList.add('anim');
}

function drawPack(){
  let out = '', fresh = 0;
  for(let i=0;i<=cur;i++){
    const now = i===cur;
    for(const part of PACK[i].add){
      if(now) fresh++;
      out += '<div class="chunk '+(now?'new':'old')+'"'
          +  (now?' style="color:'+SHEETS[cur].color+'"':'')+'>'
          +  '<div class="h"><span class="kind">'+esc(part[0])+'</span>'
          +  '<span class="nm">'+esc(part[1])+'</span>'
          +  (now?'<span class="tag">이번에 생김</span>':'')
          +  '<span class="fr">'+PACK[i].n+'번</span></div><pre>'
          +  lined(part[2], part[3])+'</pre>'
          +  (part[3] ? '<div class="notehint">줄에 마우스를 올리면 그 줄 설명이 뜹니다</div>' : '')
          +  '</div>';
    }
  }
  $('fresh').textContent = fresh
    ? (cur+1)+'번 단계에서 '+fresh+'개가 새로 붙었습니다. 색이 들어온 것이 그것입니다.'
    : (cur+1)+'번 단계는 새로 만드는 것 없이 지나갑니다.';
  $('stream').innerHTML = out
    || '<div style="color:var(--faint);font-size:13px">아직 아무것도 안 만들어졌습니다.</div>';
  let st = null;
  for(let i=0;i<=cur;i++) if(PACK[i].state) st = PACK[i].state;
  $('badge').innerHTML = st
    ? 'Case 상태 <b class="'+(st[0]==='resolved'?'done':'')+'">'+st[0]+'  v'+st[1]+'</b>'
    : 'Case 상태 <span style="color:var(--faint)">아직 Case 가 없습니다</span>';
  // ★scrollIntoView 를 쓰지 않는다. 그것은 페이지까지 같이 움직여서
  //   위에 붙어 있는 진행바가 새 덩어리를 덮는다. 이 칸만 내린다.
  // ★offsetTop 을 쓰지 않는다. .pack 이 sticky 라 그것이 offsetParent 가 되고,
  //   머리 높이만큼 어긋난다. 화면 좌표로 재는 것이 어느 배치에서나 맞다.
  // ★scrollTo({behavior:'smooth'}) 도 쓰지 않는다. 방금 innerHTML 을 갈아 끼운
  //   직후라 애니메이션이 취소되고 0 에 머문다. scrollTop 에 바로 넣고,
  //   부드러움은 CSS scroll-behavior 가 맡는다.
  const news = $('stream').querySelectorAll('.chunk.new');
  if(news.length){
    const box = $('stream'), last = news[news.length-1];
    const bt = box.getBoundingClientRect(), lt = last.getBoundingClientRect();
    box.scrollTop = Math.max(0, box.scrollTop + (lt.bottom - bt.bottom) + 12);
  }
}

function render(){
  drawBar(); drawSheet(); drawPack();
  $('tick').textContent = (cur+1)+' / '+SHEETS.length+' 단계';
  $('fabn').textContent = String(cur+1);
  $('fabs').textContent = '/ '+SHEETS.length;
  $('prev').disabled = cur<=0;
  $('next').disabled = cur>=SHEETS.length-1;
  if($('mapov').classList.contains('on')) drawMap();
}

function go(i){ cur = Math.max(0, Math.min(SHEETS.length-1, i)); render(); }
function play(){
  if(timer){ clearInterval(timer); timer=null; $('play').textContent='자동 재생'; return; }
  if(cur>=SHEETS.length-1) go(0);   // ★cur=0 만 하면 화면이 안 바뀌어 1번을 건너뛴다
  $('play').textContent='멈춤';
  timer = setInterval(()=>{ if(cur>=SHEETS.length-1){ play(); return; } go(cur+1); }, 3200);
}

function drawMap(){
  $('mapbody').innerHTML = SHEETS.map((s,i) =>
    '<button class="st '+(i===cur?'now':(i<cur?'done':''))+'" style="color:'+s.color+'"'
    + ' onclick="go('+i+');hideMap()"><div class="n">'+s.n+'</div>'
    + '<div class="t">'+esc(s.head)+'</div>'
    + '<div class="o">'+esc(PACK[i].owner)+'</div></button>').join('');
}
function showMap(){ stop(); drawMap(); $('mapov').classList.add('on'); $('mapov').scrollTop=0; }
function hideMap(){ $('mapov').classList.remove('on'); }

function stop(){ if(timer){ clearInterval(timer); timer=null; $('play').textContent='자동 재생'; } }

function showCode(){
  stop();                          // ★열어 둔 코드와 뒤에서 도는 단계가 어긋난다
  $('dock').classList.remove('on');
  const s = PACK[cur];
  $('ovtitle').textContent = s.n+'번 단계 · '+s.title+' · 이 일을 실제로 하는 코드';
  $('ovbody').innerHTML = s.code.map(c =>
    '<div class="src"><div class="path">'+esc(c.path)+'</div>'
    +(c.notes ? '<div class="notehint">줄에 마우스를 올리면 그 줄 설명이 뜹니다</div>' : '')
    +'<pre>'+lined(c.code.split('\n'), c.notes)+'</pre>'
    +'<div class="plain"><span class="lbl">쉬운 풀이</span>'
    + c.plain.split('\n\n').map(p=>'<p>'+p+'</p>').join('')
    +'</div></div>').join('');
  $('ov').classList.add('on');
  $('ov').scrollTop = 0;
}
function hideCode(){ $('ov').classList.remove('on'); }

function dock(e){ if(e) e.stopPropagation(); $('dock').classList.toggle('on'); }
document.addEventListener('click', e=>{
  const d = $('dock');
  if(d.classList.contains('on') && !d.contains(e.target)) d.classList.remove('on');
});
// ★키를 문서 전체에서 뺏지 않는다. 위아래 화살표와 Space 와 Home/End 를 다 막으면
//   페이지를 키보드로 굴릴 수 없고, 단추에 초점이 있어도 단계가 넘어간다.
//   좌우 화살표만 어디서나 받고, 나머지는 글자를 입력하는 곳이 아닐 때만 받는다.
function typing(el){
  return el && (el.isContentEditable ||
    /^(INPUT|TEXTAREA|SELECT|BUTTON|A)$/.test(el.tagName));
}
document.addEventListener('keydown', e=>{
  if(e.key==='Escape'){ hideCode(); hideMap(); return; }
  if($('ov').classList.contains('on') || $('mapov').classList.contains('on')) return;
  if(e.altKey || e.ctrlKey || e.metaKey) return;
  if(e.key==='ArrowRight'){ e.preventDefault(); go(cur+1); }
  else if(e.key==='ArrowLeft'){ e.preventDefault(); go(cur-1); }
  else if(!typing(e.target)){
    if(e.key===' '){ e.preventDefault(); play(); }
    else if(e.key==='Home'){ e.preventDefault(); go(0); }
    else if(e.key==='End'){ e.preventDefault(); go(SHEETS.length-1); }
  }
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
낱장의 글자는 그림이 아니라 글자입니다. 긁어서 복사할 수 있습니다.</p>

<h2 class="sec">한 단계씩 따라가기</h2>
<p>왼쪽이 그 단계의 구조 좌표, 가운데가 들어온 문서와 나간 문서, 오른쪽이 지금까지 쌓인 것입니다.
바뀐 줄에만 색이 붙습니다. 위쪽 진행바의 칸을 누르면 그 단계로 갑니다. 좌우 화살표 키도 됩니다.</p>

<div class="barwrap">
  <div class="top">
    <span class="t">열두 단계 진행바</span>
    <span class="r">
      <span class="keys"><kbd>&#8592;</kbd><kbd>&#8594;</kbd> 앞뒤로
        <kbd>Space</kbd> 자동 재생 <kbd>Esc</kbd> 닫기</span>
      <button onclick="showMap()">열두 칸 지도 펼치기</button>
      <button onclick="showCode()">이 단계 코드 보기</button>
    </span>
  </div>
  <div class="bar" id="bar"></div>
</div>

<div class="stage">
  <div class="sheet" id="sheet"></div>
  <div class="pack">
    <h3>지금까지 만들어진 것</h3>
    <p class="note" id="fresh"></p>
    <div class="stream" id="stream"></div>
    <div class="badge" id="badge"></div>
  </div>
</div>

<h2 class="sec">그림으로 펴 보기</h2>
<p>같은 내용을 한 장씩 그림으로 편 것입니다.
위 열두 장에 더해 구조와 갈림길과 파일 이야기가 들어 있습니다.</p>
<nav class="jump">%(links)s</nav>
%(figures)s

<div class="foot">코드는 <code>final_project_cs</code> 에서 줄 번호로 잘라 온 실제 코드입니다.
손으로 옮겨 적지 않았습니다. 낱장의 내용도 그림을 그리는
<code>program/onboarding/trace/steps.py</code> 에서 그대로 가져옵니다.
그림과 화면이 어긋날 수 없습니다.<br>
이 파일은 <code>program/onboarding/build_trace_html.py</code> 가 만듭니다. 손으로 고치지 마세요.</div>
</div>

<div class="ov" id="mapov" onclick="if(event.target===this)hideMap()">
  <div class="ovbox">
    <div class="ovhead"><h3>열두 단계 지도</h3>
      <button class="x" onclick="hideMap()">닫기 (Esc)</button></div>
    <div class="map" id="mapbody"></div>
  </div>
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
    <button onclick="go(0)">처음으로</button>
    <button onclick="showMap()">열두 칸 지도</button>
    <button onclick="showCode()">이 단계 코드 보기</button>
    <div class="tick" id="tick"></div>
  </div>
  <button class="fab" onclick="dock(event)" title="조작판">
    <span class="big" id="fabn">1</span><span class="small" id="fabs">/ 12</span>
  </button>
</div>

<script>%(js)s</script></body></html>
"""
