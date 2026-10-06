# -*- coding: utf-8 -*-
"""사람 평가 시트(human_eval_sheet.csv)를 **한 파일 HTML**로 — 평가자가 브라우저에서 바로 점수를 매기고 CSV 로 내려받는다. `[2026-10-06 사용자 지시]`

    python build_html.py            →  human_eval_sheet.html (같은 폴더)

★시트의 「층」 · 「기계 판정」은 `human_eval_key.json` 에만 있고 **HTML 에 넣지 않는다**(답의 좋고 나쁨을 미리 알려 주지 않으려고).
★HTML 의 내려받기 CSV 는 `human_eval_sheet.csv` 와 같은 열이라 `python score.py <파일>` 이 그대로 읽는다.
★점수는 평가자의 브라우저(localStorage)에만 저장된다 — 서버로 보내지 않는다.
"""
import csv
import json
import os
import sys
from html import escape as html_escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8")

rows = list(csv.DictReader(open(os.path.join(HERE, "human_eval_sheet.csv"), encoding="utf-8-sig")))
data = [{"id": r["id"], "kind": r["종류"], "input": r["고객 입력"], "answer": r["시스템 답"]} for r in rows]
assert len(data) == 35 and all(d["id"] and d["input"] and d["answer"] for d in data), "시트 모양이 다르다"
html = open(os.path.join(HERE, "human_eval_template.html"), encoding="utf-8").read()
CRIT = ["정확성", "근거충실", "질문에맞음", "자연스러움", "안전성"]


def static_rows() -> str:
    """★스크립트가 안 도는 곳(파일 미리보기 · 메일 · 일부 앱 안의 보기)에서도 **내용이 보이게** 35행을 글자로 미리 적어 둔다. 스크립트가 돌면 이 부분은 숨고 점수 입력 화면이 대신 나온다."""
    out = ['<div class="nojs"><div class="banner"><b>이 화면은 점수를 누를 수 없는 미리보기입니다.</b> '
           '점수를 매기려면 이 파일을 <b>크롬 · 엣지 · 사파리 같은 브라우저로 직접 여세요</b>(파일을 더블클릭하거나 브라우저로 끌어다 놓기). '
           '아래는 35행의 내용이고, 인쇄해서 종이로 점수(1~5점)를 적어도 됩니다.</div>']
    for number, d in enumerate(data, start=1):
        blank = "".join(f"<span>{c} ____</span>" for c in CRIT)
        out.append(f'<div class="card rowcard"><div class="row"><span class="pill kind">{html_escape(d["kind"])}</span>'
                   f'<span class="pill">{d["id"]} · {number}/{len(data)}</span></div>'
                   f'<div class="lab">{"원문(한국어) · 번역 언어" if "번역" in d["kind"] else "고객 입력"}</div><div class="box">{html_escape(d["input"])}</div>'
                   f'<div class="lab">{"번역 결과" if "번역" in d["kind"] else "시스템 답"}</div><div class="box">{html_escape(d["answer"])}</div>'
                   f'<div class="blank">{blank}</div></div>')
    out.append("</div>")
    return "\n".join(out)
# `</script>` 가 글 안에 있어도 깨지지 않게
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
out = os.path.join(HERE, "human_eval_sheet.html")
open(out, "w", encoding="utf-8").write(html.replace("__DATA__", payload).replace("<!--STATIC-->", static_rows()))
print(f"만들었다 — {len(data)}행 · {os.path.getsize(out):,}바이트 · {out}")
