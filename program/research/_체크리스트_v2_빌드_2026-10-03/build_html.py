# -*- coding: utf-8 -*-
"""v2_table.json → 아티팩트 페이지(out/index.html). 기존 v1 페이지의 색·글꼴 체계를 이어 쓴다."""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "out" / "v2_table.json").read_text(encoding="utf-8"))
E = html.escape
rows, N = D["rows"], D["n"]
C = D["counts"]
S = D["status"]
n_part, n_show, n_none = S.get("일부 경로·조건에서 판정", 0), S.get("표시만(판정 없음)", 0), S.get("어느 경로에도 없음", 0)
PATHS = [("g", "생성"), ("r", "등록"), ("w", "감시"), ("a", "응답")]
SYM = {"Y": "●", "P": "◐", "N": "·", "C": "◇"}
WORD = {"Y": "판정", "P": "일부", "N": "안 함", "C": "구성 보장"}
moves = D["moves"]


def mv(a, b):
    return moves.get(f"{a}→{b}", 0)


V1 = ["서버가 이미 판정", "일부 상황만 판정", "아직 없음", "직접 확인(고객만 앎)"]
V2 = ["일부 경로·조건에서 판정", "표시만(판정 없음)", "어느 경로에도 없음"]
v1_none_found = mv("아직 없음", V2[0]) + mv("아직 없음", V2[1])
v1_done = sum(mv("서버가 이미 판정", b) for b in V2)
p1 = [r for r in rows if r["priority"] == 1]
p1_rule = [r for r in p1 if r["action"] in ("규칙 추가", "배선")]
cats = []
for r in rows:
    if r["cat"] not in cats:
        cats.append(r["cat"])


def pctw(a, b):
    return f"{a * 100 / b:.1f}%"


def pathbar(p):
    c = C[p]
    segs = [("Y", "seg-y"), ("C", "seg-c"), ("P", "seg-p"), ("N", "seg-n")]
    out = []
    for k, cls in segs:
        v = c.get(k, 0)
        if v:
            out.append(f'<span class="{cls}" style="flex:{v}">{v}</span>')
    return "".join(out)


def cellhtml(letter, label):
    return f'<span class="cell c-{letter}" aria-label="{label} {WORD[letter]}" title="{label} {WORD[letter]}"><b>{SYM[letter]}</b><small>{label}</small></span>'


items = []
for r in rows:
    cells = "".join(cellhtml(r[p][0], name) for p, name in PATHS)
    notes = "".join(
        f'<div class="pn"><span class="cell c-{r[p][0]}"><b>{SYM[r[p][0]]}</b></span><div><strong>{name}</strong> <span class="muted">{WORD[r[p][0]]}</span><p>{E(r[p][1]) or "해당 코드 없음"}</p></div></div>'
        for p, name in PATHS)
    items.append(f'''<details class="item" data-cat="{E(r["cat"])}" data-status="{E(r["status"])}" data-pri="{r["priority"]}" data-act="{E(r["action"])}" data-q="{E((r["id"] + " " + r["text"]).lower())}">
<summary><span class="id">{r["id"]}</span><span class="txt">{E(r["text"])}</span><span class="cells">{cells}</span><span class="pri p{r["priority"]}" title="우선순위">{r["priority"]}</span><span class="act">{E(r["action"])}</span></summary>
<div class="detail">
<div class="paths">{notes}</div>
<dl>
<dt>확인 방법</dt><dd>{E(r["method"])}</dd>
<dt>통과 기준</dt><dd>{E(r["criterion"])}</dd>
<dt>값이 없을 때</dt><dd>{E(r["miss"])}</dd>
<dt>근거</dt><dd><code>{E(r["ev"])}</code></dd>
{f'<dt>메모</dt><dd>{E(r["note"])}</dd>' if r["note"] else ""}
<dt>v1 → v2</dt><dd>{E(r["v1"])} → {E(r["status"])}</dd>
</dl>
</div></details>''')

catchips = "".join(f'<button type="button" class="chipbtn" data-cat="{E(c)}" aria-pressed="false">{E(c)} <span class="muted">{sum(1 for r in rows if r["cat"] == c)}</span></button>' for c in cats)

facts = "".join(f'<li><strong>{E(a)}</strong><span>{E(b)}</span><code>{E(c)}</code></li>' for a, b, c in D["facts"])
metrics = "".join(f"<tr><th scope=row>{E(a)}</th><td>{E(b)}</td><td>{E(c)}</td></tr>" for a, b, c in D["metrics"])
vocab = "".join(f'<li><code>{E(a)}</code> {E(b)}</li>' for a, b in D["vocab"])
cross = "".join(f"<li>{E(x)}</li>" for x in D["cross"])
src = E(D["sources"]) if D["sources"] else "하위 조사 3개(Claude) · Codex(gpt-6-luna) 반증 · 검토 전용 Claude 에이전트의 적대적 반증을 합쳤습니다."
out = "".join(f"<li><code>{k}</code> {E(v['item'])}</li>" for k, v in D["out"].items())

move_rows = ""
for a in V1:
    tot = sum(mv(a, b) for b in V2)
    cells = "".join(f'<td class="num">{mv(a, b) or "·"}</td>' for b in V2)
    move_rows += f'<tr><th scope="row">{E(a)}</th><td class="num">{tot}</td>{cells}</tr>'
move_rows += '<tr class="sum"><th scope="row">합계</th><td class="num">%d</td>%s</tr>' % (N, "".join(f'<td class="num">{S.get(b, 0)}</td>' for b in V2))

pri_n = {k: D["priority"].get(str(k), D["priority"].get(k, 0)) for k in (1, 2, 3)}
act_n = D["action"]

PAGE = f'''<title>여행 확인 체크리스트</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap">
<style>
/* 레이아웃: 한 칸짜리 보고서. 결론 → 길별 현황 → 66항목 필터 표 → 구멍 → 평가 고리 → 순서. v1 페이지의 색·글꼴을 그대로 이어 쓴다. */
:root {{
  --bg: #f4f6f3; --surface: #ffffff; --ink: #24392f; --muted: #5d6e64; --line: #dce3dd;
  --accent: #2e6047; --soft: #e9f2eb;
  --warn: #82693e; --warn-soft: #faf6ec; --warn-line: #e5d9c1;
  --bad: #965640; --bad-soft: #fdf3ed;
  --info: #2c6179; --info-soft: #e8f1f5;
  --gray: #8a968f; --gray-soft: #eef0ed;
  --font: "Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
  --mono: ui-monospace, "SFMono-Regular", Consolas, "Malgun Gothic", monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #131915; --surface: #1b231e; --ink: #e5ede7; --muted: #9db0a5; --line: #323f37;
    --accent: #7cc29b; --soft: #21322a;
    --warn: #dbb978; --warn-soft: #2b2619; --warn-line: #4a4128;
    --bad: #e4947d; --bad-soft: #33211b;
    --info: #87bfd9; --info-soft: #1b2d36;
    --gray: #7d8b83; --gray-soft: #232b26;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #131915; --surface: #1b231e; --ink: #e5ede7; --muted: #9db0a5; --line: #323f37;
  --accent: #7cc29b; --soft: #21322a;
  --warn: #dbb978; --warn-soft: #2b2619; --warn-line: #4a4128;
  --bad: #e4947d; --bad-soft: #33211b;
  --info: #87bfd9; --info-soft: #1b2d36;
  --gray: #7d8b83; --gray-soft: #232b26;
  color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--ink); font-family: var(--font); line-height: 1.7; word-break: keep-all; overflow-wrap: break-word; margin: 0; }}
.wrap {{ max-width: 920px; margin: 0 auto; padding-inline: 18px; padding-block: 28px 64px; display: flex; flex-direction: column; gap: 30px; }}
h1 {{ font-size: 28px; line-height: 1.35; letter-spacing: -.02em; margin: 0; text-wrap: balance; }}
h2 {{ font-size: 20px; line-height: 1.4; margin: 0 0 4px; letter-spacing: -.01em; text-wrap: balance; }}
h3 {{ font-size: 15px; margin: 0; }}
p {{ margin: 0; }}
code {{ font-family: var(--mono); font-size: 12px; background: var(--gray-soft); padding: 1px 5px; border-radius: 4px; word-break: break-all; }}
.eyebrow {{ font-size: 12px; letter-spacing: .08em; color: var(--accent); font-weight: 700; text-transform: uppercase; }}
.lead {{ color: var(--muted); font-size: 15px; }}
.muted {{ color: var(--muted); }}
.small {{ font-size: 12.5px; }}
section {{ display: flex; flex-direction: column; gap: 12px; min-width: 0; }}
.card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; }}
.conclusion {{ background: var(--soft); border-color: transparent; display: flex; flex-direction: column; gap: 8px; }}
.conclusion ul {{ margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }}
.ask {{ border-top: 1px solid var(--line); padding-top: 8px; margin-top: 2px; }}
.tablewrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ font-weight: 700; font-size: 12.5px; color: var(--muted); }}
tbody th {{ color: var(--ink); font-size: 13.5px; }}
td.num, th.num {{ text-align: right; }}
tr.sum td, tr.sum th {{ font-weight: 700; color: var(--ink); }}
.pbars {{ display: flex; flex-direction: column; gap: 10px; }}
.pbar {{ display: grid; grid-template-columns: 4.5em minmax(0, 1fr); gap: 10px; align-items: center; }}
.pbar .name {{ font-weight: 700; font-size: 13.5px; }}
.bar {{ display: flex; height: 30px; border-radius: 8px; overflow: hidden; border: 1px solid var(--line); }}
.bar span {{ display: flex; align-items: center; justify-content: center; font-size: 12.5px; font-weight: 700; min-width: 0; }}
.seg-y {{ background: var(--accent); color: var(--surface); }}
.seg-c {{ background: var(--info); color: var(--surface); }}
.seg-p {{ background: var(--warn-soft); color: var(--warn); }}
.seg-n {{ background: var(--gray-soft); color: var(--muted); }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; }}
.legend i {{ display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; border: 1px solid var(--line); }}
.paths4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.paths4 .card {{ padding: 12px 14px; display: flex; flex-direction: column; gap: 3px; }}
.paths4 h3 {{ color: var(--accent); }}
.filters {{ display: flex; flex-direction: column; gap: 10px; }}
.chiprow {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.chipbtn {{ font: inherit; font-size: 12.5px; padding: 3px 11px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); cursor: pointer; }}
.chipbtn[aria-pressed="true"] {{ background: var(--accent); color: var(--surface); border-color: var(--accent); }}
.chipbtn:focus-visible, select:focus-visible, input:focus-visible, summary:focus-visible, a:focus-visible {{ outline: 3px solid var(--accent); outline-offset: 2px; }}
.ctrls {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.ctrls select, .ctrls input {{ font: inherit; font-size: 13px; padding: 5px 9px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); min-width: 0; }}
.ctrls input {{ flex: 1 1 180px; }}
.count {{ color: var(--muted); font-size: 12.5px; }}
.colhead, .item > summary {{ display: grid; grid-template-columns: 3em minmax(0, 1fr) auto 1.9em 5.6em; gap: 8px 10px; align-items: start; }}
.colhead {{ padding: 0 12px; font-size: 12px; font-weight: 700; color: var(--muted); }}
.colhead .cells {{ min-width: 8.8em; }}
.list {{ display: flex; flex-direction: column; gap: 6px; }}
.item {{ border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }}
.item > summary {{ cursor: pointer; padding: 9px 12px; list-style: none; font-size: 13.5px; }}
.item > summary::-webkit-details-marker {{ display: none; }}
.item[open] > summary {{ border-bottom: 1px solid var(--line); }}
.item .id {{ font-family: var(--mono); font-size: 12px; color: var(--muted); padding-top: 2px; }}
.item .act {{ font-size: 12px; color: var(--muted); text-align: right; padding-top: 2px; }}
.cells {{ display: flex; gap: 4px; min-width: 8.8em; justify-content: flex-end; }}
.cell {{ display: inline-flex; flex-direction: column; align-items: center; justify-content: center; min-width: 2em; border-radius: 6px; padding: 1px 0; border: 1px solid var(--line); line-height: 1.2; }}
.cell b {{ font-size: 13px; }}
.cell small {{ display: none; font-size: 10px; color: inherit; opacity: .85; }}
.c-Y {{ background: var(--accent); color: var(--surface); border-color: var(--accent); }}
.c-P {{ background: var(--warn-soft); color: var(--warn); border-color: var(--warn-line); }}
.c-C {{ background: var(--info-soft); color: var(--info); border-color: transparent; }}
.c-N {{ background: var(--gray-soft); color: var(--muted); }}
.pri {{ display: inline-grid; place-items: center; width: 1.7em; height: 1.7em; border-radius: 50%; font-size: 12px; font-weight: 700; }}
.pri.p1 {{ background: var(--accent); color: var(--surface); }}
.pri.p2 {{ background: var(--warn-soft); color: var(--warn); border: 1px solid var(--warn-line); }}
.pri.p3 {{ background: var(--gray-soft); color: var(--muted); }}
.detail {{ padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 12px; }}
.paths {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.pn {{ display: grid; grid-template-columns: 2.2em minmax(0, 1fr); gap: 8px; font-size: 13px; }}
.pn p {{ color: var(--ink); line-height: 1.55; }}
dl {{ display: grid; grid-template-columns: 7em minmax(0, 1fr); gap: 4px 12px; margin: 0; font-size: 13px; }}
dt {{ color: var(--muted); font-weight: 700; font-size: 12.5px; }}
dd {{ margin: 0; min-width: 0; }}
.facts {{ list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }}
.facts li {{ display: flex; flex-direction: column; gap: 3px; border-top: 1px solid var(--line); padding-top: 10px; font-size: 13.5px; }}
.facts li:first-child {{ border-top: 0; padding-top: 0; }}
.fault {{ display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.4fr) auto; gap: 6px 14px; align-items: center; }}
.fault .meter {{ height: 14px; background: var(--gray-soft); border-radius: 7px; position: relative; overflow: hidden; }}
.fault .meter b {{ position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent); border-radius: 7px; }}
.fault .pct {{ font-weight: 700; font-size: 13px; min-width: 3.4em; text-align: right; }}
.faults {{ display: flex; flex-direction: column; gap: 10px; }}
ol.steps {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; counter-reset: s; }}
ol.steps li {{ counter-increment: s; display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 4px 12px; }}
ol.steps li::before {{ content: counter(s); grid-row: 1 / span 2; width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: var(--surface); font-weight: 700; display: grid; place-items: center; font-size: 13px; }}
ol.steps .what {{ font-weight: 700; }}
ol.steps .effect {{ color: var(--muted); font-size: 13.5px; }}
a {{ color: var(--accent); }}
ul.plain {{ margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }}
@media (max-width: 640px) {{
  h1 {{ font-size: 24px; }}
  .colhead {{ display: none; }}
  .item > summary {{ grid-template-columns: 2.6em minmax(0, 1fr) 1.9em; }}
  .item .cells {{ grid-column: 1 / -1; justify-content: flex-start; }}
  .item .act {{ grid-column: 2 / -1; text-align: left; }}
  .cell {{ min-width: 3em; }}
  .cell small {{ display: block; }}
  dl {{ grid-template-columns: 1fr; }}
  .fault {{ grid-template-columns: 1fr auto; }}
  .fault .meter {{ grid-column: 1 / -1; order: 3; }}
}}
</style>

<main class="wrap">
  <header style="display:flex;flex-direction:column;gap:8px">
    <span class="eyebrow">Validation 보강 · 2026-10-03 · 2판</span>
    <h1>여행 확인 체크리스트</h1>
    <p class="lead">여행하는 사람이 일정표를 믿으려고 직접 하는 확인 72가지를, 서버의 네 길(생성·등록·감시·응답)마다 코드와 대조해 다시 쟀습니다. 확인 결과를 일정표에 붙인 화면 시안은 <a href="mock.html">시안 페이지</a>에 그대로 있습니다.</p>
  </header>

  <section class="card conclusion" aria-labelledby="c">
    <h2 id="c">결론</h2>
    <ul>
      <li>서버가 일정을 판정하는 범위 안은 <strong>{N}가지</strong>입니다. 그중 <strong>{n_part}가지</strong>는 일부 길이나 일부 조건에서 이미 판정하고, <strong>{n_show}가지</strong>는 보여 주기만 하고, <strong>{n_none}가지</strong>는 어느 길에도 없습니다. 모든 길에서 판정하는 항목은 하나도 없습니다.</li>
      <li>v1이 「서버가 이미 판정」이라 한 {v1_done}가지는 {v1_done}가지 모두 일부 길에서만이었습니다. 「아직 없음」 {sum(mv("아직 없음", b) for b in V2)}가지 중 <strong>{mv("아직 없음", V2[0])}가지</strong>는 일부 길에서 이미 판정하고 {mv("아직 없음", V2[1])}가지는 보여 주기만 합니다.</li>
      <li>가장 큰 구멍은 셋입니다. 외부에서 받은 일정(등록 길)은 같은 곳 두 번·끼니 빠짐·요일 불일치를 못 봅니다. 웹 화면은 결제·예산·식이 조건을 서버에 보내지 않아(서버 입구는 받습니다) 웹 경로에서는 그 검사가 꺼져 있습니다. 감시 두 벌 중 시나리오 쪽에는 「바꾼 뒤 일정 전체 재판정」이 없습니다.</li>
      <li>항목마다 확인 방법과 통과 기준을 붙였고, 결과를 숫자로 내는 평가 고리(결함일 비율 등 6개 지표)를 설계했습니다. 아직 한 번도 재지 않았습니다.</li>
    </ul>
    <p class="ask"><strong>정하실 것</strong> 아래 「적용 순서」 1단계({len(p1_rule)}가지 규칙 추가)를 서버 담당 세션에 넘길지, 결함일 비율을 먼저 한 번 잴지.</p>
  </section>

  <section aria-labelledby="p">
    <h2 id="p">진행 현황</h2>
    <div class="card tablewrap">
      <table>
        <thead><tr><th>할 일</th><th>상태</th><th class="num">진행</th></tr></thead>
        <tbody>
          <tr><td>v1 서버 현황 주장을 코드로 반증</td><td>끝</td><td class="num">{N}/{N} = 100%</td></tr>
          <tr><td>길별 판정 표</td><td>끝</td><td class="num">{N}/{N} = 100%</td></tr>
          <tr><td>항목별 확인 방법·통과 기준·우선순위</td><td>끝</td><td class="num">{N}/{N} = 100%</td></tr>
          <tr><td>평가 고리 설계</td><td>설계만</td><td class="num">지표 6 · 결과 어휘 4</td></tr>
          <tr><td>평가 고리 실측</td><td>미착수</td><td class="num">0/1 = 0%</td></tr>
          <tr><td>서버에 규칙 추가</td><td>승인 대기</td><td class="num">0/{len(p1_rule)} = 0%</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section aria-labelledby="w">
    <h2 id="w">네 길마다 얼마나 판정하나</h2>
    <p class="muted">같은 확인도 어느 길에서 도는지가 다릅니다. 숫자는 코드를 읽어 센 것이고, 서버에서 돌려 본 값이 아닙니다.</p>
    <div class="paths4">
      <div class="card"><h3>생성</h3><p class="small">우리 생성기가 일정을 짤 때. 짜면서 같은 판정기로 최대 3회 고칩니다.</p></div>
      <div class="card"><h3>등록</h3><p class="small">고객·외부 에이전트가 만든 일정을 받을 때(REST·MCP·읽은 일정 확인).</p></div>
      <div class="card"><h3>감시</h3><p class="small">여행 중 3분 점검, 03:00 새벽 확인, 고객 신고. 항목 하나씩 봅니다.</p></div>
      <div class="card"><h3>응답</h3><p class="small">결과가 고객 화면·API에 나가는가. 표시일 뿐 판정은 아닙니다.</p></div>
    </div>
    <div class="card" style="display:flex;flex-direction:column;gap:12px">
      <div class="pbars">
        {"".join(f'<div class="pbar"><span class="name">{name}</span><div class="bar" role="img" aria-label="{name}: 판정 {C[p].get("Y", 0)}, 구성 보장 {C[p].get("C", 0)}, 일부 {C[p].get("P", 0)}, 안 함 {C[p].get("N", 0)}">{pathbar(p)}</div></div>' for p, name in PATHS)}
      </div>
      <div class="legend">
        <span><i style="background:var(--accent)"></i>● 판정한다</span>
        <span><i style="background:var(--info)"></i>◇ 만드는 방식으로 보장</span>
        <span><i style="background:var(--warn-soft)"></i>◐ 일부 조건·일부 경우만</span>
        <span><i style="background:var(--gray-soft)"></i>· 안 한다</span>
      </div>
      <p class="small muted">막대 하나가 {N}가지입니다. 「구성 보장」은 일정을 만드는 방식 때문에 어긋날 수 없을 뿐 검증하는 코드는 아닌 경우입니다(예: 날짜에서 요일을 계산해 붙이므로 요일이 틀릴 수 없음).</p>
    </div>
  </section>

  <section aria-labelledby="v">
    <h2 id="v">v1 주장은 얼마나 맞았나</h2>
    <div class="card tablewrap">
      <table>
        <thead><tr><th>v1 상태</th><th class="num">항목</th><th class="num">v2: 일부 길 판정</th><th class="num">표시만</th><th class="num">어느 길에도 없음</th></tr></thead>
        <tbody>{move_rows}</tbody>
      </table>
    </div>
    <p class="small muted">「아직 없음」 {mv("아직 없음", V2[0])}개는 일부 길에서 이미 판정하므로 「없음」이라고만 쓰면 과하게 읽힙니다. v1의 「찾았고 안 나왔다」는 등록 길 기준으로는 대체로 맞았습니다.</p>
  </section>

  <section aria-labelledby="t">
    <h2 id="t">66항목 길별 판정표</h2>
    <p class="muted">줄을 누르면 길별 설명, 확인 방법과 통과 기준, 값이 없을 때, 근거 파일·줄이 펼쳐집니다. 우선순위 1은 흔한 결함이고 값이 이미 있어 규칙만 더하면 되는 것(또는 우선 연결할 것), 2는 입력·소스를 이어야 하는 것, 3은 소스가 아예 없어 보류하는 것입니다.</p>
    <div class="card filters">
      <div class="chiprow" id="cats">{catchips}</div>
      <div class="ctrls">
        <select id="fs" aria-label="상태로 거르기"><option value="">상태 전체</option><option>일부 경로·조건에서 판정</option><option>표시만(판정 없음)</option><option>어느 경로에도 없음</option></select>
        <select id="fp" aria-label="우선순위로 거르기"><option value="">우선순위 전체</option><option value="1">1순위 {pri_n[1]}</option><option value="2">2순위 {pri_n[2]}</option><option value="3">3순위 {pri_n[3]}</option></select>
        <select id="fa" aria-label="다음 조치로 거르기"><option value="">다음 조치 전체</option>{"".join(f'<option>{E(k)}</option>' for k in act_n)}</select>
        <input id="fq" type="search" placeholder="항목 이름·ID 검색" aria-label="항목 검색">
      </div>
      <p class="count" id="cnt" aria-live="polite">{N}개 표시</p>
    </div>
    <div class="colhead" aria-hidden="true"><span>ID</span><span>확인</span><span class="cells"><span style="min-width:2em;text-align:center">생성</span><span style="min-width:2em;text-align:center">등록</span><span style="min-width:2em;text-align:center">감시</span><span style="min-width:2em;text-align:center">응답</span></span><span>우선</span><span style="text-align:right">조치</span></div>
    <div class="list" id="list">
      {"".join(items)}
    </div>
    <p class="small muted">범위 밖 6가지(표에서 뺌):</p>
    <ul class="plain small muted">{out}</ul>
  </section>

  <section aria-labelledby="f">
    <h2 id="f">표 밖의 구멍</h2>
    <div class="card"><ul class="facts">{facts}</ul></div>
  </section>

  <section aria-labelledby="k">
    <h2 id="k">모르는 값을 길마다 다르게 다룹니다</h2>
    <p class="muted">2026-09-10 결정 15는 「값을 모르는 상황을 만들지 않는다」입니다. 코드에서는 같은 「모름」이 길에 따라 통과도 되고 탈락도 됩니다.</p>
    <div class="card tablewrap"><table>
      <thead><tr><th>모르는 값</th><th>등록</th><th>생성</th><th>감시(대체 후보)</th></tr></thead>
      <tbody>
        <tr><th scope="row">영업시간</th><td>통과(건너뜀)</td><td>통과. 응답에 읽은 칸 수를 공개</td><td>식당은 탈락, 활동은 통과</td></tr>
        <tr><th scope="row">결제 수단</th><td>통과</td><td>통과</td><td>식당은 탈락, 활동은 안 봄</td></tr>
        <tr><th scope="row">가격</th><td>0원으로 합산</td><td>0원으로 합산</td><td>활동은 경고, 식당은 안 봄</td></tr>
        <tr><th scope="row">소스 호출 실패</th><td>해당 없음</td><td>해당 없음</td><td>바꾸지 않고 알리지도 않음(fatal)</td></tr>
      </tbody></table></div>
    <p class="small muted">결과 어휘에 <code>unknown</code>을 두면 이 차이가 숫자로 보입니다. 아래 평가 고리가 그렇게 합니다.</p>
  </section>

  <section aria-labelledby="e">
    <h2 id="e">숫자로 보이는 평가 고리</h2>
    <p class="muted">체크리스트를 채점표로 쓰면 일정 하나를 넣을 때 항목마다 한 줄 결과가 나옵니다. 멘토 피드백의 「추천 품질을 숫자로 보여라」에 대한 답입니다.</p>
    <div class="card" style="display:flex;flex-direction:column;gap:12px">
      <h3>결과 어휘</h3>
      <ul class="plain small">{vocab}</ul>
      <p class="small muted"><code>unknown</code>은 통과가 아닙니다. 값이 없어 못 본 것을 통과로 세면 모름이 성공률을 올려 보이게 합니다.</p>
    </div>
    <div class="card tablewrap"><table>
      <thead><tr><th>지표</th><th>계산</th><th>왜 재나</th></tr></thead>
      <tbody>{metrics}</tbody></table></div>
    <div class="card" style="display:flex;flex-direction:column;gap:14px">
      <h3>밖에서는 어떤 오류가 흔한가</h3>
      <p class="small muted">AI가 만든 여행 일정 356개(2,735일)를 외부 자료와 대조한 한 업체의 연구입니다. 퍼센트는 그 오류가 하나라도 있는 날의 비율이고, 하나라도 있는 날은 전체의 43.2%입니다. 막대는 25%를 끝으로 한 같은 눈금입니다.</p>
      <div class="faults">
        <div class="fault"><span>그 시각에 닫혀 있음</span><span class="meter"><b style="width:90.8%"></b></span><span class="pct">22.7%</span></div>
        <div class="fault"><span>머무는 중에 마감을 넘김</span><span class="meter"><b style="width:66.4%"></b></span><span class="pct">16.6%</span></div>
        <div class="fault"><span>하루 동선이 왔다 갔다</span><span class="meter"><b style="width:38%"></b></span><span class="pct">9.5%</span></div>
        <div class="fault"><span>같은 장소를 두 번 이상</span><span class="meter"><b style="width:20.4%"></b></span><span class="pct">5.1%</span></div>
        <div class="fault"><span>폐업·휴업한 곳</span><span class="meter"><b style="width:2%"></b></span><span class="pct">0.5%</span></div>
        <div class="fault"><span>한낮에 일출·일몰 활동</span><span class="meter"><b style="width:0.4%"></b></span><span class="pct">0.1%</span></div>
      </div>
      <p class="small muted">이 연구는 업체 자체 운영 자료이고 동료 검토가 없으며, 서울 일정이 아닌 61개국 표본입니다. 어떤 오류가 흔한지 가늠하는 힌트로만 씁니다. 같은 정의(하루에 결함이 하나라도 있나)로 우리 일정을 재면 직접 비교됩니다.
        출처: <a href="https://monkeyeatingmango.com/research/ai-itinerary-errors-data-study/" target="_blank" rel="noopener">43% of AI-Planned Days Carry a Fault</a></p>
      <p class="small muted">기존 평가 러너(<code>eval/runners/travel_scenarios.py</code>)는 시나리오 10건(하루 1종·서울 1도시)에서 위반 0건을 확인하는 용도라, 결함일 비율은 아직 잰 적이 없습니다.</p>
    </div>
  </section>

  <section aria-labelledby="o">
    <h2 id="o">적용 순서</h2>
    <ol class="steps">
      <li><span class="what">우선순위 1 규칙 추가 ({len(p1_rule)}가지, 서버)</span><span class="effect">값은 이미 있는데 판정이 안 걸린 길에 판정만 더합니다. 등록 길의 같은 곳 중복·끼니 누락·요일 대조, 공휴일 연결, 되돌아감, 시나리오 감시의 전체 재판정이 여기 듭니다.</span></li>
      <li><span class="what">입력 연결 (서버·웹)</span><span class="effect">웹 화면이 결제·예산·식이를 서버에 보내게 하고, 설문 음식 코드를 식이 조건으로 바꾸는 코드와 이동 일행 조건을 실제로 채웁니다.</span></li>
      <li><span class="what">배선 (서버)</span><span class="effect">만들어 두고 아무도 부르지 않는 하루 점검·방문 전 확인·장소 변경 감시를 감시 루프에 겁니다. 안 쓸 거면 문서에서 「있다」고 하지 않습니다.</span></li>
      <li><span class="what">평가 고리 측정 (평가)</span><span class="effect">체크리스트 id별 결과를 세는 채점기를 붙여 결함일 비율·모름 비율·판정 범위를 한 번 잽니다.</span></li>
      <li><span class="what">소스 필요 항목은 보류 (기획)</span><span class="effect">예약·메뉴·접근성처럼 데이터가 아예 없는 것은 소스를 정할 때까지 「모름」으로 표시합니다.</span></li>
    </ol>
  </section>

  <section aria-labelledby="x">
    <h2 id="x">교차검증 기록</h2>
    <div class="card" style="display:flex;flex-direction:column;gap:8px">
      <p class="small">{src}</p>
      <ul class="plain small">{cross}</ul>
    </div>
  </section>

  <section aria-labelledby="l">
    <h2 id="l">한계</h2>
    <ul class="small muted plain">
      <li>코드만 읽었습니다. DB에 영업시간·결제·가격 칸이 실제로 몇 % 채워져 있는지, 운영에서 이동 계산기가 켜져 있는지, 구글·교통 키가 있는지는 보지 않았습니다. 꺼져 있으면 표의 ◐ 중 일부는 · 이 됩니다.</li>
      <li>「안 한다(·)」는 한국어·영어 키워드 검색으로 안 나왔다는 뜻입니다. 약어·JSON 키·런타임에 조립되는 문자열은 놓칠 수 있습니다.</li>
      <li>「호출처 0건」은 <code>app/</code>·<code>scripts/</code> 이름 검색입니다. 크론·동적 호출은 놓칠 수 있습니다.</li>
      <li>응답 칸은 서버가 내보내는 값 기준입니다. 프런트가 실제로 그리는지는 보지 않았습니다.</li>
      <li>72가지는 여행자·상담사에게 묻거나 실제 일정표 표본으로 센 것이 아닙니다. 「빠진 것이 없다」는 증명이 아닙니다.</li>
    </ul>
  </section>
</main>

<script>
(function () {{
  var items = Array.prototype.slice.call(document.querySelectorAll('#list .item'));
  var cat = null, st = document.getElementById('fs'), pr = document.getElementById('fp'), ac = document.getElementById('fa'), q = document.getElementById('fq'), cnt = document.getElementById('cnt');
  function apply() {{
    var n = 0, k = q.value.trim().toLowerCase();
    items.forEach(function (el) {{
      var ok = (!cat || el.dataset.cat === cat) && (!st.value || el.dataset.status === st.value) && (!pr.value || el.dataset.pri === pr.value) && (!ac.value || el.dataset.act === ac.value) && (!k || el.dataset.q.indexOf(k) >= 0);
      el.hidden = !ok; if (ok) n++;
    }});
    cnt.textContent = n + '개 표시';
  }}
  document.getElementById('cats').addEventListener('click', function (e) {{
    var b = e.target.closest('button'); if (!b) return;
    var on = b.getAttribute('aria-pressed') === 'true';
    Array.prototype.forEach.call(this.children, function (x) {{ x.setAttribute('aria-pressed', 'false'); }});
    cat = on ? null : b.dataset.cat; if (!on) b.setAttribute('aria-pressed', 'true');
    apply();
  }});
  [st, pr, ac].forEach(function (x) {{ x.addEventListener('change', apply); }});
  q.addEventListener('input', apply);
}})();
</script>
'''
(HERE / "out" / "index.html").write_text(PAGE, encoding="utf-8")
print("html", len(PAGE))
