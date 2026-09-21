"""요식 원장 확인기. 읽기 전용에 가까운 로컬 화면이다.

왜 만드는가.
    판정이 왜 그렇게 나왔는지 SQL 없이 눈으로 따라갈 수 있어야 한다.
    원문 한 줄이 어떤 규칙이 되었고 그 규칙이 어떤 답을 내는지 한 화면에서 본다.

무엇을 하지 않는가.
    영업 규칙과 휴무 규칙을 여기서 고치지 않는다. 그것은 적재기의 일이다.
    쓰기는 현장 확인 기록 한 가지뿐이며, 그것도 관측이지 규칙이 아니다.

띄우기
    set DINING_DSN=postgresql://postgres@localhost:5433/dining_dev
    python -m uvicorn scripts.dining.inspect_app:app --port 8011 --reload
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

KST = timezone(timedelta(hours=9))
DAYS = ["", "월", "화", "수", "목", "금", "토", "일"]

app = FastAPI(title="요식 원장 확인기")


def connect():
    import psycopg

    dsn = os.environ.get("DINING_DSN")
    if not dsn:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))))
            from app.infrastructure.db.session import database_dsn
            dsn = database_dsn()
        except Exception as exc:                        # noqa: BLE001
            raise HTTPException(500, f"접속 주소를 찾지 못했다: {exc}") from exc
    return psycopg.connect(dsn)


def hhmm(minutes) -> str:
    """자정 넘김은 24:30 처럼 보인다. 이튿날로 접지 않는다."""
    if minutes is None:
        return "—"
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_at(text: str | None) -> datetime:
    if not text:
        return datetime.now(KST).replace(second=0, microsecond=0)
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    raise HTTPException(400, f"시각을 읽지 못했다: {text}")


# ──────────────────────────────────────────────────────────────
# 자료
# ──────────────────────────────────────────────────────────────

@app.get("/api/summary")
def api_summary():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dining.dn_place")
        places = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM dining.v_hours_rule_active")
        rules = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM dining.v_closure_rule_active")
        closures = cur.fetchone()[0]
        cur.execute("SELECT area, count(*) FROM dining.dn_place GROUP BY 1 ORDER BY 2 DESC")
        areas = [{"area": a, "n": n} for a, n in cur.fetchall()]
        # 판단 불가. 규칙이 아예 없거나 coverage 가 unknown 인 요일이 있는 곳
        cur.execute("""
            SELECT count(DISTINCT p.place_uid) FROM dining.dn_place p
            WHERE NOT EXISTS (SELECT 1 FROM dining.v_hours_rule_active r
                               WHERE r.place_uid = p.place_uid
                                 AND r.coverage = 'intervals')""")
        blind = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM dining.dn_live_check")
        checks = cur.fetchone()[0]
    return {"places": places, "rules": rules, "closures": closures,
            "areas": areas, "blind": blind, "checks": checks}


@app.get("/api/places")
def api_places(q: str = "", limit: int = 300):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT p.place_uid, p.name_ko, p.area, p.record_status,
                   (SELECT count(*) FROM dining.v_closure_rule_active c
                     WHERE c.place_uid = p.place_uid)
            FROM dining.dn_place p
            WHERE (%s = '' OR p.name_ko ILIKE '%%' || %s || '%%'
                           OR p.area ILIKE '%%' || %s || '%%')
            ORDER BY p.area, p.name_ko
            LIMIT %s""", (q, q, q, limit))
        rows = cur.fetchall()
    return [{"uid": str(u), "name": n, "area": a, "status": s, "closures": c}
            for u, n, a, s, c in rows]


@app.get("/api/place/{uid}")
def api_place(uid: str, at: str | None = None, conds: str = "card_payment,parking,takeout"):
    when = parse_at(at)
    visit = when.date()
    codes = [c.strip() for c in conds.split(",") if c.strip()]

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT name_ko, area, road_address, phone, record_status, lat, lng
            FROM dining.dn_place WHERE place_uid = %s""", (uid,))
        got = cur.fetchone()
        if not got:
            raise HTTPException(404, "그런 장소가 없다")
        name, area, addr, phone, status, lat, lng = got

        # 원문. 판정을 따라가려면 무엇을 읽고 만든 것인지 보여야 한다.
        cur.execute("""
            SELECT raw_json ->> 'opentimefood', raw_json ->> 'restdatefood'
            FROM dining.dn_source_record WHERE place_uid = %s LIMIT 1""", (uid,))
        raw = cur.fetchone() or (None, None)

        # 이번 주 7일
        week = []
        monday = visit - timedelta(days=visit.weekday())
        for i in range(7):
            d = monday + timedelta(days=i)
            cur.execute("""
                SELECT seq, open_min, close_min, last_order_min, last_order_state,
                       break_state, coverage, source_code, extract_method
                FROM dining.day_intervals(%s, %s) ORDER BY seq""", (uid, d))
            ivs = cur.fetchall()
            cur.execute("SELECT dining.is_closed_on(%s, %s)", (uid, d))
            closed = cur.fetchone()[0]
            week.append({
                "date": d.isoformat(), "day": DAYS[i + 1], "closed": closed,
                "today": d == visit,
                "intervals": [{
                    "open": hhmm(o), "close": hhmm(c),
                    "lo": hhmm(lo) if lst == "present" else ("없음" if lst == "none" else "모름"),
                    "break_state": bs, "coverage": cov,
                    "source": src, "method": mth,
                } for _, o, c, lo, lst, bs, cov, src, mth in ivs],
            })

        # 그 시각 판정
        ends = when + timedelta(hours=1)
        cur.execute("SELECT dining.open_at_slot(%s, %s, %s)", (uid, when, ends))
        open_ok = cur.fetchone()[0]
        cur.execute("SELECT dining.needs_last_order_check(%s, %s, %s)", (uid, when, ends))
        lo_check = cur.fetchone()[0]
        cur.execute("SELECT dining.needs_holiday_check(%s, %s)", (uid, when))
        hol_check = cur.fetchone()[0]
        cur.execute("SELECT dining.holiday_context(%s, %s)", (uid, when))
        hol_ctx = cur.fetchone()[0]
        cur.execute("SELECT dining.condition_report(%s, %s)", (uid, codes))
        conds_out = cur.fetchone()[0]
        cur.execute("SELECT dining.check_prompt(%s, %s, %s)", (uid, when, True))
        prompt = cur.fetchone()[0]

        cur.execute("""
            SELECT topic, outcome, value_state, value_num, value_detail,
                   source_code, asked_at, ttl_seconds, checked_by
            FROM dining.dn_live_check WHERE place_uid = %s
            ORDER BY asked_at DESC LIMIT 20""", (uid,))
        checks = [{"topic": t, "outcome": o, "state": s, "num": n, "detail": d,
                   "source": src, "at": a.isoformat(), "ttl": ttl, "by": by,
                   "fresh": a + timedelta(seconds=ttl) > datetime.now(a.tzinfo)}
                  for t, o, s, n, d, src, a, ttl, by in cur.fetchall()]

        live = {}
        for topic in ("hours", "closure", "vacancy", "waiting"):
            cur.execute("SELECT dining.live_state(%s, %s)", (uid, topic))
            live[topic] = cur.fetchone()[0]

    return {
        "uid": uid, "name": name, "area": area, "address": addr, "phone": phone,
        "status": status, "lat": lat, "lng": lng,
        "raw_hours": raw[0], "raw_rest": raw[1],
        "at": when.isoformat(), "week": week,
        "judge": {"open": open_ok, "last_order_check": lo_check,
                  "holiday_check": hol_check, "holiday_context": hol_ctx},
        "conditions": conds_out, "prompt": prompt,
        "checks": checks, "live": live,
    }


@app.post("/api/place/{uid}/check")
def api_record(uid: str, body: dict):
    """현장 확인 한 건을 적는다. 화면에서 하는 유일한 쓰기다."""
    topic = body.get("topic")
    if topic not in ("hours", "closure", "vacancy", "waiting"):
        raise HTTPException(400, "그런 주제가 없다")
    source = body.get("source") or (
        "catchtable_trial" if topic in ("vacancy", "waiting") else "operator_check")
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT dining.record_live_check(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, source, topic,
             body.get("outcome", "ok"), body.get("state", "unknown"),
             body.get("num"), body.get("detail") or None,
             "inspect_app", parse_at(body.get("at")), "inspect_app"))
        new_id = cur.fetchone()[0]
        conn.commit()
    return JSONResponse({"check_id": str(new_id)})


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


PAGE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>요식 원장 확인기</title>
<style>
:root{--bg:#fbfaf8;--panel:#fff;--ink:#1b1a18;--dim:#6f6a63;--line:#e4e0da;
      --ok:#1f7a45;--no:#a3341f;--unk:#8a7320;--accent:#2b5c8a;}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#17171a;--panel:#1f1f23;--ink:#eceae6;--dim:#9c968d;--line:#32323a;
  --ok:#5cc98a;--no:#e8836b;--unk:#d8b84a;--accent:#7fb2e0;}}
:root[data-theme=dark]{--bg:#17171a;--panel:#1f1f23;--ink:#eceae6;--dim:#9c968d;
  --line:#32323a;--ok:#5cc98a;--no:#e8836b;--unk:#d8b84a;--accent:#7fb2e0;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:15px/1.6 -apple-system,"Segoe UI","Malgun Gothic",sans-serif}
header{padding:14px 16px;border-bottom:1px solid var(--line);
       display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:650}
.sum{color:var(--dim);font-size:13px}
main{display:grid;grid-template-columns:270px 1fr;gap:0;min-height:calc(100vh - 52px)}
@media(max-width:820px){main{grid-template-columns:1fr}
  #list{max-height:230px;border-right:none;border-bottom:1px solid var(--line)}}
#list{border-right:1px solid var(--line);overflow:auto;padding:10px}
#list input{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:7px;
  background:var(--panel);color:var(--ink);margin-bottom:8px}
.item{padding:6px 8px;border-radius:6px;cursor:pointer;font-size:13.5px}
.item:hover{background:var(--line)}
.item.on{background:var(--accent);color:#fff}
.item .a{color:var(--dim);font-size:11.5px;margin-left:5px}
.item.on .a{color:#dbe8f4}
#pane{padding:16px 18px;overflow:auto}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
      padding:13px 15px;margin-bottom:13px}
.card h2{font-size:13px;margin:0 0 9px;color:var(--dim);font-weight:650;
         letter-spacing:.04em;text-transform:uppercase}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:5px 9px 5px 0;vertical-align:top}
th{color:var(--dim);font-weight:500;white-space:nowrap}
tr+tr td,tr+tr th{border-top:1px solid var(--line)}
.ok{color:var(--ok);font-weight:650}
.no{color:var(--no);font-weight:650}
.unk{color:var(--unk);font-weight:650}
.raw{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;
     white-space:pre-wrap;color:var(--dim);word-break:break-all}
.ctl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:13px}
input[type=datetime-local],select,button{padding:6px 9px;border:1px solid var(--line);
  border-radius:7px;background:var(--panel);color:var(--ink);font-size:13.5px}
button{cursor:pointer}
button.go{background:var(--accent);color:#fff;border-color:transparent}
.tag{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11.5px;
     border:1px solid var(--line);color:var(--dim);margin-right:4px}
a{color:var(--accent)}
.hint{color:var(--dim);font-size:12.5px;margin-top:7px}
.big{font-size:19px;font-weight:650}
.wk td{padding:4px 9px 4px 0}
.wk .d{width:38px;color:var(--dim)}
.wk .today{font-weight:700;color:var(--accent)}
</style></head><body>
<header><h1>요식 원장 확인기</h1><span class="sum" id="sum">…</span></header>
<main>
  <div id="list"><input id="q" placeholder="상호 또는 지역"><div id="items"></div></div>
  <div id="pane"><p class="hint">왼쪽에서 한 곳을 고르면 판정이 어떻게 나오는지 보여준다.</p></div>
</main>
<script>
const $=s=>document.querySelector(s);
let cur=null, at=null;

function initAt(){
  const d=new Date(); d.setMinutes(0,0,0);
  at=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
}
initAt();

function state(v){
  if(v===true) return '<span class="ok">열림</span>';
  if(v===false) return '<span class="no">닫힘</span>';
  return '<span class="unk">모름</span>';
}
function cond(v){
  if(v===true) return '<span class="ok">맞음</span>';
  if(v===false) return '<span class="no">아님</span>';
  return '<span class="unk">모름</span>';
}
function esc(s){return (s??'').toString().replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));}

async function loadSummary(){
  const s=await (await fetch('/api/summary')).json();
  $('#sum').textContent=`장소 ${s.places} · 영업규칙 ${s.rules} · 휴무규칙 ${s.closures}`
    +` · 영업시간 모름 ${s.blind}곳 · 현장확인 ${s.checks}건`;
}

async function loadList(){
  const q=$('#q').value.trim();
  const rows=await (await fetch('/api/places?q='+encodeURIComponent(q))).json();
  $('#items').innerHTML=rows.map(r=>
    // record_status 는 대부분 unknown 이다. 인허가 자료를 아직 안 붙였기 때문이며
    // 영업 여부와 무관하다. 폐업일 때만 눈에 띄게 한다.
    `<div class="item${r.uid===cur?' on':''}" data-uid="${r.uid}">${esc(r.name)}`
    +`<span class="a">${esc(r.area)}${r.status==='closed'?' · 폐업':''}</span></div>`).join('');
  $('#items').querySelectorAll('.item').forEach(el=>
    el.onclick=()=>{cur=el.dataset.uid; loadList(); loadPlace();});
}

async function loadPlace(){
  if(!cur) return;
  const d=await (await fetch(`/api/place/${cur}?at=${encodeURIComponent(at)}`)).json();
  const j=d.judge;
  const wk=d.week.map(w=>{
    let body;
    if(w.closed) body='<span class="no">휴무</span>';
    else if(!w.intervals.length) body='<span class="unk">모름</span>';
    else body=w.intervals.map(i=>`${i.open}–${i.close}`
        +(i.lo!=='모름'&&i.lo!=='없음'?` <span class="tag">LO ${i.lo}</span>`:'')).join(' , ');
    return `<tr><td class="d${w.today?' today':''}">${w.day}</td><td>${body}</td></tr>`;
  }).join('');

  const cr=d.conditions||{};
  const conds=Object.keys(cr).map(k=>
    `<tr><th>${k}</th><td>${cond(cr[k].meets)} <span class="tag">${cr[k].state}</span>`
    +`${cr[k].detail?' '+esc(cr[k].detail):''}</td></tr>`).join('');

  const checks=d.checks.length? d.checks.map(c=>
    `<tr><th>${c.at.slice(5,16).replace('T',' ')}</th><td>${c.topic} · `
    +`${c.outcome==='ok'?'':'<span class="no">'+c.outcome+'</span> '}`
    +`<b>${c.state}</b>${c.num!=null?' ('+c.num+')':''} `
    +`<span class="tag">${c.source}</span>${c.fresh?'':'<span class="tag">기한지남</span>'}`
    +`${c.detail?' '+esc(c.detail):''}</td></tr>`).join('')
    : '<tr><td class="hint">아직 확인한 적 없다.</td></tr>';

  const p=d.prompt;
  const promptBox = p
    ? `<div class="raw">${esc(p.sentence)}</div>
       <p class="hint">${p.topics.map(t=>`<span class="tag">${t}</span>`).join('')}
       상한 ${p.timeout_seconds}초 ·
       <a href="${p.naver}" target="_blank" rel="noopener">네이버</a> ·
       <a href="${p.google}" target="_blank" rel="noopener">구글</a>
       ${p.phone?' · '+esc(p.phone):''}</p>
       <div class="ctl" style="margin-top:8px">
         <select id="t">${p.topics.map(t=>`<option>${t}</option>`).join('')}</select>
         <select id="s"><option value="yes">그렇다</option><option value="no">아니다</option>
           <option value="unknown">모르겠다</option></select>
         <input id="dt" placeholder="본 대로 한 줄" style="flex:1;min-width:150px">
         <button class="go" onclick="record()">적기</button>
       </div>`
    : '<p class="hint">물을 것이 없다. 원장으로 답이 되거나 이미 확인했다.</p>';

  $('#pane').innerHTML=`
  <div class="ctl">
    <b style="font-size:17px">${esc(d.name)}</b>
    <span class="tag">${esc(d.area)}</span>
    ${d.status==='closed'?'<span class="tag no">폐업</span>':''}
    <input type="datetime-local" id="at" value="${at}">
    <button class="go" onclick="at=$('#at').value;loadPlace()">이 시각으로 판정</button>
  </div>

  <div class="card"><h2>그 시각 판정</h2>
    <p class="big">${state(j.open)}</p>
    <table>
      <tr><th>마지막 주문 확인</th><td>${j.last_order_check?'<span class="unk">필요</span>':'불필요'}</td></tr>
      <tr><th>명절 확인</th><td>${j.holiday_check?'<span class="unk">필요</span>':'불필요'}</td></tr>
      ${j.holiday_context?`<tr><th>명절</th><td>${esc(j.holiday_context.holiday_name)}
        ${j.holiday_context.same_day?'<span class="tag">당일</span>':''}</td></tr>`:''}
    </table>
    <p class="hint">모름은 닫혔다는 뜻이 아니다. 원장에 그 요일 자료가 없다는 뜻이다.</p>
  </div>

  <div class="card"><h2>이번 주</h2><table class="wk">${wk}</table></div>

  <div class="card"><h2>원문</h2>
    <table>
      <tr><th>영업시간</th><td class="raw">${esc(d.raw_hours)||'(없음)'}</td></tr>
      <tr><th>휴무</th><td class="raw">${esc(d.raw_rest)||'(없음)'}</td></tr>
      <tr><th>주소</th><td>${esc(d.address)||'—'}</td></tr>
      <tr><th>전화</th><td>${esc(d.phone)||'—'}</td></tr>
    </table>
  </div>

  <div class="card"><h2>여행 조건</h2><table>${conds}</table></div>

  <div class="card"><h2>현장 확인</h2>${promptBox}
    <table style="margin-top:10px">${checks}</table>
    <p class="hint">빈자리와 웨이팅은 catchtable_trial 로 적히며 판정에는 쓰이지 않는다.</p>
  </div>`;
}

async function record(){
  const topic=$('#t').value;
  await fetch(`/api/place/${cur}/check`,{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({topic,state:$('#s').value,detail:$('#dt').value,at})});
  loadPlace(); loadSummary();
}

$('#q').oninput=loadList;
loadSummary(); loadList();
</script></body></html>"""
