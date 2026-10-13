"""검토 준비본을 Markdown과 같은 내용의 로컬 HTML로 만든다."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import html
import shutil
import markdown

BASE = Path(__file__).resolve().parent
stamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d_%H%M%S")
css = """
*{box-sizing:border-box}body{margin:0;background:#fbfcfd;color:#161c28;font-family:'Noto Sans KR','Malgun Gothic',sans-serif;font-size:16px;line-height:1.75}main{max-width:1040px;margin:auto;padding:40px 32px}h1{font-size:30px;line-height:1.4}h2{font-size:23px;margin-top:40px}h3{font-size:19px}a{color:#2f5bd8}code{font-size:.9em;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}th,td{padding:12px;border:1px solid #dbe0ea;text-align:left;vertical-align:top}th{background:#f1f4f8}blockquote{border-left:4px solid #a8720c;margin:0;padding:12px 20px;background:rgba(168,114,12,.1)}.meta{font-size:13px;color:#6b7488;overflow-wrap:anywhere}svg{display:block;width:100%;height:auto}svg text{font-family:'Geist','Noto Sans KR','Malgun Gothic',sans-serif;fill:#161c28;text-anchor:middle;font-size:16px}svg .label{font-size:12px;font-weight:500}.figure{overflow:auto}figure{margin:32px 0}figcaption{font-size:14px;color:#6b7488}@media(max-width:600px){main{padding:24px 16px}table{font-size:12px}td,th{padding:8px}.figure svg{min-width:900px}}@media print{main{max-width:none;padding:0}h2,h3{break-after:avoid}tr,figure{break-inside:avoid}table{font-size:11px}a{color:inherit;text-decoration:none}.figure{overflow:visible}.figure svg{min-width:0}}
"""
flow = (BASE / "finalization-flow.html").read_text(encoding="utf-8")
svg = flow[flow.index("<svg "):flow.index("</svg>") + 6]
for filename in ["v12-outline", "baseline-outline", "review-checklist", "integration-table"]:
    source = BASE / (filename + ".md")
    raw = source.read_text(encoding="utf-8")
    body = raw
    if body.startswith("---\n"):
        body = body.split("---\n", 2)[2]
    rendered = markdown.markdown(body, extensions=["tables", "fenced_code"])
    figure = f'<figure><div class="figure">{svg}</div><figcaption>최종 통합 절차 — 필수 근거가 부족하면 보완 대기로 종료합니다.</figcaption></figure>' if filename in {"baseline-outline", "review-checklist"} else ""
    target = source.with_suffix(".html")
    if target.exists():
        backup = BASE / "_backup" / (stamp + "_preparation_html")
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup / target.name)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    title = next(line.removeprefix("# ") for line in body.splitlines() if line.startswith("# "))
    target.write_text(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="source-sha256" content="{sha}"><title>{html.escape(title)}</title><style>{css}</style></head><body><main><p class="meta">검토 준비본 · 최종 완료본 아님 · 원문 SHA-256 {sha}</p>{rendered}{figure}</main></body></html>', encoding="utf-8")
    print(target.name, sha)
