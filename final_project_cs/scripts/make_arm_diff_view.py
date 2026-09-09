# -*- coding: utf-8 -*-
"""B 와 Proposed 의 답변을 같은 case 에서 나란히 놓고 읽는 HTML 을 만든다.

★왜 만드나 — **수치만 보면 원인을 못 찾는다.**
  재기준선(D-014) 뒤 `B > Proposed` 가 모든 축에서 나왔는데, 평균값만 보고는
  "Proposed 가 나쁘다" 와 "재는 쪽이 틀렸다" 를 못 가른다. 답변을 실제로 읽자
  1초 만에 갈렸다 — Proposed 는 **Team 의 내부 판정 문구**를 냈고 B 는
  **고객용 산문**을 냈다. 채점자는 고객 답변을 채점하니 B 가 이긴다.

  이 저장소는 같은 모양으로 다섯 번 속았다(DoD-15 실패 이력 3·4·5회차).
  매번 수치가 먼저 나오고 원인은 답변을 읽고 나서야 나왔다. 그래서 읽는 도구를
  남긴다.

★공정하게 보이려고 지킨 것:
  - 같은 `case_id` · 같은 `repeat` 만 짝짓는다. 회차가 다르면 후보 답변이 달라
    채점자 차이와 답변 차이가 섞인다
  - 어느 쪽이 "정답" 인지 표시하지 않는다. 점수는 보여주되 승패를 미리 칠하지 않는다
  - 답변을 자르지 않는다. 자르면 "짧아서 진 것" 과 "잘려서 짧아 보이는 것" 이 섞인다

    python -m scripts.make_arm_diff_view
    # 그다음 wiki/records/labeling/arm_diff.html 을 브라우저로 연다
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIELDS = ("correctness", "policy_grounding", "next_action", "safety", "personalization")
FIELD_KO = {"correctness": "사실", "policy_grounding": "근거", "next_action": "다음행동",
            "safety": "안전", "personalization": "맞춤"}


#: 이 스크립트가 실제로 쓰는 필드. 나머지(team_result·citations·config)는 크고 안 쓴다.
_KEEP = ("case_id", "repeat")


def _slim(row: dict) -> dict:
    """행에서 **쓸 것만** 남긴다.

    ★2026-09-09 — 처음엔 `read_text()` 로 통째 읽고 행을 그대로 들고 있었다.
      Proposed 산출물이 3.2MB 인데 `MemoryError` 가 났다 — 파일이 커서가 아니라
      그때 이 기계의 **커밋 여유가 0.84GB** 였기 때문이다(claude 프로세스 30개가
      6.7GB 를 쓰고 있었다). 파일 크기만 보고 "이 정도면 괜찮다" 고 넘기면
      같은 자리에서 또 죽는다.
      그래서 **줄 단위로 읽고 쓸 필드만 남긴다** — `team_result` 하나가 행 부피의
      대부분이고 이 화면은 그걸 안 쓴다.
    """
    judge = row.get("judge") or {}
    pred = row.get("prediction") or {}
    reasons = judge.get("reasons") or []
    return {
        "answer": (pred.get("answer") or "").strip(),
        "next_action": pred.get("next_action"),
        "scores": {f: judge.get(f, 0) for f in FIELDS},
        "total": judge.get("total", 0),
        "pass": bool(judge.get("pass")),
        # 사유는 첫 줄만, 그것도 잘라서 — 화면에서도 220자만 쓴다
        "reasons": [str(reasons[0])[:240]] if reasons else [],
    }


def _load(path: Path) -> dict:
    out = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            out[(row["case_id"], row.get("repeat", 1))] = _slim(row)
    return out


def _cases() -> dict[str, dict]:
    out = {}
    for name in ("golden.jsonl", "holdout.jsonl"):
        p = ROOT / "eval/datasets" / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out[row["case_id"]] = row
    return out


def build(b_path: Path, p_path: Path) -> dict:
    left, right = _load(b_path), _load(p_path)
    cases = _cases()
    keys = sorted(set(left) & set(right))

    items = []
    for key in keys:
        b, p = left[key], right[key]
        bj, pj = b, p
        # ★"어느 쪽이 통과했나" 로 묶는다. 점수 차가 아니라 판정이 갈리는 곳이
        #   읽을 가치가 있다 — 점수는 조금 차이나도 결론이 같으면 볼 게 없다.
        if bj["pass"] and not pj["pass"]:
            group = "b_only"
        elif pj["pass"] and not bj["pass"]:
            group = "p_only"
        elif bj["pass"] and pj["pass"]:
            group = "both"
        else:
            group = "neither"
        items.append({
            "case_id": key[0], "repeat": key[1], "group": group,
            "message": (cases.get(key[0], {}) or {}).get("message", ""),
            "b": b, "p": p,
        })

    # 읽는 순서 — 판정이 갈린 것 먼저, 그중 점수 차가 큰 것 먼저.
    order = {"b_only": 0, "p_only": 1, "neither": 2, "both": 3}
    items.sort(key=lambda i: (order[i["group"]], -abs(i["b"]["total"] - i["p"]["total"])))

    n = len(items)
    def _stat(side: str) -> dict:
        answers = [i[side]["answer"] for i in items]
        counts = collections.Counter(answers)
        top_text, top_n = counts.most_common(1)[0]
        return {
            "distinct": len(counts), "distinct_pct": len(counts) / n if n else 0,
            "mean_len": round(statistics.mean([len(a) for a in answers]), 1) if n else 0,
            "empty": sum(1 for a in answers if not a),
            "empty_pct": (sum(1 for a in answers if not a) / n) if n else 0,
            "top_n": top_n, "top_pct": top_n / n if n else 0, "top_text": top_text,
            "fields": {f: round(statistics.mean([i[side]["scores"][f] for i in items]), 2) for f in FIELDS},
            "pass": sum(1 for i in items if i[side]["pass"]),
        }

    groups = collections.Counter(i["group"] for i in items)
    return {"n": n, "items": items, "b": _stat("b"), "p": _stat("p"),
            "groups": {k: {"n": groups.get(k, 0), "pct": groups.get(k, 0) / n if n else 0}
                       for k in ("b_only", "p_only", "both", "neither")}}


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>군 답변 대조 — B 와 Proposed 를 같은 case 에서 나란히</title>
<style>
:root{{--bg:#f6f7fa;--surface:#fff;--line:#dfe3ec;--text:#161c28;--dim:#5c667a;
--code:#eef1f6;--band:#f0f2f7;--b:#2f6f8b;--p:#8a5a20;--warn:#fdeeee;--warnL:#e08a8a;
--ok:#eefbf4;--okL:#7fcaa6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{
--bg:#12151c;--surface:#191d26;--line:#2b3240;--text:#e6e9f0;--dim:#98a2b8;
--code:#1f2430;--band:#1c212b;--b:#6fb6d6;--p:#d6a45f;--warn:#2c1a1a;--warnL:#7d4141;
--ok:#12291f;--okL:#2f6b50}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);
font:15px/1.7 -apple-system,"Segoe UI",system-ui,"Malgun Gothic",sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:30px 20px 100px}}
h1{{font-size:24px;margin:0 0 5px;letter-spacing:-.3px}}
.sub{{color:var(--dim);margin:0 0 22px;font-size:14.5px}}
h2{{font-size:19px;margin:36px 0 10px;padding-top:15px;border-top:1px solid var(--line)}}
code{{background:var(--code);padding:1.5px 6px;border-radius:4px;
font:12.5px ui-monospace,Consolas,monospace}}
pre{{background:var(--code);padding:12px 15px;border-radius:8px;overflow-x:auto;
font:12.5px/1.6 ui-monospace,Consolas,monospace;margin:11px 0}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}}
th,td{{border:1px solid var(--line);padding:7px 10px;text-align:left}}
th{{background:var(--band)}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
.box{{border:1px solid var(--line);border-left-width:4px;border-radius:8px;padding:12px 16px;margin:15px 0}}
.box.warn{{background:var(--warn);border-left-color:var(--warnL)}}
.box.ok{{background:var(--ok);border-left-color:var(--okL)}}
.bar{{position:sticky;top:0;z-index:5;background:var(--bg);padding:11px 0;
border-bottom:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.bar button{{font:13.5px inherit;padding:6px 13px;border-radius:99px;cursor:pointer;
border:1px solid var(--line);background:var(--surface);color:var(--text)}}
.bar button[aria-pressed=true]{{background:#58a;color:#fff;border-color:#58a}}
.bar .count{{color:var(--dim);font-size:13px;margin-left:auto}}
.case{{border:1px solid var(--line);border-radius:10px;margin:14px 0;overflow:hidden;background:var(--surface)}}
.chead{{padding:11px 15px;background:var(--band);display:flex;gap:10px;
align-items:baseline;flex-wrap:wrap;border-bottom:1px solid var(--line)}}
.cid{{font:12px ui-monospace,monospace;color:var(--dim)}}
.msg{{flex:1 1 340px;font-size:14.5px}}
.pill{{font-size:11.5px;padding:1px 9px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
@media(max-width:760px){{.cols{{grid-template-columns:1fr}}}}
.col{{padding:13px 15px}}
.col+.col{{border-left:1px solid var(--line)}}
@media(max-width:760px){{.col+.col{{border-left:0;border-top:1px solid var(--line)}}}}
.who{{font-weight:600;font-size:13.5px;margin-bottom:7px}}
.who.b{{color:var(--b)}} .who.p{{color:var(--p)}}
.ans{{background:var(--code);border-radius:7px;padding:10px 13px;margin:7px 0;
font-size:14px;white-space:pre-wrap;word-break:break-word;min-height:44px}}
.ans.empty{{color:var(--warnL);font-style:italic}}
.sc{{display:flex;gap:5px;flex-wrap:wrap;margin:7px 0;font-size:11.5px}}
.sc span{{background:var(--band);padding:2px 8px;border-radius:5px;
font-variant-numeric:tabular-nums;border:1px solid var(--line)}}
.rs{{font-size:12.5px;color:var(--dim);margin-top:6px}}
.foot{{margin-top:44px;padding-top:15px;border-top:1px solid var(--line);
color:var(--dim);font-size:13px}}
</style></head><body><div class="wrap">

<h1>군 답변 대조 — 같은 case 에서 B 와 Proposed 를 나란히</h1>
<p class="sub">{n}행 (72 case × 3회) · judge-v3 · 재기준선 산출물 · 생성 {stamp}</p>

<div class="box warn">
<p><b>이 페이지가 답하는 질문:</b> <code>B &gt; Proposed</code> 가 <b>제품이 나빠서</b>인가,
<b>재는 쪽이 틀려서</b>인가. 평균값만 보면 안 갈린다 — <b>답변을 읽으면 갈린다.</b></p>
</div>

<h2>먼저 — 답변의 모양</h2>
<table>
<thead><tr><th></th><th class="n">서로 다른 답변</th><th class="n">평균 길이</th>
<th class="n">빈 답변</th><th class="n">최다 반복 문구</th></tr></thead>
<tbody>
<tr><td><b style="color:var(--b)">B</b> (고정 워크플로 + 정책검색)</td>
    <td class="n">{b_distinct}/{n} = {b_distinct_pct}</td><td class="n">{b_len}자</td>
    <td class="n">{b_empty}/{n} = {b_empty_pct}</td>
    <td class="n">{b_top}/{n} = {b_top_pct}</td></tr>
<tr><td><b style="color:var(--p)">Proposed</b> (Case lifecycle + Team)</td>
    <td class="n">{p_distinct}/{n} = {p_distinct_pct}</td><td class="n">{p_len}자</td>
    <td class="n">{p_empty}/{n} = {p_empty_pct}</td>
    <td class="n">{p_top}/{n} = {p_top_pct}</td></tr>
</tbody></table>

<div class="box">
<p>★ Proposed 는 216행에서 <b>답변이 {p_distinct}종뿐</b>이고 <b>{p_empty_pct} 가 빈 문자열</b>이다.
나머지도 <code>{p_top_text}</code> 같은 <b>고정 문구</b>다 — 이것은 Team 의
<b>내부 판정 문구</b>이지 고객이 읽을 문장이 아니다.</p>
<p>채점자는 <b>고객 답변</b>을 채점한다. 한쪽은 판정 문구를, 한쪽은 고객용 산문을 냈다.</p>
</div>

<h2>축별 평균</h2>
<table>
<thead><tr><th>축</th><th class="n">B</th><th class="n">Proposed</th><th class="n">차이</th></tr></thead>
<tbody>{axis_rows}</tbody></table>

<h2>판정이 갈린 곳</h2>
<table>
<thead><tr><th>구분</th><th class="n">행</th><th class="n">비율</th></tr></thead>
<tbody>{group_rows}</tbody></table>

<h2>실제 답변 — 읽어 보기</h2>
<div class="bar">
  <button data-f="b_only" aria-pressed="true">B만 통과</button>
  <button data-f="p_only" aria-pressed="true">Proposed만 통과</button>
  <button data-f="neither" aria-pressed="false">둘 다 실패</button>
  <button data-f="both" aria-pressed="false">둘 다 통과</button>
  <button id="empty" aria-pressed="false">Proposed 답변이 빈 것만</button>
  <span class="count" id="count"></span>
</div>
<div id="list"></div>

<div class="foot">
근거 — <code>eval/reports/2026-09-06_rebaseline_B_judgev3.jsonl</code> ·
<code>eval/reports/2026-09-06_rebaseline_Proposed_judgev3.jsonl</code><br>
생성 — <code>python -m scripts.make_arm_diff_view</code> ·
경위 <code>wiki/records/reports/debugs/2026-09-06_B가_Proposed를_이긴다.md</code>
</div>

</div>
<script>
const ITEMS = {items_json};
const KO = {ko_json};
const GROUP_KO = {{b_only:"B만 통과", p_only:"Proposed만 통과", both:"둘 다 통과", neither:"둘 다 실패"}};
const on = new Set(["b_only","p_only"]);
let emptyOnly = false;

function esc(s){{return String(s==null?"":s).replace(/[&<>"']/g,c=>(
  {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));}}

function side(o, cls, who){{
  const empty = !o.answer;
  return '<div class="col"><div class="who '+cls+'">'+who+
    ' · 총점 '+o.total+' · '+(o.pass?"통과":"실패")+'</div>'+
    '<div class="ans'+(empty?" empty":"")+'">'+(empty?"(빈 답변)":esc(o.answer))+'</div>'+
    '<div class="sc">'+Object.keys(o.scores).map(f=>
      '<span>'+KO[f]+' '+o.scores[f]+'</span>').join('')+
      '<span>next '+esc(o.next_action)+'</span></div>'+
    (o.reasons.length?'<div class="rs">'+esc(o.reasons[0]).slice(0,220)+'</div>':'')+
    '</div>';
}}

function render(){{
  const list = document.getElementById("list");
  const rows = ITEMS.filter(i => on.has(i.group) && (!emptyOnly || !i.p.answer));
  document.getElementById("count").textContent = rows.length + " / " + ITEMS.length + " 행";
  list.innerHTML = rows.map(i =>
    '<div class="case"><div class="chead">'+
      '<span class="cid">'+esc(i.case_id)+' · '+i.repeat+'회</span>'+
      '<span class="msg">'+esc(i.message)+'</span>'+
      '<span class="pill">'+GROUP_KO[i.group]+'</span>'+
    '</div><div class="cols">'+side(i.b,"b","B")+side(i.p,"p","Proposed")+'</div></div>'
  ).join('') || '<p class="sub">고른 조건에 맞는 행이 없습니다.</p>';
}}

document.querySelectorAll('.bar button[data-f]').forEach(btn=>{{
  btn.onclick = () => {{
    const f = btn.dataset.f;
    if(on.has(f)) on.delete(f); else on.add(f);
    btn.setAttribute("aria-pressed", on.has(f));
    render();
  }};
}});
document.getElementById("empty").onclick = (e) => {{
  emptyOnly = !emptyOnly;
  e.target.setAttribute("aria-pressed", emptyOnly);
  render();
}};
render();
</script></body></html>
"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="B 대 Proposed 답변 대조 뷰")
    parser.add_argument("--b", default="eval/reports/2026-09-06_rebaseline_B_judgev3.jsonl")
    parser.add_argument("--proposed", default="eval/reports/2026-09-06_rebaseline_Proposed_judgev3.jsonl")
    parser.add_argument("--out", default="wiki/records/labeling/arm_diff.html")
    args = parser.parse_args()

    data = build(ROOT / args.b, ROOT / args.proposed)
    n = data["n"]
    if not n:
        print("겹치는 행이 없다. 입력 파일을 확인한다.")
        return 1
    b, p = data["b"], data["p"]
    pct = lambda x: f"{x:.1%}"

    axis_rows = "".join(
        f'<tr><td>{FIELD_KO[f]} <code>{f}</code></td>'
        f'<td class="n">{b["fields"][f]:.2f}</td><td class="n">{p["fields"][f]:.2f}</td>'
        f'<td class="n">{p["fields"][f] - b["fields"][f]:+.2f}</td></tr>' for f in FIELDS)
    group_ko = {"b_only": "B만 통과", "p_only": "Proposed만 통과",
                "both": "둘 다 통과", "neither": "둘 다 실패"}
    group_rows = "".join(
        f'<tr><td>{group_ko[k]}</td><td class="n">{v["n"]}</td>'
        f'<td class="n">{v["n"]}/{n} = {pct(v["pct"])}</td></tr>'
        for k, v in data["groups"].items())

    from datetime import datetime
    page = PAGE.format(
        n=n, stamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        b_distinct=b["distinct"], b_distinct_pct=pct(b["distinct_pct"]), b_len=b["mean_len"],
        b_empty=b["empty"], b_empty_pct=pct(b["empty_pct"]), b_top=b["top_n"], b_top_pct=pct(b["top_pct"]),
        p_distinct=p["distinct"], p_distinct_pct=pct(p["distinct_pct"]), p_len=p["mean_len"],
        p_empty=p["empty"], p_empty_pct=pct(p["empty_pct"]), p_top=p["top_n"], p_top_pct=pct(p["top_pct"]),
        p_top_text=html.escape((p["top_text"] or "(빈 문자열)")[:70]),
        axis_rows=axis_rows, group_rows=group_rows,
        items_json=json.dumps(data["items"], ensure_ascii=False),
        ko_json=json.dumps(FIELD_KO, ensure_ascii=False))

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"out": args.out, "rows": n,
                      "groups": {k: v["n"] for k, v in data["groups"].items()}}, ensure_ascii=False))
    print(f"\n브라우저로 열기: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
