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
--code-bg:#0f141f;--code-ink:#dbe3f0;--done:#e2e6ee;--todo:#f2f4f8;--amber:#a8720c}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#11141b;--card:#181c25;--soft:#1d222c;--line:#2a303d;--ink:#e7eaf2;--dim:#98a2b8;
--faint:#6d778c;--warm:#211d14;
--red:#e08063;--blue:#7fa1f7;--green:#4bb489;--purple:#a888e0;--grey:#98a2b8;
--done:#2b3140;--todo:#20252f;--amber:#d8a445}}
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
/* 진행바 위에 있던 줄은 없앴다. 버튼 둘이 플로팅 독에 그대로 있어 중복이었고,
   좁은 화면에서 글자가 세로로 서서 읽히지도 않았다. 지금 상태와 단축키
   안내만 독 안으로 옮겼다. */
.dock .barstate{font-size:12px;color:var(--dim);line-height:1.5;
padding:0 2px 8px;border-bottom:1px solid var(--line);margin-bottom:2px}
.dock .barstate b{font-family:Consolas,monospace;font-size:12.5px;color:var(--ink);
display:block;margin-top:2px}
.dock .keys{border-top:1px solid var(--line);margin-top:2px;padding-top:8px;
flex-wrap:wrap;justify-content:center}
.keys{font-size:11.5px;color:var(--faint);display:flex;gap:5px;align-items:center;
margin-right:4px}
.keys kbd{font-family:Consolas,monospace;font-size:11px;border:1px solid var(--line);
border-bottom-width:2px;border-radius:4px;padding:1px 5px;background:var(--bg);color:var(--dim)}
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
/* ★기본은 접어 둔다. 스물넷을 다 펴 두면 정작 문서가 밀린다.
   물음표에 마우스를 올리면 뜨고, 누르면 고정된다. */
.doc .say{display:none;margin:0 0 10px;padding:9px 11px;border-radius:8px;
background:rgba(47,91,216,.08);border-left:3px solid currentColor;
font-size:13px;line-height:1.68;color:var(--ink)}
.doc:has(.q:hover) .say,.doc.open .say{display:block;animation:sheetin .2s ease both}
.doc.open .q{opacity:1;background:currentColor;color:var(--card)}
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
/* 생명주기 상태. 영어 그대로 적는다. 코드와 DB 에 그 글자로 들어 있다. */
.st .stt{font-family:Consolas,monospace;font-size:12px;font-weight:700;margin-top:5px;
padding-top:5px;border-top:1px dashed var(--line);color:currentColor}
.st.now .stt{color:#fff;border-top-color:rgba(255,255,255,.45)}
.st.done{opacity:1;border-color:currentColor}
.st.now{opacity:1;background:currentColor;border-color:currentColor}
.st.now .n,.st.now .o{color:rgba(255,255,255,.82)}
.st.now .t{color:#fff}

/* 그림 대신 HTML 로 그리는 판들 */
.plate{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:20px 22px;margin:18px 0 0}
.plate > h3{font-size:19px;margin:0 0 4px}
.plate > p.sub2{color:var(--dim);font-size:14px;margin:0 0 16px;max-width:96ch}
.plate .foot2{margin-top:14px;font-size:13px;color:var(--dim)}
.plate .warn{margin:0 0 14px;padding:11px 14px;border-radius:10px;background:var(--warm);
border:1px solid var(--amber);font-size:14px}
/* 배너로 쓸 때는 굵게. 원본 그림에서 이 한 줄만 굵은 글씨였다. */
.plate .warn > b{font-weight:700;display:block}
/* 여러 줄짜리 상자. 제목 한 줄 아래 근거가 붙는다. */
.plate .warn.soft{margin:14px 0 0}
.plate .warn.soft > b{margin-bottom:7px}
.plate .warn.soft > span{display:block;font-size:13px;color:var(--dim);
margin-top:5px;line-height:1.66}

/* 두 기둥. 왼쪽 위아래가 한 짝, 오른쪽 위아래가 다른 한 짝이다.
   격자에 그냥 흘리면 순서가 가로로 꺾여 그 짝이 깨진다. */
.twocol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.col2{display:flex;flex-direction:column;gap:14px}
@media(max-width:900px){.twocol{grid-template-columns:minmax(0,1fr)}}

/* 전체 지도. 칸마다 따로 떼고 사이를 벌린다. 원본 그림이 그랬고,
   붙여 놨더니 연달아 오는 단계가 한 칸처럼 읽혔다. */
.lanes{display:grid;grid-template-columns:150px repeat(12,minmax(0,1fr));
gap:8px 5px;align-items:stretch}
.lanes .name{border:2px solid;border-radius:11px;display:flex;align-items:center;
justify-content:center;font-size:12px;font-weight:700;padding:10px 6px;
text-align:center;margin-right:9px;word-break:keep-all}
.lanes .cell{min-height:56px;display:flex;align-items:center;justify-content:center}
.lanes .cell > i{display:block;height:8px;width:100%;background:var(--todo);
border-radius:4px}
.lanes .cell.on{color:#fff;flex-direction:column;gap:2px;padding:8px 2px;
text-align:center;justify-content:center;border-radius:10px}
.lanes .cell.on b{font-size:15px;line-height:1.1}
.lanes .cell.on span{font-size:11px;line-height:1.2;opacity:.94;word-break:keep-all}
/* 좁아지면 글자가 한 자씩 세로로 선다. 그 전에 옆으로 밀리게 한다. */
@media(max-width:1000px){.lanes{min-width:840px}
.lanes .name{font-size:11px}.lanes .cell.on b{font-size:13.5px}
.lanes .cell.on span{font-size:10px}}

/* 큰 구조 / 파일 이름 / 남는 표 */
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
@media(max-width:900px){.cards{grid-template-columns:minmax(0,1fr)}}
.card{border:2px solid;border-radius:12px;padding:13px 15px}
.card h4{margin:0 0 2px;font-size:14.5px}
.card .cs{font-size:12.5px;color:var(--dim);margin:0 0 10px}
.card .it{display:flex;gap:9px;align-items:baseline;font-size:13.5px;padding:2px 0}
.card .it .dot{flex:none;font-size:11px;line-height:1.6}
.card .it .nm2{flex:1;min-width:0}
.card .it .no2{font-size:12.5px;text-align:right;white-space:nowrap}
/* 줄바꿈을 허용한 메모는 왼쪽에 맞춘다. 오른쪽 정렬이면 줄마다 시작점이 달라진다. */
.card .it .no2.free{text-align:left;white-space:normal;color:var(--dim);flex:1.2}
/* ★이름 칸은 글자만큼만 잡는다. flex 로 반씩 나누면 짧은 이름 뒤에
   200px 짜리 빈 자리가 남아 두 칸이 따로 노는 표처럼 보인다.
   실측한 가장 긴 이름에 맞춘 폭이다. */
.card .it .nm2.mono{font-family:Consolas,monospace;flex:0 1 auto;
width:452px;max-width:52%}
.card .it .nm2.mono.narrow{width:200px;max-width:40%}
/* ★이름 칸을 줄마다 같은 폭으로 맞추면 짧은 이름 뒤에 빈 자리가 남는다.
   그 자리를 없앨 수는 없다. 대신 줄을 그어 한 줄이 한 짝이라고 보이게 한다.
   선이 없으면 왼쪽 목록과 오른쪽 목록이 따로 노는 것처럼 읽힌다. */
.card .it.line{border-bottom:1px solid var(--line);padding:8px 2px}
.card .it.line:last-child{border-bottom:none}
/* 좁아지면 두 칸을 위아래로 쌓는다. 옆으로 붙이면 이름이 한 자씩 접힌다. */
@media(max-width:760px){
.card .it{flex-direction:column;align-items:stretch;gap:2px;padding:7px 0;
border-bottom:1px solid var(--line)}
.card .it:last-child{border-bottom:none}
/* ★위아래로 쌓을 때는 flex 를 꺼야 한다. flex-grow 가 남아 있으면 두 줄짜리
   설명이 세로로 늘어나 칸 하나가 190px 를 먹는다. */
.card .it .nm2,.card .it .nm2.mono,.card .it .nm2.mono.narrow,
.card .it .no2,.card .it .no2.free{flex:none;width:auto;
text-align:left;white-space:normal}}
.card .it .nm2{overflow-wrap:anywhere}
/* "왜 헷갈리나" 는 원본에서 회색 바탕 상자였다. 본문과 구별되는 자리다. */
.card.why2b{border-color:var(--line);margin-top:14px;background:var(--soft)}
.card .it.off{color:var(--faint)}
.card .it.off .nm2{color:var(--faint)}
.card pre{margin:0;font-size:12.5px;line-height:1.62;white-space:pre-wrap;
word-break:break-word}

/* 상태 12개를 상태 기계 그림으로 그린다. 그림 파일이 아니라 SVG 라
   글자를 긁을 수 있다. 색은 테마를 따라간다. */
.sd{display:block;min-width:920px;width:100%;height:auto}
.sd .bx{fill:var(--card);stroke-width:2}
.sd .bx.bl{stroke:var(--blue)}
.sd .bx.gr{stroke:var(--green);stroke-width:2.4}
.sd .bx.am{stroke:var(--amber);fill:var(--warm)}
.sd .nm{font-family:Consolas,monospace;font-size:14px;font-weight:700;
text-anchor:middle}
.sd .nm.bl{fill:var(--blue)}
.sd .nm.gr{fill:var(--green)}
.sd .nm.am{fill:var(--amber)}
.sd .sb{font-size:10.5px;fill:var(--dim);text-anchor:middle}
.sd .ln{fill:none;stroke-width:1.7}
.sd .ln.bl{stroke:var(--dim)}
.sd .ln.am{stroke:var(--amber)}
.sd marker.bl path{fill:var(--dim)}
.sd marker.am path{fill:var(--amber)}
.sd .ed{font-family:Consolas,monospace;font-size:10.5px;fill:var(--faint)}
.sd .no{font-size:11px;fill:var(--dim)}
.sd .ok{font-size:11px;fill:var(--green)}
.sd .note{fill:var(--soft);stroke:var(--line)}
.sd .nt{font-size:12.5px;fill:var(--ink)}
.sd .src{font-size:11px;fill:var(--faint)}

.ar{font-size:19px;color:var(--faint);flex:none;line-height:1}
.ar.up{transform:rotate(-90deg);display:inline-block;color:var(--amber)}
.ar.down{transform:rotate(90deg);display:inline-block;color:var(--blue)}
.ar.mid{align-self:center;color:var(--dim)}
.downto{display:flex;gap:9px;align-items:center;font-size:13.5px;font-weight:700;
color:var(--blue);margin:14px 0 8px}

/* 전달 문서 다섯 */
.docs5{display:flex;gap:6px;align-items:stretch}
.docs5 .d5{flex:1;min-width:0}
@media(max-width:1000px){.docs5{flex-wrap:wrap}.docs5 .d5{flex:1 1 44%}
.docs5 .ar.mid{display:none}}
.docs5 .d5{border:2px solid;border-radius:12px;padding:11px 12px}
.docs5 .d5 b{font-size:14px}
.docs5 .d5 .at{font-size:11.5px;color:var(--faint);display:block;margin-bottom:7px}
.docs5 .d5 div.f{font-family:Consolas,monospace;font-size:12.5px;padding:1px 0}
.docs5 .d5 div.note2{font-size:12px;color:var(--dim);margin-top:7px}

/* 갈림길 표 */
/* ★좁은 화면에서 네 열이 안 들어간다. 판을 넘치게 두지 않고 표만 굴린다. */
.plate .scroll{overflow-x:auto}
table.br{width:100%;min-width:560px;border-collapse:collapse;font-size:13.5px}
table.br th{text-align:left;font-size:12px;color:var(--faint);font-weight:700;
padding:0 10px 7px 0;border-bottom:1px solid var(--line)}
table.br td{padding:9px 10px 9px 0;border-bottom:1px solid var(--line);
vertical-align:top}
table.br td.at2{white-space:nowrap;font-weight:700;font-size:12.5px}
table.br td.then{font-family:Consolas,monospace;font-size:12.5px}
table.br td.why2{color:var(--dim)}


/* 떠 있는 조작 단추 */
.dock{position:fixed;right:20px;bottom:20px;z-index:40;display:flex;flex-direction:column;
align-items:flex-end;gap:11px}
.dock .menu{display:none;flex-direction:column;gap:7px;background:var(--card);
border:1px solid var(--line);border-radius:15px;padding:12px;min-width:216px;
box-shadow:0 16px 44px rgba(8,12,22,.26);animation:pop .18s ease both}
.dock.on .menu{display:flex}
@keyframes pop{from{opacity:0;transform:translateY(12px) scale(.96)}to{opacity:1;transform:none}}
.dock .menu button{width:100%;text-align:left;display:flex;align-items:center;gap:8px}
/* 단추 안 오른쪽 끝의 단축키 표시 */
.dock .menu button .sk{margin-left:auto;font-family:Consolas,monospace;font-size:10.5px;
border:1px solid var(--line);border-radius:5px;padding:1px 5px;color:var(--faint);
background:var(--soft)}
.dock .menu button.primary .sk{border-color:rgba(255,255,255,.45);color:#fff;
background:rgba(255,255,255,.16)}
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

.plate{scroll-margin-top:120px}   /* ★위에 붙은 진행바가 제목을 덮지 않게 */
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
  const st = stateAt(cur);
  $('barstate').innerHTML = st
    ? '이 단계를 지나면 Case 는 <b>'+st[0]+'  v'+st[1]+'</b>'
    : '아직 Case 가 없습니다';
}

// ★pre 안의 글을 줄 단위 span 으로 쪼갠다. 주석이 있는 줄만 has 를 붙인다.
//   위에서 두 줄 안쪽은 말풍선이 잘리므로 아래로 펴게 down 을 준다.
function lined(lines, notes, mark){
  mark = mark || [];
  return lines.map((l,i) => {
    let t = esc(l) || ' ';
    if(mark.includes(i)){
      const d = (mark.indexOf(i) * 0.09 + 0.16).toFixed(2);
      t = '<b style="--d:'+d+'s">'+t+'</b>';
    }
    const n = notes && notes[i];
    if(!n) return '<span class="ln">'+t+'</span>';
    return '<span class="ln has'+(i<2?' down':'')+'" data-note="'+esc(n)+'">'+t+'</span>';
  }).join('');
}

// 문서 칸 하나. 제목 옆 물음표를 누르면 이 칸이 무엇인지 펼쳐진다.
function oneDoc(cls, label, lines, mark, say, notes){
  return '<div class="doc'+cls+'">'
    + '<h4>'+esc(label)
    + (say?'<button class="q" onclick="tellDoc(this)"'
        + ' title="이 칸이 무엇인지. 눌러 두면 고정됩니다">?</button>':'')
    + '</h4>'
    + (say?'<div class="say">'+esc(say)+'</div>':'')
    + (notes ? '<div class="notehint">줄에 마우스를 올리면 그 줄 설명이 뜹니다</div>' : '')
    + '<pre>'+lined(lines, notes, mark)+'</pre></div>';
}
function tellDoc(el){ el.closest('.doc').classList.toggle('open'); }


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
    +   oneDoc('', s.in_label, s.in_lines, [], s.in_say, s.in_notes)
    +   '<div class="arrow">&#10142;</div>'
    +   oneDoc(' out', s.out_label, s.out_lines, s.mark, s.out_say, s.out_notes)
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
  if(timer){ clearInterval(timer); timer=null; setPlayLabel('자동 재생'); return; }
  if(cur>=SHEETS.length-1) go(0);   // ★cur=0 만 하면 화면이 안 바뀌어 1번을 건너뛴다
  setPlayLabel('멈춤');
  timer = setInterval(()=>{ if(cur>=SHEETS.length-1){ play(); return; } go(cur+1); }, 3200);
}

// 그 단계를 지난 뒤의 Case 상태. 상태를 안 바꾸는 단계는 앞의 것을 그대로 쓴다.
function stateAt(i){
  let st = null;
  for(let k=0;k<=i;k++) if(PACK[k].state) st = PACK[k].state;
  return st;
}
function drawMap(){
  $('mapbody').innerHTML = SHEETS.map((s,i) => {
    const st = stateAt(i);
    return '<button class="st '+(i===cur?'now':(i<cur?'done':''))+'" style="color:'+s.color+'"'
    + ' onclick="go('+i+');hideMap()"><div class="n">'+s.n+'</div>'
    + '<div class="t">'+esc(s.head)+'</div>'
    + '<div class="o">'+esc(PACK[i].owner)+'</div>'
    + '<div class="stt">'+(st ? st[0]+'  v'+st[1] : 'Case 없음')+'</div></button>';
  }).join('');
}
function showMap(){ stop(); hideCode(); drawMap(); $('mapov').classList.add('on'); $('mapov').scrollTop=0; }
function hideMap(){ $('mapov').classList.remove('on'); }

function stop(){ if(timer){ clearInterval(timer); timer=null; setPlayLabel('자동 재생'); } }
// ★textContent 로 통째로 바꾸면 단추 안의 단축키 표시가 지워진다.
function setPlayLabel(text){
  $('play').innerHTML = esc(text)+' <span class="sk">Space</span>';
}

function showCode(){
  stop();                          // ★열어 둔 코드와 뒤에서 도는 단계가 어긋난다
  hideMap();
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
//   페이지를 키보드로 굴릴 수 없다. 좌우 화살표만 어디서나 받고, 나머지는
//   글자를 넣는 곳이 아닐 때만 받는다.
function editing(el){
  return !!el && (el.isContentEditable ||
    /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
}
// ★전에는 여기에 BUTTON 과 A 도 넣어 두었다. 그래서 진행바 칸이나 독 단추를
//   마우스로 한 번이라도 누르면 그 단추에 초점이 남아 Space 가 자동 재생까지
//   가지 못했다. 브라우저가 그 단추를 다시 누를 뿐이라 아무 일도 안 일어난 것처럼
//   보였다. 초점을 키보드로 옮긴 경우에만 단추에 Space 를 양보한다.
function keyFocused(el){
  try { return !!el && el.matches(':focus-visible'); } catch(_) { return false; }
}
function toggleCode(){ $('ov').classList.contains('on') ? hideCode() : showCode(); }
function toggleMap(){ $('mapov').classList.contains('on') ? hideMap() : showMap(); }
document.addEventListener('keydown', e=>{
  if(e.key==='Escape'){ hideCode(); hideMap(); return; }
  if(e.altKey || e.ctrlKey || e.metaKey) return;
  const k = e.key.length===1 ? e.key.toLowerCase() : e.key;
  // ★c 와 m 은 덮개가 열려 있어도 받는다. 같은 키로 열고 닫는다.
  if((k==='c' || k==='m') && !editing(e.target)){
    e.preventDefault();
    if(k==='c') toggleCode(); else toggleMap();
    return;
  }
  if($('ov').classList.contains('on') || $('mapov').classList.contains('on')) return;
  if(e.key==='ArrowRight'){ e.preventDefault(); go(cur+1); }
  else if(e.key==='ArrowLeft'){ e.preventDefault(); go(cur-1); }
  else if(!editing(e.target)){
    if(e.key===' '){
      if(keyFocused(e.target)) return;   // 탭으로 간 단추는 Space 로 눌리게 둔다
      e.preventDefault(); play();
    }
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

<h2 class="sec">낱장 말고 나머지</h2>
<p>전체 지도, 큰 구조, 상태 열두 개, 전달 문서, 갈림길, 남는 표, 파일 이름.
그림이 아니라 글자라 긁어서 복사할 수 있습니다.</p>
%(plates)s

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
    <span class="barstate" id="barstate"></span>
    <button id="prev" onclick="go(cur-1)">이전 단계</button>
    <button id="next" class="primary" onclick="go(cur+1)">다음 단계</button>
    <button id="play" onclick="play()">자동 재생 <span class="sk">Space</span></button>
    <button onclick="go(0)">처음으로</button>
    <button onclick="showMap()">열두 칸 지도 <span class="sk">M</span></button>
    <button onclick="showCode()">이 단계 코드 보기 <span class="sk">C</span></button>
    <div class="tick" id="tick"></div>
    <div class="keys"><kbd>&#8592;</kbd><kbd>&#8594;</kbd> 앞뒤로
      <kbd>Space</kbd> 자동 재생 <kbd>M</kbd> 지도 <kbd>C</kbd> 코드
      <kbd>Esc</kbd> 닫기</div>
  </div>
  <button class="fab" onclick="dock(event)" title="조작판">
    <span class="big" id="fabn">1</span><span class="small" id="fabs">/ 12</span>
  </button>
</div>

<script>%(js)s</script></body></html>
"""
