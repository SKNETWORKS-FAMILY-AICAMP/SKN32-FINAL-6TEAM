"""capability 선택을 사람이 감사할 수 있는 로컬 HTML 폼을 만든다.

★`docs/reports/2026-09-03_S-CAPABILITY-SELECTION-측정_리포트.md` 가 지금 방식의
  정확도를 **41.7%(25/60)** 로 쟀다. 낮다. 그런데 낮은 이유가 둘로 갈린다:

      (a) 휴리스틱이 틀렸다      → 규칙을 고치면 오른다
      (b) **라벨이 틀렸다**       → 규칙을 고쳐도 안 오른다. 라벨을 고쳐야 한다

  이 둘을 코드로는 못 가른다. 사람이 문장을 읽고 "이 문의에 어느 capability 가
  맞나" 를 판정해야 한다. 그 일을 원시 JSONL 에서 하면 35건 × (문장 읽기 +
  선택지 비교)라 실수가 난다.

이 폼이 하는 것:

    - 어긋난 건을 **먼저** 보여준다(일치하는 건은 접어 둔다)
    - 문의 문장과 함께 라벨·휴리스틱 선택을 나란히 놓는다
    - 그 팀이 실제로 가진 capability 목록에서 고르게 한다 — 없는 것을 못 고른다
    - 진행 상황을 브라우저에 저장한다
    - 판정 결과를 JSONL 로 내려받는다

★**정답을 미리 보여주지 않는다.** 라벨과 휴리스틱을 나란히 보여주되 어느 쪽이
  "정답" 인지 표시하지 않는다. 표시하면 사람이 그쪽으로 끌린다 — DoD-15
  라벨링 폼이 judge 점수를 숨기는 것과 같은 이유다.

    python -m scripts.make_capability_audit_form
    # 그다음 docs/labeling/capability_audit.html 을 브라우저로 연다
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>capability 선택 감사</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
         max-width: 960px; margin: 0 auto; padding: 24px 20px 140px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ opacity: .72; margin: 0 0 18px; }}
  .note {{ border: 1px solid #8884; border-radius: 8px; padding: 12px 16px;
           margin-bottom: 22px; font-size: 14px; }}
  .case {{ border: 1px solid #8884; border-left: 4px solid #c85; border-radius: 8px;
           padding: 15px 18px; margin-bottom: 16px; }}
  .case.agree {{ border-left-color: #6a8; }}
  .case.done {{ border-left-color: #58a; opacity: .8; }}
  .cid {{ font: 12px ui-monospace, monospace; opacity: .65; }}
  .msg {{ margin: 8px 0 10px; font-size: 15px; }}
  .pair {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; font-size: 13px; }}
  .pair div {{ background: #8881; padding: 5px 10px; border-radius: 6px; }}
  .pair code {{ font: 12px ui-monospace, monospace; }}
  .opts {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  button.opt {{ font: 13px ui-monospace, monospace; padding: 6px 10px; cursor: pointer;
                border: 1px solid #8886; background: transparent; border-radius: 6px; }}
  button.opt[aria-pressed="true"] {{ background: #58a; color: #fff; border-color: #58a; }}
  button.opt.undecidable {{ font-family: inherit; font-style: italic; }}
  button.opt.undecidable[aria-pressed="true"] {{ background: #c85; border-color: #c85; }}
  .verdict {{ margin-top: 9px; font-size: 13px; font-weight: 600; }}
  .bar {{ position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 20px;
          background: Canvas; border-top: 1px solid #8884; display: flex;
          gap: 14px; align-items: center; flex-wrap: wrap; }}
  .bar button {{ font: inherit; padding: 8px 14px; border-radius: 6px; cursor: pointer;
                 border: 1px solid #8886; background: transparent; }}
  .bar button.primary {{ background: #58a; color: #fff; border-color: #58a; }}
  details {{ margin-top: 20px; }}
  summary {{ cursor: pointer; opacity: .75; }}
</style>
<h1>capability 선택 감사</h1>
<p class="sub">이 문의에는 어느 capability 가 맞습니까? 문장을 읽고 고르십시오.</p>
<div class="note">
  지금 자동 선택의 라벨 대비 정확도는 <strong>41.7% (25/60)</strong>입니다.
  낮은 이유가 <strong>휴리스틱이 틀려서</strong>인지 <strong>라벨이 틀려서</strong>인지를
  코드로는 가를 수 없어 사람 판정이 필요합니다.<br>
  아래 두 값은 참고로 나란히 보여주지만 <strong>어느 쪽이 정답인지 표시하지 않습니다</strong> —
  보고 끌리면 감사가 무의미해집니다.<br>
  <strong>진행</strong> — 브라우저에 자동 저장됩니다.<br>
  ★<strong>정할 수 없으면 「이 문장만으로는 정할 수 없다」를 고르십시오.</strong>
  억지로 하나를 고르면 <em>애매함이 불일치로 둔갑</em>합니다. LLM 실험에서
  같은 두 기능 사이를 <strong>양방향으로</strong> 틀리는 것이 관측됐는데, 그건
  경계가 한 문장에 없다는 뜻일 수 있습니다 — 그 사실 자체가 이 감사의 결과입니다.
</div>
<div id="cases"></div>
<details>
  <summary id="agreesum">라벨과 자동 선택이 일치한 건 (접힘)</summary>
  <div id="agree"></div>
</details>
<div class="bar">
  <span id="progress">0 / 0</span>
  <button class="primary" id="export">판정 내려받기</button>
  <button id="reset">판정 지우기</button>
  <span class="sub" style="margin:0">불일치 건부터 위에 나옵니다.</span>
</div>
<script>
const CASES = {cases_json};
const UNDECIDABLE = "__undecidable__";
const KEY = "acop-capability-audit-v1";
let state = {{}};
try {{ state = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ state = {{}}; }}
function save() {{ try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}} }}

function esc(s) {{
  return String(s == null ? "" : s).replace(/[&<>"']/g, ch => (
    {{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[ch]));
}}

function card(c) {{
  const chosen = state[c.case_id];
  const box = document.createElement("div");
  box.className = "case" + (c.agree ? " agree" : "") + (chosen ? " done" : "");
  box.innerHTML =
    `<div class="cid">${{esc(c.case_id)}} · team ${{esc(c.team_id)}} · intent ${{esc(c.intent)}}</div>` +
    `<div class="msg">${{esc(c.message)}}</div>` +
    `<div class="pair">` +
      `<div>데이터셋 라벨 <code>${{esc(c.label)}}</code></div>` +
      `<div>자동 선택 <code>${{esc(c.heuristic)}}</code></div>` +
    `</div>`;
  const opts = document.createElement("div");
  opts.className = "opts";
  for (const cap of c.capabilities.concat([UNDECIDABLE])) {{
    const b = document.createElement("button");
    b.className = "opt" + (cap === UNDECIDABLE ? " undecidable" : "");
    b.textContent = cap === UNDECIDABLE ? "이 문장만으로는 정할 수 없다" : cap;
    b.setAttribute("aria-pressed", chosen === cap ? "true" : "false");
    b.onclick = () => {{ state[c.case_id] = cap; save(); render(); }};
    opts.appendChild(b);
  }}
  box.appendChild(opts);
  const v = document.createElement("div");
  v.className = "verdict";
  if (!chosen) {{ v.textContent = "미판정"; }}
  else if (chosen === UNDECIDABLE) {{ v.textContent = "한 문장으로는 정할 수 없음 — 경계 문제로 기록됩니다"; }}
  else {{
    const marks = [];
    if (chosen === c.label) marks.push("라벨과 같음");
    if (chosen === c.heuristic) marks.push("자동 선택과 같음");
    v.textContent = marks.length ? marks.join(" · ") : "둘 다 아님";
  }}
  box.appendChild(v);
  return box;
}}

function render() {{
  const mism = document.getElementById("cases");
  const agr = document.getElementById("agree");
  mism.innerHTML = ""; agr.innerHTML = "";
  let n = 0;
  for (const c of CASES) {{
    (c.agree ? agr : mism).appendChild(card(c));
    if (state[c.case_id]) n++;
  }}
  document.getElementById("progress").textContent = `${{n}} / ${{CASES.length}}`;
  const a = CASES.filter(c => c.agree).length;
  document.getElementById("agreesum").textContent =
    `라벨과 자동 선택이 일치한 건 ${{a}}개 (접힘 — 확인만 하려면 펼치십시오)`;
}}

document.getElementById("export").onclick = () => {{
  const lines = CASES.map(c => JSON.stringify({{
    case_id: c.case_id, message: c.message, intent: c.intent, team_id: c.team_id,
    dataset_label: c.label, heuristic: c.heuristic,
    human_capability: (state[c.case_id] && state[c.case_id] !== UNDECIDABLE) ? state[c.case_id] : null,
    undecidable_from_message_alone: state[c.case_id] === UNDECIDABLE,
    label_is_right: (state[c.case_id] && state[c.case_id] !== UNDECIDABLE) ? state[c.case_id] === c.label : null,
    heuristic_is_right: (state[c.case_id] && state[c.case_id] !== UNDECIDABLE) ? state[c.case_id] === c.heuristic : null,
  }}));
  const blob = new Blob([lines.join("\\n") + "\\n"], {{ type: "application/x-ndjson" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "capability_audit_filled.jsonl";
  a.click();
}};
document.getElementById("reset").onclick = () => {{
  if (confirm("판정을 모두 지웁니다. 계속할까요?")) {{ state = {{}}; save(); render(); }}
}};
render();
</script>
"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="capability 선택 감사용 로컬 HTML 폼")
    parser.add_argument("--dataset", default="eval/datasets/golden.jsonl")
    parser.add_argument("--out", default="docs/labeling/capability_audit.html")
    args = parser.parse_args()

    from app.composition import build_registry
    from app.core.registry import TeamRegistry

    registry = build_registry()
    rows = [json.loads(line) for line in (ROOT / args.dataset).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    labeled = [r for r in rows if r.get("expected_capability")]
    if not labeled:
        print(f"ERROR: {args.dataset} 에 expected_capability 라벨이 없다. 감사할 것이 없다.")
        return 1

    cases = []
    for row in labeled:
        intent = row.get("expected_intent")
        try:
            entry = registry.resolve(case_type=intent or "", intent=intent)
        except Exception:
            continue
        heuristic = TeamRegistry.capability_for(entry, intent, input_text=row["message"])
        label = row["expected_capability"]
        cases.append({
            "case_id": row["case_id"], "message": row["message"], "intent": intent,
            "team_id": entry.manifest.team_id,
            "capabilities": list(entry.manifest.capabilities),
            "label": label, "heuristic": heuristic,
            "agree": label == heuristic,
        })

    # ★어긋난 건이 먼저 오게 둔다 — 감사의 목적이 그것이다.
    cases.sort(key=lambda c: (c["agree"], c["case_id"]))

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(PAGE.format(cases_json=json.dumps(cases, ensure_ascii=False)),
                        encoding="utf-8")

    mismatch = sum(1 for c in cases if not c["agree"])
    print(json.dumps({"out": args.out, "cases": len(cases), "mismatch": mismatch,
                      "agree": len(cases) - mismatch}, ensure_ascii=False))
    print(f"\n브라우저로 열기: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
