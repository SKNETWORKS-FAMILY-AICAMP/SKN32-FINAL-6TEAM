"""오프라인 지도 화면. 기록을 읽고 표시하며 판정하거나 저장하지 않는다."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read(path: Path) -> tuple[dict | None, str]:
    if not path.exists():
        return None, "기록 없음"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("객체가 아님")
        return value, "읽음"
    except (OSError, ValueError):
        return None, "기록을 읽지 못함"


def snapshot(track_id: str, scenario_id: str) -> dict[str, Any]:
    from . import build, scenarios, tracks
    from .config import WORKSPACE_ROOT, progress_path

    entries = []
    for scenario in scenarios.SCENARIOS.values():
        path = WORKSPACE_ROOT / ".acop_dojo" / "traces" / f"{scenario.scenario_id}.json"
        trace, note = _read(path)
        if trace is not None and (not isinstance(trace.get("steps"), list) or
                any(not isinstance(s, dict) or not all(isinstance(s.get(k), str)
                    for k in ("path", "symbol")) or
                    (s.get("caller") is not None and not isinstance(s["caller"], str))
                    for s in trace["steps"])):
            trace, note = None, "트레이스 형식을 읽지 못함"
        if trace is not None and trace.get("entry") != scenario.nodeid:
            trace, note = None, "현재 시나리오와 다른 테스트 기록"
        entries.append({**asdict(scenario), "trace": trace, "note": note,
                        "source": str(path)})
    state, note = _read(build.state_path())
    if state is not None and (not isinstance(state.get("steps", {}), dict) or
            not isinstance(state.get("revealed", []), list) or
            any(not isinstance(v, dict) for v in state.get("steps", {}).values())):
        state, note = None, "기록을 읽지 못함"
    _, progress_note = _read(progress_path())
    return {
        "tracks": [asdict(t) for t in tracks.TRACKS.values()],
        "scenarios": entries, "track": track_id, "scenario": scenario_id,
        "build_steps": [{**asdict(s), "paths": s.paths()} for s in build.steps()],
        "build_state": state or {}, "build_note": note,
        "build_source": str(build.state_path()),
        "build_target": str(build.build_target_root()),
        "build_workspace": str(build.build_workspace()),
        "progress_source": str(progress_path()), "progress_note": progress_note,
    }


def render(target: Path, trace: dict | None, progress: dict, track: Any = None,
           *, context: dict | None = None) -> str:
    from .mapgen import static_imports, module_name, layer_of, runtime_calls, measured_order

    data = dict(context or {})
    if context is None:
        data.update(tracks=[asdict(track)] if track else [],
                    track=track.track_id if track else "all",
                    scenario="selected", scenarios=[{
                        "scenario_id": "selected", "title": "선택한 트레이스",
                        "trace": trace, "note": "읽음" if trace else "기록 없음",
                        "source": "호출자가 전달한 트레이스", "nodeid": (trace or {}).get("entry", ""),
                        "needs_db": None}], build_steps=[], build_state={})
    imports = static_imports(target)
    modules = {module_name(p, target) for p in (target / "app").rglob("*.py")
               if "__pycache__" not in p.parts}
    modules.update(imports)
    modules.update(m for group in imports.values() for m in group)
    for entry in data["scenarios"]:
        raw = entry.get("trace")
        entry["order"] = measured_order(raw)
        entry["calls"] = [[a, b, count] for (a, b), count in runtime_calls(raw or {}).items()]
        modules.update(entry["order"])
    data.update(modules=[{"name": m, "layer": layer_of(m)} for m in sorted(modules)],
                imports=[[a, b] for a in sorted(imports) for b in sorted(imports[a])],
                progress=progress, target=str(target),
                generated=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    # JSON 안의 닫는 script 태그도 HTML 파서가 해석하지 못하게 한다.
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("&", "\\u0026")
    return PAGE.replace("__DOJO_DATA__", payload)


PAGE = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>triPilot 학습 지도</title>
<style>
:root{color-scheme:light;--bg:#f4f5f2;--paper:#fff;--ink:#20332f;--mut:#596963;--line:#dce3dd;--accent:#116652;--soft:#e9f3ed;--amber:#a95216}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 system-ui,-apple-system,'Segoe UI',sans-serif}
button,input,select{font:inherit;color:inherit}button,select,input{border:1px solid var(--line);border-radius:7px;background:var(--paper);padding:9px 12px}button{cursor:pointer}button:hover{border-color:var(--accent);background:var(--soft)}button:disabled{opacity:.45;cursor:default}button.primary{background:var(--accent);color:white;border-color:var(--accent)}:focus-visible{outline:3px solid #d68d25;outline-offset:3px}
[hidden]{display:none!important}h1,h2,h3,p{margin:0}h1{font-size:22px;font-weight:550}h2{font-size:18px;font-weight:550}h3{font-size:15px;font-weight:550}p+p{margin-top:8px}a{color:var(--accent)}code,pre,.mono{font:12px/1.6 ui-monospace,Consolas,monospace}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}small,.muted{color:var(--mut);font-size:12px}
.shell{max-width:1600px;margin:auto;padding:26px 32px 40px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:22px}.brand{display:flex;align-items:center;gap:13px}.mark{background:var(--accent);color:white;border-radius:10px;padding:8px 13px;font-size:20px}.stamp{text-align:right;color:var(--mut);font-size:12px}
nav{display:flex;gap:6px;border-bottom:1px solid var(--line);margin-bottom:24px}nav button{border:0;border-radius:0;background:transparent;padding:12px 22px;border-bottom:3px solid transparent}nav button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}
.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:20px}.stack{display:grid;gap:18px}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.between{justify-content:space-between}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;margin-top:18px}.controls{display:grid;grid-template-columns:240px minmax(0,1fr);gap:18px}label{display:grid;gap:6px;color:var(--mut);font-size:12px}select{width:100%;min-width:0;color:var(--ink)}.context{margin-top:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.tag{display:inline-block;border:1px solid var(--line);border-radius:5px;padding:2px 7px;font-size:12px;color:var(--mut)}.notice{padding:12px 14px;background:var(--soft);border-radius:7px;margin:12px 0}.warn{background:#fff3e7;color:#824418}.tools{margin:14px 0}.tools input{flex:1;min-width:150px}.tools label{display:flex;align-items:center}.tools input[type=checkbox]{min-width:0;flex:none;width:16px;height:16px}.graph{height:450px;overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fafcf9}.graph svg{display:block}.graph text{font:11px ui-monospace,Consolas,monospace;fill:var(--ink)}.graph .layer{font:12px system-ui;fill:var(--mut)}.graph .imp{stroke:#cbd5cd;fill:none}.graph .run{stroke:var(--amber);fill:none}.graph .node rect{fill:white;stroke:#c2cdc5}.graph .node.seen rect{fill:#e4eee6}.graph .node.selected rect{fill:#cce9dd;stroke:var(--accent);stroke-width:2}.graph .node{cursor:pointer}.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin-top:10px}.line{display:inline-block;width:18px;border-top:2px solid #b8c6bc;margin-right:6px;vertical-align:middle}.line.orange{border-color:var(--amber)}.dot{display:inline-block;width:9px;height:9px;background:#e4eee6;border:1px solid #a2b8a8;margin-right:6px}.eyebrow{font-size:12px;color:var(--accent);margin-bottom:5px}.prediction{display:flex;flex-direction:column;gap:12px;align-self:start}.prediction ol{padding-left:23px;margin:0;max-height:220px;overflow:auto}.prediction li{padding:5px 0;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,Consolas,monospace}.prediction .primary{width:100%}.command{display:flex;gap:10px;align-items:center;padding:10px 12px;background:#f3f6f2;border-radius:7px;margin-top:8px}.command code{flex:1}.command button{flex:none;padding:4px 8px;font-size:12px}.source{overflow-wrap:anywhere;font-size:12px;color:var(--mut)}details{border-top:1px solid var(--line);padding-top:10px;margin-top:12px}summary{cursor:pointer;color:var(--mut)}.evidence{margin-top:18px}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:16px 0}.sequence{max-height:210px;overflow:auto;padding-left:25px;font:12px/1.8 ui-monospace,Consolas,monospace;overflow-wrap:anywhere}.table-scroll{overflow:auto;max-height:360px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:10px;vertical-align:top}th{font-weight:500;color:var(--mut);position:sticky;top:0;background:var(--paper)}td{overflow-wrap:anywhere}td code{word-break:break-word}.build-grid{display:grid;grid-template-columns:310px minmax(0,1fr);gap:18px;margin-top:18px}.step-list{display:grid;gap:5px}.step-list button{text-align:left;display:flex;gap:10px;align-items:center}.step-list button[aria-pressed=true]{background:var(--soft);border-color:var(--accent)}.step-list .num{width:26px;color:var(--mut)}.step-list .name{flex:1}.file-list{overflow-wrap:anywhere;padding-left:20px}.record-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:18px}.record{padding:13px 0;border-bottom:1px solid var(--line)}.record:last-child{border-bottom:0}.footer{margin-top:22px;color:var(--mut);font-size:12px}.toast{min-height:22px;color:var(--accent);font-size:12px}.skip{position:absolute;left:20px;top:-100px}.skip:focus{top:8px;background:white;padding:8px;z-index:5}
@media(max-width:1000px){.workspace{grid-template-columns:minmax(0,1fr)}.prediction{display:grid;grid-template-columns:1fr 1fr}.prediction>h2,.prediction>.eyebrow,.prediction>.notice{grid-column:1/-1}.build-grid{grid-template-columns:250px minmax(0,1fr)}}
@media(max-width:640px){.shell{padding:18px 14px}.top{align-items:flex-start}.stamp{max-width:130px}.brand{gap:8px}h1{font-size:19px}nav button{padding:10px 13px}.controls,.build-grid,.record-grid,.comparison,.prediction{display:block}.controls label+label{margin-top:12px}.card{padding:15px}.workspace{gap:14px}.prediction>*+*{margin-top:12px}.build-grid>*,.record-grid>*{margin-bottom:14px}.graph{height:340px}.step-list{max-height:280px;overflow:auto}.comparison>div+div{margin-top:18px}.command{align-items:flex-start}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style></head><body>
<a class="skip" href="#main">내용으로 이동</a>
<div class="shell"><header class="top"><div class="brand"><span class="mark" aria-hidden="true">⌘</span><h1>triPilot 학습 지도</h1></div><div class="stamp">생성 시점의 기록<br><span id="generated"></span></div></header>
<nav aria-label="학습 화면"><button data-view="map" aria-pressed="true">실행 지도</button><button data-view="build" aria-pressed="false">처음부터 쌓기</button><button data-view="records" aria-pressed="false">진행 기록</button></nav>
<main id="main"><section id="view-map" aria-label="실행 지도">
<div class="card"><div class="controls"><label>학습 트랙<select id="track"></select></label><label>시나리오<select id="scenario"></select></label></div><div class="context"><span id="scenario-id" class="mono"></span><span id="trace-status" class="tag"></span></div><p id="objective" class="muted"></p></div>
<div class="workspace"><div class="card"><div class="row between"><h2>모듈 지도</h2><span id="module-count" class="muted"></span></div>
<div class="row tools"><input id="search" type="search" aria-label="모듈 경로 검색" placeholder="모듈 경로 검색"><label><input id="owned" type="checkbox">트랙 범위만</label><label><input id="imports" type="checkbox">정적 import</label></div>
<div class="graph" id="graph" tabindex="0" aria-label="모듈 지도. 가로와 세로로 스크롤할 수 있다."></div><p id="empty-map" hidden class="notice">조건에 맞는 모듈이 없다. 검색어나 트랙 범위를 바꾼다.</p>
<div class="legend"><span><i class="dot"></i>진행 기록에서 발견</span><span><i class="line"></i>정적 import</span><span id="run-legend">실측 호출 숨김</span></div><p class="muted" style="margin-top:8px">모듈을 누르면 예상에 추가된다. 같은 모듈을 다시 넣을 수 있다.</p></div>
<aside class="card prediction"><div class="eyebrow" id="phase">01 · 예상 작성</div><h2>내 예상 경로</h2><p id="prediction-empty" class="muted">요청이 지나갈 모듈을 지도에서 고른다.</p><ol id="picked" aria-label="내 예상 경로"></ol><div class="row"><button id="undo">하나 취소</button><button id="clear">다시 예상</button></div><button id="reveal" class="primary" disabled>실측 열기</button><p id="gate" class="muted"></p><div id="trace-notice" class="notice"></div><div><h3>터미널에서 실행</h3><div id="trace-command"></div><div id="map-command"></div><p class="muted" style="margin-top:8px">실행 후 지도를 다시 만들고 파일을 연다.</p></div></aside></div>
<section id="evidence" class="card evidence" hidden><div class="row between"><h2>예상과 실측</h2><span class="tag">저장된 트레이스</span></div><div class="comparison"><div><h3>내 예상</h3><ol id="mine" class="sequence"></ol></div><div><h3>실측 모듈 순서</h3><p class="muted">연속한 같은 모듈만 묶었다. 재방문은 남긴다.</p><ol id="actual" class="sequence"></ol></div></div><details><summary>호출 기록과 코드 위치</summary><p class="muted">호출자는 트레이스의 caller 값이다. 서로 다른 파일에 같은 심볼 이름이 있으면 지도 간선의 구분에 한계가 있다.</p><div class="table-scroll"><table><thead><tr><th>순서</th><th>호출자</th><th>실행 함수</th><th>코드 위치</th></tr></thead><tbody id="trace-rows"></tbody></table></div></details></section>
<details class="card"><summary>읽은 파일과 기록 정보</summary><div id="trace-source" class="source"></div><p class="muted">정적 import는 동적 조립을 모두 보여주지 못한다. 트레이스는 저장 당시 실행이다. 현재 코드와 같은지는 이 화면에서 판정하지 않는다.</p></details>
</section>
<section id="view-build" hidden aria-label="처음부터 쌓기"><div class="card"><div class="row between"><h2>처음부터 쌓기</h2><span id="build-summary" class="tag"></span></div><p style="margin-top:10px">빈 작업 폴더에서 베이스먼트를 단계별로 만든다. 판정은 CLI가 실행한 테스트 기록을 따른다.</p><p id="build-target" class="source"></p><div id="build-start"></div><p id="build-note" class="notice"></p></div><div class="build-grid"><div class="card step-list" id="build-steps" aria-label="쌓기 단계"></div><article class="card" id="build-detail"></article></div><details class="card"><summary>쌓기 기록 출처</summary><p id="build-source" class="source"></p></details></section>
<section id="view-records" hidden aria-label="진행 기록"><div class="card"><h2>진행 기록</h2><p class="muted" style="margin-top:8px">CLI가 남긴 상태와 근거다. 화면에서 새로 판정하지 않는다.</p><p id="progress-source" class="source"></p><div id="status-command"></div></div><div class="record-grid"><div class="card"><h3>학습 단계</h3><div id="stages"></div></div><div class="card"><h3>능력과 근거</h3><div id="abilities"></div></div><details class="card"><summary>보관된 기록</summary><p class="muted">중지한 커머스 기록은 현재 진행과 분리한다.</p><pre id="archived"></pre></details></section>
</main><footer class="footer">진행 파일과 실측 트레이스를 읽어 만든 HTML이다. 예상은 이 화면을 닫으면 사라진다.</footer><div id="toast" class="toast" role="status" aria-live="polite"></div></div>
<script type="application/json" id="dojo-data">__DOJO_DATA__</script>
<script>
'use strict';
const D=JSON.parse(document.getElementById('dojo-data').textContent), $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const status=v=>({passed:'통과',in_progress:'진행 중',completed:'완료',confirmed:'확정',provisional:'잠정',failed:'실패',unknown:'알 수 없음'}[v]||v||'기록 없음');
let picked=[],revealed=false,selectedStep=1;
function command(host,text){const box=el('div',undefined,'command'),code=el('code',text),button=el('button','복사');button.type='button';button.setAttribute('aria-label',text+' 복사');button.onclick=async()=>{try{if(!navigator.clipboard)throw Error();await navigator.clipboard.writeText(text);$('toast').textContent='명령을 복사했다.';}catch(_){const r=document.createRange();r.selectNodeContents(code);const s=window.getSelection();s.removeAllRanges();s.addRange(r);$('toast').textContent='명령을 선택했다. Ctrl+C 또는 복사 메뉴를 사용한다.';}};box.append(code,button);host.append(box);}
function fillSelect(host,items,value){host.replaceChildren();items.forEach(([v,t])=>{const o=el('option',t);o.value=v;host.append(o);});host.value=value;}
const track=()=>D.tracks.find(t=>t.track_id===$('track').value)||{track_id:'all',owns:[],scenarios:[]};
const scenario=()=>D.scenarios.find(s=>s.scenario_id===$('scenario').value)||D.scenarios[0];
const owns=m=>!track().owns.length||track().owns.some(p=>(m.replaceAll('.','/')+'.py').startsWith(p)||(m.replaceAll('.','/')+'/').startsWith(p));
function setScenarios(initial){const t=track();fillSelect($('scenario'),D.scenarios.map(s=>[s.scenario_id,(t.scenarios.includes(s.scenario_id)?'트랙 · ':'')+s.title]),initial||t.scenarios[0]||D.scenarios[0].scenario_id);if(!$('scenario').value)$('scenario').selectedIndex=0;}
function sourceLine(host,label,value){host.append(el('p',label+' · '+(value||'기록 없음')));}
function refreshScenario(){picked=[];revealed=false;const s=scenario(),raw=s.trace;const valid=raw&&raw.steps&&raw.steps.length;$('scenario-id').textContent=s.scenario_id;$('objective').textContent=s.objective||'';$('trace-status').textContent=valid?'트레이스 있음 · '+status(raw.outcome?.status):s.note==='읽음'?'호출 기록 없음':s.note;
$('trace-notice').textContent=valid?'저장된 실행 결과 · '+status(raw.outcome?.status)+(s.needs_db?' · 재실행에 DB 필요':''):'열 수 있는 호출 기록이 없다. 트레이스를 만든 뒤 지도를 다시 만든다.';
$('trace-notice').classList.toggle('warn',!valid||raw?.outcome?.status!=='passed');
$('trace-command').replaceChildren();$('map-command').replaceChildren();command($('trace-command'),'python dojo.py trace '+s.scenario_id);command($('map-command'),'python dojo.py map --track '+track().track_id+' --scenario '+s.scenario_id);
$('trace-source').replaceChildren();sourceLine($('trace-source'),'대상',D.target);sourceLine($('trace-source'),'트레이스',s.source);sourceLine($('trace-source'),'테스트',raw?.entry||s.nodeid);sourceLine($('trace-source'),'저장된 코드 리비전',raw?.code_revision);drawPrediction();drawGraph();}
function drawPrediction(){const s=scenario();$('picked').replaceChildren(...picked.map(m=>el('li',m)));$('prediction-empty').hidden=!!picked.length;$('undo').disabled=!picked.length||revealed;$('clear').disabled=!picked.length&&!revealed;$('reveal').disabled=!picked.length||!s.trace?.steps?.length||revealed;$('gate').textContent=revealed?'실측을 열었다. 다시 예상하면 실측이 숨겨진다.':picked.length?'예상을 정했으면 실측을 연다.':'모듈을 하나 이상 고르면 실측을 열 수 있다.';$('phase').textContent=revealed?'02 · 실측 확인':'01 · 예상 작성';$('evidence').hidden=!revealed;$('run-legend').textContent=revealed?'실측 호출 · 주황색 →':'실측 호출 숨김';}
function addModule(m){if(revealed)return;picked.push(m);drawPrediction();drawGraph();}
const NS='http://www.w3.org/2000/svg';
function svgEl(tag,attrs={},text){const e=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;return e;}
function drawGraph(){const query=$('search').value.toLowerCase();const mods=D.modules.filter(m=>(!$('owned').checked||owns(m.name))&&m.name.toLowerCase().includes(query));$('module-count').textContent=mods.length+' / '+D.modules.length+'개';$('empty-map').hidden=!!mods.length;
const layers=['presentation','application','core','domain','infrastructure','modules','기타'].filter(l=>mods.some(m=>m.layer===l)),pos=new Map();let rows=0;layers.forEach((l,i)=>{const ms=mods.filter(m=>m.layer===l);rows=Math.max(rows,ms.length);ms.forEach((m,j)=>pos.set(m.name,[18+i*225,48+j*36]));});
const width=Math.max(760,layers.length*225+20),height=Math.max(380,rows*36+65),svg=svgEl('svg',{width,height,role:'group','aria-label':'모듈 선택'});const defs=svgEl('defs'),marker=svgEl('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#a95216'}));defs.append(marker);svg.append(defs);
function edge(a,b,kind,count){if(!pos.has(a)||!pos.has(b))return;let [x,y]=pos.get(a),[u,v]=pos.get(b);const start=u>x?x+200:x,end=u>x?u:u+200,middle=(start+end)/2;const p=svgEl('path',{d:`M${start} ${y+13} C${middle} ${y+13} ${middle} ${v+13} ${end} ${v+13}`,class:kind,'stroke-width':kind==='run'?Math.min(1+count*.25,3):1});if(kind==='run'){p.setAttribute('marker-end','url(#arrow)');p.append(svgEl('title',{},a+' → '+b+' · '+count+'회'));}svg.append(p);}
if($('imports').checked)D.imports.forEach(([a,b])=>edge(a,b,'imp',1));if(revealed)scenario().calls.forEach(([a,b,n])=>edge(a,b,'run',n));
layers.forEach((l,i)=>svg.append(svgEl('text',{x:18+i*225,y:25,class:'layer'},l)));
const discovered=new Set((D.progress.discovered||[]).map(s=>s.split('::')[0].replace(/\/__init__\.py$/,'').replace(/\.py$/,'').replaceAll('/','.')));
mods.forEach(m=>{const [x,y]=pos.get(m.name),g=svgEl('g',{class:'node'+(discovered.has(m.name)?' seen':'')+(picked.includes(m.name)?' selected':''),role:'button',tabindex:'0','data-module':m.name,'aria-label':m.name+(revealed?'':' 예상에 추가'),'aria-disabled':String(revealed)});g.append(svgEl('title',{},m.name),svgEl('rect',{x,y,width:200,height:27,rx:5}));const short=m.name.replace('app.',''),label=short.length>27?'…'+short.slice(-26):short;g.append(svgEl('text',{x:x+8,y:y+18},label));g.onclick=()=>addModule(m.name);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();addModule(m.name);const replacement=Array.from($('graph').querySelectorAll('[data-module]')).find(n=>n.dataset.module===m.name);replacement?.focus({preventScroll:true});}};svg.append(g);});$('graph').replaceChildren(svg);}
$('undo').onclick=()=>{if(revealed)return;picked.pop();drawPrediction();drawGraph();};$('clear').onclick=()=>{picked=[];revealed=false;drawPrediction();drawGraph();};
$('reveal').onclick=()=>{if(!picked.length||!scenario().trace?.steps?.length)return;revealed=true;drawPrediction();drawGraph();$('mine').replaceChildren(...picked.map(m=>el('li',m)));$('actual').replaceChildren(...scenario().order.map(m=>el('li',m)));$('trace-rows').replaceChildren(...scenario().trace.steps.map((s,i)=>{const tr=el('tr');[String(i+1),s.caller||'기록 없음',s.symbol,s.path+':'+(s.line??'?')].forEach(v=>{const td=el('td');td.append(el('code',v));tr.append(td);});return tr;}));};
$('search').oninput=drawGraph;$('owned').onchange=drawGraph;$('imports').onchange=drawGraph;$('scenario').onchange=refreshScenario;$('track').onchange=()=>{setScenarios();refreshScenario();};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-view]').forEach(n=>{const active=n===b;n.setAttribute('aria-pressed',String(active));$('view-'+n.dataset.view).hidden=!active;});});
function renderBuild(){const state=D.build_state||{},steps=D.build_steps||[];$('build-summary').textContent=steps.filter(s=>state.steps?.[s.index]?.status==='passed').length+' / '+steps.length+'단계 통과 기록';$('build-target').textContent='대상 · '+(D.build_target||'기록 없음');$('build-note').textContent=D.build_note==='기록을 읽지 못함'?'쌓기 기록을 읽지 못했다. 상태 파일을 확인한다.':state.prepared_at?'작업 폴더 준비 기록 · '+state.prepared_at:'작업 폴더 준비 기록이 없다. 시작 전 터미널에서 build steps를 확인한다.';
command($('build-start'),'python dojo.py build '+(state.prepared_at?'steps':'start'));$('build-source').textContent=(D.build_source||'출처 없음')+' · '+(D.build_note||'기록 없음')+' · 작업 폴더: '+(D.build_workspace||'기록 없음');
selectedStep=steps.find(s=>state.steps?.[s.index]?.status!=='passed')?.index||1;
steps.forEach(s=>{const b=el('button');b.dataset.step=s.index;b.append(el('span',String(s.index).padStart(2,'0'),'num'),el('span',s.title,'name'),el('span',status(state.steps?.[s.index]?.status),'muted'));b.onclick=()=>{selectedStep=s.index;drawStep();};$('build-steps').append(b);});if(steps.length)drawStep();else $('build-detail').textContent='쌓기 단계가 전달되지 않았다.';}
function drawStep(){const s=D.build_steps.find(s=>s.index===selectedStep),state=D.build_state||{},record=state.steps?.[s.index],host=$('build-detail');document.querySelectorAll('[data-step]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.step)===selectedStep)));host.replaceChildren(el('div',String(s.index).padStart(2,'0')+' · '+status(record?.status),'eyebrow'),el('h2',s.title),el('p',s.claim,'notice'),el('p',s.why));command(host,'python dojo.py build brief '+s.index);command(host,'python dojo.py build check '+s.index);
const fileTitle=el('h3','만들 파일');fileTitle.style.marginTop='20px';host.append(fileTitle);const list=el('ul',undefined,'file-list');s.paths.forEach(p=>{const li=el('li');li.append(el('code',p));if((state.revealed||[]).includes(p))li.append(el('span',' · 참고 구현 꺼냄','tag'));list.append(li);});host.append(list);
const evidence=el('details');evidence.open=!!record;evidence.append(el('summary','테스트 기록과 대상'));sourceLine(evidence,'최근 요약',record?.summary);sourceLine(evidence,'시도',record?.attempts===undefined?'기록 없음':String(record.attempts));if(record?.failed?.length)evidence.append(el('pre',record.failed.join('\n')));evidence.append(el('pre',s.tests.join('\n')));host.append(evidence);}
function renderRecords(){const p=D.progress||{},names={'0':'해설된 완주','1':'실행 경로 복원','2':'예측과 대조','3':'결함 수리','4':'보스전 · 검증 엔진'};$('progress-source').textContent=(D.progress_source||'호출자가 전달한 진행 기록')+' · '+(D.progress_note||'읽음');command($('status-command'),'python dojo.py status');
Object.entries(names).forEach(([k,title])=>{const record=p.stages?.[k],box=el('div',undefined,'record');box.append(el('p',k+' · '+title),el('span',status(record?.status),'tag'));if(record){const d=el('details');d.append(el('summary','저장된 근거'),el('pre',JSON.stringify(record,null,2)));box.append(d);}$('stages').append(box);});command($('stages'),'python dojo.py boss');
const abilities=Object.entries(p.abilities||{});if(!abilities.length)$('abilities').append(el('p','능력 기록이 없다.','notice'));abilities.forEach(([name,v])=>{const box=el('div',undefined,'record');box.append(el('p',name),el('span',status(v.state),'tag'),el('p',v.evidence||'근거 기록 없음','source'));$('abilities').append(box);});$('archived').textContent=Object.keys(p.archived||{}).length?JSON.stringify(p.archived,null,2):'보관된 기록이 없다.';}
$('generated').textContent=new Date(D.generated).toLocaleString('ko-KR');fillSelect($('track'),D.tracks.length?D.tracks.map(t=>[t.track_id,t.title]):[['all','전체']],D.track);setScenarios(D.scenario);refreshScenario();renderBuild();renderRecords();
</script></body></html>'''
