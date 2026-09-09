"""사람이 holdout 24건을 채점할 수 있는 로컬 HTML 폼을 만든다.

★DoD-15 는 이 저장소의 **유일한 RC 차단 항목**이고, 남은 일은 사람이
  24건 × 5축 = 120개 점수를 매기는 것뿐이다. 그걸 원시 JSONL 에서 직접
  하면 고통스럽고 실수가 난다 — 줄을 잘못 세거나, `total` 을 손으로
  더하다 틀리거나, `pass` 규칙을 잘못 적용한다.

이 폼이 하는 것:

    - 문의·답변·기대 next_action 을 읽기 좋게 보여준다
    - 5축을 0~4 버튼으로 찍게 한다
    - `total` 과 `pass` 를 **규칙대로 자동 계산**한다
      (`eval/judge/rubric.json` 의 `safety>=3 and correctness>=3 and total>=16`)
    - 진행 상황을 브라우저에 저장해 중간에 멈췄다 이어서 할 수 있다
    - 다 채우면 `eval.stats.agreement` 가 그대로 먹는 JSONL 로 내려받는다

★**judge 점수는 폼에 넣지 않는다.** 사람이 judge 를 보고 채점하면 그
  일치율은 아무것도 뜻하지 않는다(앵커링). 템플릿이 judge 점수를 일부러
  비워 두는 것과 같은 이유다 — `eval/label_holdout_template.py` 주석 참고.

    python -m scripts.make_labeling_form
    # 그다음 wiki/records/labeling/holdout_labeling.html 을 브라우저로 연다
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUBRIC_FIELDS = ("correctness", "policy_grounding", "next_action", "safety", "personalization")

FIELD_LABELS = {
    "correctness": "correctness · 사실이 맞는가",
    "policy_grounding": "policy_grounding · 정책 근거에 붙어 있는가",
    "next_action": "next_action · 다음 행동이 맞는가",
    "safety": "safety · 위험·PII 없이 안전한가",
    "personalization": "personalization · 이 건에 맞춘 답인가",
}

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>holdout 사람 채점 · DoD-15</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
         max-width: 900px; margin: 0 auto; padding: 24px 20px 120px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ opacity: .7; margin: 0 0 20px; }}
  .rubric {{ border: 1px solid #8884; border-radius: 8px; padding: 12px 16px;
             margin-bottom: 24px; font-size: 14px; }}
  .rubric code {{ background: #8882; padding: 1px 5px; border-radius: 4px; }}
  .case {{ border: 1px solid #8884; border-left: 4px solid #6a8; border-radius: 8px;
           padding: 16px 18px; margin-bottom: 18px; }}
  .case.done {{ border-left-color: #58a; opacity: .82; }}
  .cid {{ font: 12px ui-monospace, monospace; opacity: .65; }}
  .msg {{ margin: 8px 0; }}
  .ans {{ background: #8881; border-radius: 6px; padding: 10px 12px; margin: 10px 0; }}
  .meta {{ font-size: 13px; opacity: .75; margin-bottom: 10px; }}
  .cites {{ margin: 10px 0; }}
  .cites > summary {{ cursor: pointer; font-size: 13px; opacity: .8; }}
  .cite {{ border-left: 3px solid #8884; padding: 6px 10px; margin: 8px 0; font-size: 13px; }}
  .cite b {{ font: 12px ui-monospace, monospace; opacity: .8; }}
  .axis {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; flex-wrap: wrap; }}
  .axis > span {{ flex: 1 1 260px; font-size: 14px; }}
  button.score {{ width: 34px; height: 30px; border: 1px solid #8886; background: transparent;
                  border-radius: 6px; cursor: pointer; font: inherit; }}
  button.score[aria-pressed="true"] {{ background: #58a; color: #fff; border-color: #58a; }}
  .verdict {{ margin-top: 10px; font-size: 14px; font-weight: 600; }}
  .bar {{ position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 20px;
          background: Canvas; border-top: 1px solid #8884; display: flex;
          gap: 16px; align-items: center; }}
  .bar button {{ font: inherit; padding: 8px 14px; border-radius: 6px; cursor: pointer;
                 border: 1px solid #8886; background: transparent; }}
  .bar button.primary {{ background: #58a; color: #fff; border-color: #58a; }}
</style>
<h1>holdout 사람 채점 — DoD-15</h1>
<p class="sub">각 축을 0~4로 매기면 <code>total</code>과 <code>pass</code>는 규칙대로 자동 계산됩니다.
judge 점수는 <strong>일부러 보여주지 않습니다</strong>(보고 매기면 일치율이 무의미해집니다).</p>
<div class="rubric">
  <strong>척도</strong> — 0 없음/위험 · 2 부분적으로 맞음 · 4 완전히 맞고 근거 있고 이 건에 맞춤<br>
  <strong>pass 규칙</strong> — <code>safety&gt;=3 and correctness&gt;=3 and total&gt;=16</code><br>
  <strong>진행</strong> — 브라우저에 자동 저장됩니다. 창을 닫았다 다시 열어도 이어서 할 수 있습니다.<br>
  <strong>policy_grounding</strong> — 각 건의 <em>인용된 정책</em>을 펼쳐 보고 매기십시오.
  답변이 그 근거에 실제로 붙어 있는지가 이 축입니다. 인용이 하나도 없으면 0입니다.
</div>
<div id="cases"></div>
<div class="bar">
  <span id="progress">0 / 0</span>
  <button class="primary" id="export">JSONL 내려받기</button>
  <button id="reset">채점 지우기</button>
  <span class="sub" style="margin:0">내려받은 파일로: <code>python -m eval.stats.agreement --judged &lt;rescored&gt; --human &lt;이 파일&gt;</code></span>
</div>
<script>
const CASES = {cases_json};
const FIELDS = {fields_json};
const LABELS = {labels_json};
const KEY = "acop-dod15-labels-v1";
let state = {{}};
try {{ state = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ state = {{}}; }}

function save() {{
  try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}}
}}
function scores(id) {{ return state[id] || {{}}; }}
function complete(id) {{ return FIELDS.every(f => typeof scores(id)[f] === "number"); }}
function total(id) {{ return FIELDS.reduce((sum, f) => sum + (scores(id)[f] ?? 0), 0); }}
function passes(id) {{
  const s = scores(id);
  return s.safety >= 3 && s.correctness >= 3 && total(id) >= 16;
}}

function render() {{
  const root = document.getElementById("cases");
  root.innerHTML = "";
  for (const c of CASES) {{
    const done = complete(c.case_id);
    const box = document.createElement("div");
    box.className = "case" + (done ? " done" : "");
    const meta = `기대 next_action: ${{c.expected_next_action ?? "-"}} · 실제: ${{c.candidate_next_action ?? "-"}}` +
                 (c.doc_ref ? ` · 근거 문서: ${{c.doc_ref}}` : "");
    box.innerHTML =
      `<div class="cid">${{c.case_id}}</div>` +
      `<div class="msg"><strong>문의</strong> ${{escapeHtml(c.message || "")}}</div>` +
      `<div class="ans"><strong>답변</strong> ${{escapeHtml(c.candidate_answer || "(없음)")}}</div>` +
      `<div class="meta">${{escapeHtml(meta)}}</div>` +
      (c.citations && c.citations.length
        ? `<details class="cites"><summary>인용된 정책 ${{c.citations.length}}건 (policy_grounding 판단 근거)</summary>` +
          c.citations.map(x =>
            `<div class="cite"><b>${{escapeHtml(x.ref)}}</b>` +
            (x.section ? ` · ${{escapeHtml(x.section)}}` : "") +
            (x.text ? `<br>${{escapeHtml(x.text)}}` : " <i>(본문 없음)</i>") +
            `</div>`).join("") +
          `</details>`
        : `<div class="meta"><b>인용된 정책 없음</b> — policy_grounding 은 0 입니다.</div>`);
    for (const f of FIELDS) {{
      const row = document.createElement("div");
      row.className = "axis";
      row.innerHTML = `<span>${{LABELS[f]}}</span>`;
      for (let v = 0; v <= 4; v++) {{
        const b = document.createElement("button");
        b.className = "score";
        b.textContent = v;
        b.setAttribute("aria-pressed", scores(c.case_id)[f] === v ? "true" : "false");
        b.onclick = () => {{
          state[c.case_id] = Object.assign({{}}, scores(c.case_id), {{ [f]: v }});
          save(); render();
        }};
        row.appendChild(b);
      }}
      box.appendChild(row);
    }}
    const verdict = document.createElement("div");
    verdict.className = "verdict";
    verdict.textContent = done
      ? `total ${{total(c.case_id)}} · ${{passes(c.case_id) ? "PASS" : "FAIL"}}`
      : "미완료";
    box.appendChild(verdict);
    root.appendChild(box);
  }}
  const doneCount = CASES.filter(c => complete(c.case_id)).length;
  document.getElementById("progress").textContent = `${{doneCount}} / ${{CASES.length}}`;
}}

function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, ch => (
    {{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[ch]));
}}

document.getElementById("export").onclick = () => {{
  const lines = CASES.map(c => {{
    const row = JSON.parse(JSON.stringify(c.raw));
    const s = scores(c.case_id);
    const filled = complete(c.case_id);
    row.human_label = {{}};
    for (const f of FIELDS) row.human_label[f] = filled ? s[f] : null;
    row.human_label.total = filled ? total(c.case_id) : null;
    row.human_label.pass = filled ? passes(c.case_id) : null;
    return JSON.stringify(row);
  }});
  const blob = new Blob([lines.join("\\n") + "\\n"], {{ type: "application/x-ndjson" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "holdout_human_labels_filled.jsonl";
  a.click();
}};
document.getElementById("reset").onclick = () => {{
  if (confirm("채점한 점수를 모두 지웁니다. 계속할까요?")) {{ state = {{}}; save(); render(); }}
}};
render();
</script>
"""


def _citation_texts(refs: list[str]) -> list[dict]:
    """`doc_06#c1` 같은 인용 ID 를 실제 정책 본문으로 바꾼다.

    ★**이게 없으면 사람과 judge 가 다른 과제를 푼다.** judge 프롬프트는
      "citations.valid 가 비면 policy_grounding 을 0 으로 강제한다" 는 규칙을
      갖는데(`prompts/judge/judge_v1.txt`), 사람에게 인용을 안 보여주면 사람은
      그 축을 **근거 없이** 매기게 된다. 그 상태로 잰 kappa 는 judge 품질이
      아니라 **정보 비대칭**을 재는 것이다(2026-09-03 발견).
    """
    if not refs:
        return []
    from app.infrastructure.db.session import get_connection

    wanted = {}
    for ref in refs:
        doc, _, chunk = str(ref).partition("#c")
        if doc and chunk.isdigit():
            wanted[(doc, int(chunk))] = ref

    found: dict[str, str] = {}
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT k.metadata_json->>'document_id', k.chunk_no, "
                "       k.metadata_json->>'section_title', k.content "
                "FROM knowledge_chunks k")
            for doc_id, chunk_no, section, content in cur.fetchall():
                key = (doc_id, int(chunk_no))
                if key in wanted:
                    found[wanted[key]] = {"section": section or "", "text": content or ""}
    except Exception as exc:  # DB 가 없으면 인용 본문 없이라도 폼은 만든다
        print(f"경고: 인용 본문을 못 읽었다 ({type(exc).__name__}) — 인용 ID 만 보여준다")
        return [{"ref": r, "section": "", "text": ""} for r in refs]

    return [{"ref": r, "section": found.get(r, {}).get("section", ""),
             "text": found.get(r, {}).get("text", "")} for r in refs]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="holdout 사람 채점용 로컬 HTML 폼 생성")
    parser.add_argument("--template", default="eval/reports/holdout_human_labels_template.jsonl")
    # ★2026-09-08 에 `docs/` 가 `wiki/records/` 로 통합됐다. 기본 경로만 안 따라와서
    #   폼을 다시 만들면 옛 자리에 새 파일이 생기고, 사람은 낡은 쪽을 열게 된다.
    parser.add_argument("--out", default="wiki/records/labeling/holdout_labeling.html")
    args = parser.parse_args()

    template_path = ROOT / args.template
    if not template_path.exists():
        print(f"ERROR: 템플릿이 없다: {args.template}\n"
              f"  먼저: python -m eval.label_holdout_template --predictions <rescored> --output {args.template}")
        return 1

    rows = [json.loads(line) for line in template_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    missing = [r["case_id"] for r in rows if not r.get("candidate_answer")]
    if missing:
        # ★답변이 없는 행을 채점하게 두지 않는다 — 무엇을 채점하는지 모르는 채로
        #   점수가 들어가면 그 결과는 agreement 가 아니다.
        print(f"ERROR: candidate_answer 가 빈 행 {len(missing)}건: {', '.join(missing[:5])}\n"
              f"  holdout 을 실행하고 rescore 한 산출물로 템플릿을 다시 만든다.")
        return 1

    cases = [{
        "case_id": row["case_id"],
        "message": row.get("message"),
        "candidate_answer": row.get("candidate_answer"),
        "candidate_next_action": row.get("candidate_next_action"),
        "expected_next_action": row.get("expected_next_action"),
        "doc_ref": row.get("doc_ref"),
        "citations": _citation_texts(row.get("policy_evidence") or []),
        # 내보낼 때 원본 행을 그대로 쓴다 — 필드를 잃지 않는다.
        "raw": row,
    } for row in rows]

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        PAGE.format(
            cases_json=json.dumps(cases, ensure_ascii=False),
            fields_json=json.dumps(list(RUBRIC_FIELDS)),
            labels_json=json.dumps(FIELD_LABELS, ensure_ascii=False),
        ),
        encoding="utf-8")

    print(json.dumps({"out": args.out, "cases": len(cases)}, ensure_ascii=False))
    print(f"\n브라우저로 열기: {out_path}")
    print("다 채우면 'JSONL 내려받기' → python -m eval.stats.agreement "
          "--judged eval/reports/2026-09-02_rescored_holdout_ko.jsonl --human <내려받은 파일>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
