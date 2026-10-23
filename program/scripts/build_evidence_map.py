"""근거 지도 HTML 생성기.

두 곳에서 읽어 한 장으로 만든다. 손으로 옮기지 않는다.

    team_branch/output/A-COPilot_제출표.xlsx   근거출처 41건 (정본)
    program/산출물양식/[기획] 프로젝트 기획서_A-COPilot.docx   본문 인용 위치
    program/briefing/_근거지도_보강.json        세그먼트 검증 보강분 (2026-09-01)

    python program/scripts/build_evidence_map.py

결과: program/briefing/A-COP_근거지도.html
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import openpyxl
from docx import Document

ROOT = Path(__file__).resolve().parents[2]
XLSX = ROOT / "team_branch" / "output" / "A-COPilot_제출표.xlsx"
DOCX = ROOT / "program" / "산출물양식" / "[기획] 프로젝트 기획서_A-COPilot.docx"
EXTRA = ROOT / "program" / "briefing" / "_근거지도_보강.json"
OUT = ROOT / "program" / "briefing" / "A-COP_근거지도.html"

#: 제출표 41건의 주제군. 엑셀에 이름 칸이 없어 내용을 보고 붙인다.
BASE_GROUPS = {
    "A": ("봇·자동화 트래픽", "웹 트래픽의 절반이 이미 사람이 아니라는 것"),
    "B": ("AI 경유 커머스 유입", "고객이 자기 에이전트로 들어오기 시작했다는 것"),
    "C": ("시장 규모", "AI 고객서비스 시장이 얼마나 되는가"),
    "D": ("도입과 작동의 격차", "도입은 했는데 왜 안 굴러가는가"),
    "E": ("처리 비용과 가격 구조", "사람과 AI의 건당 비용, 과금 방식의 함정"),
    "F": ("규제와 자체 호스팅 수요", "왜 데이터를 안에 두라는 요구가 생기는가"),
    "G": ("경쟁 제품의 구조적 공백", "1군 제품이 공개 자료로 증명하지 못하는 것"),
    "H": ("에이전트 상호운용 표준", "A2A·AP2·UCP·MCP — 우리가 붙을 규약"),
    "I": ("기획서 작성 방법론", "문서를 어떻게 쓸지에 대한 참고. 본문 인용 대상이 아니다"),
}

GRADE_CLASS = [("미확인", "gx"), ("미기재", "gn"), ("불명", "gx"), ("1차", "g1"), ("2차", "g2")]


def grade_class(g: str) -> str:
    for key, cls in GRADE_CLASS:
        if key in g:
            return cls
    return "gn"


def esc(s) -> str:
    return html.escape(str(s or ""))


def host(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url or "").split("/")[0]


def load_base():
    ws = openpyxl.load_workbook(XLSX).active
    src = {}
    for r in range(1, ws.max_row + 1):
        key = ws.cell(r, 1).value
        if not (key and re.fullmatch(r"[A-Z]\d+", str(key).strip())):
            continue
        cells = [ws.cell(r, c) for c in range(1, 8)]
        link = next((c.hyperlink.target for c in cells if c.hyperlink), None)
        src[str(key).strip()] = {
            "내용": str(cells[1].value or "").strip(),
            "기관": str(cells[2].value or "").strip(),
            "등급": str(cells[3].value or "").strip(),
            "링크": link or "",
        }
    return src


def load_citations():
    doc = Document(str(DOCX))
    sec, used = None, {}
    for p in doc.paragraphs:
        t = p.text.strip()
        if p.style.name == "Heading 1":
            sec = t
        flat = set()
        for m in re.findall(r"\[([A-Z]\d+(?:\s*,\s*[A-Z]\d+)*)[^\]]*\]", t):
            flat |= set(re.findall(r"[A-Z]\d+", m))
        for c in flat:
            used.setdefault(c, []).append({"절": sec, "문장": re.sub(r"^-\s*", "", t)})
    return used


def sortkey(k):
    return (k[0], int(k[1:]))


def card(code, s, claims, unused_why):
    gc = grade_class(s["등급"])
    if claims:
        c = claims[0]
        body = (f'<div class="claim"><span class="claim-sec">{esc(c["절"])}</span>'
                f'<p>{esc(c["문장"])}</p></div>')
    else:
        body = f'<div class="claim claim--none"><p>{esc(unused_why)}</p></div>'
    star = " src--star" if s["내용"].startswith("★") else ""
    fact = s["내용"].lstrip("★").strip()
    return f"""      <article class="src{'' if claims else ' src--unused'}{star}">
        <div class="src-head">
          <a class="code" href="{esc(s['링크'])}" target="_blank" rel="noopener">{esc(code)}</a>
          <span class="pill pill--{gc}">{esc(s['등급'])}</span>
        </div>
        <p class="fact">{esc(fact)}</p>
        <p class="org">{esc(s['기관'])} · <a href="{esc(s['링크'])}" target="_blank" rel="noopener">{esc(host(s['링크']))}</a></p>
        {body}
      </article>"""


def group_section(letter, name, blurb, members, src, used, unused_why, cited_label=True):
    cited = sum(1 for k in members if k in used)
    cards = "\n".join(card(k, src[k], used.get(k, []), unused_why) for k in members)
    count = (f"{len(members)}건 중 <strong>{cited}건</strong> 인용" if cited_label
             else f"<strong>{len(members)}건</strong> · 2026-09-01 보강")
    return f"""  <section class="group">
    <header class="group-head">
      <h2><span class="letter">{letter}</span>{esc(name)}</h2>
      <p class="blurb">{esc(blurb)}</p>
      <p class="count">{count}</p>
    </header>
    <div class="grid">
{cards}
    </div>
  </section>"""


def main():
    base = load_base()
    used = load_citations()
    extra = json.loads(EXTRA.read_text(encoding="utf-8"))
    new_src = {k: {"내용": v["내용"], "기관": v["기관"], "등급": v["등급"], "링크": v["링크"]}
               for k, v in extra["sources"].items()}
    all_src = {**base, **new_src}

    n_base, n_new = len(base), len(new_src)
    n_cited = len(used)
    n_meta = sum(1 for k in base if k[0] == "I")
    n_gap = n_base - n_cited - n_meta

    grades = {"g1": 0, "g2": 0, "gx": 0, "gn": 0}
    for s in all_src.values():
        grades[grade_class(s["등급"])] += 1

    # ── 질문 매핑 ──────────────────────────────────────────────────
    q_rows = []
    for num, q in extra["questions"].items():
        chips = " ".join(
            f'<a class="chip" href="{esc(all_src[c]["링크"])}" target="_blank" rel="noopener">{c}</a>'
            for c in q["근거"] if c in all_src)
        q_rows.append(f"""    <article class="qa">
      <div class="qa-head"><span class="qnum">{esc(num)}</span><h3>{esc(q["질문"])}</h3></div>
      <p class="qa-ans">{esc(q["답"])}</p>
      <div class="chips">{chips}</div>
    </article>""")

    sections = []
    for letter, (name, blurb) in BASE_GROUPS.items():
        members = [k for k in sorted(base, key=sortkey) if k[0] == letter]
        if members:
            why = ("문서를 쓰는 참고 자료라 본문에 인용하지 않는다." if letter == "I"
                   else "확보했으나 본문에서 아직 쓰지 않았다. 보강할 때 먼저 볼 후보다.")
            sections.append(group_section(letter, name, blurb, members, base, used, why))

    for letter, (name, blurb) in extra["groups"].items():
        members = [k for k in sorted(new_src, key=sortkey) if k[0] == letter]
        if members:
            sections.append(group_section(
                letter, name, blurb, members, new_src, {},
                "2026-09-01 보강분. 기획서 본문에는 아직 반영하지 않았다.", cited_label=False))

    seg = lambda cls, n: (f'<span class="seg seg--{cls}" style="flex:{n}"></span>') if n else ""

    page = f"""<title>A-COP 근거 지도</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@500;700&family=IBM+Plex+Sans+KR:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap">
<style>
:root {{
  --paper:#fbfcfe; --surface:#f1f4f8; --raise:#ffffff;
  --ink:#14181f; --dim:#5c6675; --faint:#8b95a5; --line:#dce1e9;
  --mark:#2d4b8e; --star:#9a6a12;
  --g1:#0e6b5c; --g2:#9a6a12; --gx:#a8382c; --gn:#6b7280;
  --g1-bg:#e3f2ee; --g2-bg:#faf0dc; --gx-bg:#fbe9e6; --gn-bg:#eef0f3;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#12151a; --surface:#1a1f27; --raise:#1e242d;
    --ink:#e8ecf2; --dim:#9aa4b2; --faint:#6f7a8a; --line:#2a313c;
    --mark:#88a6e6; --star:#dcaa4c;
    --g1:#5cc7b0; --g2:#dcaa4c; --gx:#e8897c; --gn:#9aa4b2;
    --g1-bg:#123029; --g2-bg:#33280f; --gx-bg:#3a1f1c; --gn-bg:#242a33;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#12151a; --surface:#1a1f27; --raise:#1e242d;
  --ink:#e8ecf2; --dim:#9aa4b2; --faint:#6f7a8a; --line:#2a313c;
  --mark:#88a6e6; --star:#dcaa4c;
  --g1:#5cc7b0; --g2:#dcaa4c; --gx:#e8897c; --gn:#9aa4b2;
  --g1-bg:#123029; --g2-bg:#33280f; --gx-bg:#3a1f1c; --gn-bg:#242a33;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font-family:"IBM Plex Sans KR", system-ui, sans-serif; font-size:15px; line-height:1.72;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1120px; margin:0 auto; padding:56px 28px 96px; }}
.masthead {{ border-bottom:2px solid var(--ink); padding-bottom:26px; margin-bottom:36px; }}
.eyebrow {{ font-family:"IBM Plex Mono", monospace; font-size:11.5px; font-weight:600;
  letter-spacing:.14em; text-transform:uppercase; color:var(--mark); margin:0 0 12px; }}
h1 {{ font-family:"Noto Serif KR", serif; font-weight:700; font-size:clamp(30px,5vw,46px);
  line-height:1.2; margin:0 0 14px; letter-spacing:-.015em; text-wrap:balance; }}
.lede {{ margin:0; max-width:66ch; color:var(--dim); font-size:16px; }}
.lede strong {{ color:var(--ink); font-weight:600; }}
.stats {{ display:flex; flex-wrap:wrap; gap:34px; margin:30px 0 14px; }}
.stat b {{ display:block; font-family:"Noto Serif KR", serif; font-size:32px; line-height:1.1;
  font-weight:700; font-variant-numeric:tabular-nums; }}
.stat span {{ font-size:12.5px; color:var(--faint); }}
.stat--new b {{ color:var(--mark); }}
.stat--gap b {{ color:var(--g2); }}
.bar {{ display:flex; height:9px; border-radius:5px; overflow:hidden; gap:2px; margin:6px 0 12px; }}
.seg {{ display:block; }}
.seg--g1 {{ background:var(--g1); }} .seg--g2 {{ background:var(--g2); }}
.seg--gx {{ background:var(--gx); }} .seg--gn {{ background:var(--gn); }}
.legend {{ display:flex; flex-wrap:wrap; gap:16px; font-size:12.5px; color:var(--dim);
  margin:0; padding:0; list-style:none; }}
.legend li {{ display:flex; align-items:center; gap:7px; }}
.dot {{ width:9px; height:9px; border-radius:2px; flex:none; }}
.dot--g1 {{ background:var(--g1); }} .dot--g2 {{ background:var(--g2); }}
.dot--gx {{ background:var(--gx); }} .dot--gn {{ background:var(--gn); }}
.note {{ margin:30px 0 0; padding:16px 20px; background:var(--surface);
  border-left:3px solid var(--mark); border-radius:0 6px 6px 0; font-size:14px;
  color:var(--dim); max-width:76ch; }}
.note strong {{ color:var(--ink); font-weight:600; }}
.qsec {{ margin-top:56px; }}
.qsec > h2 {{ font-family:"Noto Serif KR", serif; font-size:23px; font-weight:700;
  margin:0 0 8px; letter-spacing:-.01em; }}
.qsec > p {{ margin:0 0 22px; color:var(--dim); font-size:14px; max-width:72ch; }}
.qgrid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:14px; }}
.qa {{ background:var(--surface); border-radius:9px; padding:17px 19px 15px;
  display:flex; flex-direction:column; gap:9px; }}
.qa-head {{ display:flex; align-items:baseline; gap:11px; }}
.qnum {{ font-family:"IBM Plex Mono", monospace; font-size:12px; font-weight:600;
  color:var(--paper); background:var(--ink); min-width:22px; height:22px; border-radius:5px;
  display:inline-flex; align-items:center; justify-content:center; flex:none; padding:0 5px; }}
.qa h3 {{ margin:0; font-size:15px; font-weight:600; line-height:1.5; }}
.qa-ans {{ margin:0; font-size:13.5px; line-height:1.68; color:var(--dim); }}
.chips {{ display:flex; flex-wrap:wrap; gap:5px; }}
.chip {{ font-family:"IBM Plex Mono", monospace; font-size:11px; font-weight:600;
  padding:2px 7px; border-radius:4px; background:var(--raise); border:1px solid var(--line);
  color:var(--mark); text-decoration:none; }}
.chip:hover, .chip:focus-visible {{ border-color:var(--mark); }}
.group {{ margin-top:56px; }}
.group-head {{ margin-bottom:20px; }}
.group-head h2 {{ font-family:"Noto Serif KR", serif; font-size:21px; font-weight:700;
  margin:0 0 6px; display:flex; align-items:baseline; gap:13px; letter-spacing:-.01em; }}
.letter {{ font-family:"IBM Plex Mono", monospace; font-size:13px; font-weight:600;
  color:var(--paper); background:var(--mark); width:26px; height:26px; border-radius:5px;
  flex:none; display:inline-flex; align-items:center; justify-content:center;
  transform:translateY(-2px); }}
.blurb {{ margin:0; color:var(--dim); font-size:14px; max-width:70ch; }}
.count {{ margin:8px 0 0; font-size:12.5px; color:var(--faint); font-variant-numeric:tabular-nums; }}
.count strong {{ color:var(--ink); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:14px; }}
.src {{ background:var(--raise); border:1px solid var(--line); border-radius:9px;
  padding:16px 18px 14px; display:flex; flex-direction:column; gap:9px; }}
.src--unused {{ background:transparent; border-style:dashed; }}
.src--star {{ border-left:3px solid var(--star); }}
.src-head {{ display:flex; align-items:center; justify-content:space-between; gap:10px; }}
.code {{ font-family:"IBM Plex Mono", monospace; font-weight:600; font-size:13.5px;
  color:var(--mark); text-decoration:none; letter-spacing:.02em; }}
.code:hover, .code:focus-visible {{ text-decoration:underline; }}
.pill {{ font-size:11px; font-weight:500; padding:3px 9px; border-radius:20px; white-space:nowrap; }}
.pill--g1 {{ color:var(--g1); background:var(--g1-bg); }}
.pill--g2 {{ color:var(--g2); background:var(--g2-bg); }}
.pill--gx {{ color:var(--gx); background:var(--gx-bg); }}
.pill--gn {{ color:var(--gn); background:var(--gn-bg); }}
.fact {{ margin:0; font-size:14px; line-height:1.62; }}
.org {{ margin:0; font-size:12.5px; color:var(--faint); }}
.org a {{ color:var(--faint); }}
.org a:hover, .org a:focus-visible {{ color:var(--mark); }}
.claim {{ margin-top:2px; padding-top:11px; border-top:1px solid var(--line); }}
.claim-sec {{ display:inline-block; font-family:"IBM Plex Mono", monospace; font-size:10.5px;
  letter-spacing:.08em; text-transform:uppercase; color:var(--faint); margin-bottom:5px; }}
.claim p {{ margin:0; font-size:13px; line-height:1.62; color:var(--dim); }}
.claim--none p {{ color:var(--faint); font-style:italic; }}
a:focus-visible, .code:focus-visible, .chip:focus-visible {{ outline:2px solid var(--mark);
  outline-offset:3px; border-radius:3px; }}
footer {{ margin-top:64px; padding-top:22px; border-top:1px solid var(--line);
  font-size:12.5px; color:var(--faint); }}
footer code {{ font-family:"IBM Plex Mono", monospace; font-size:12px; }}
@media (max-width:560px) {{ .wrap {{ padding:36px 18px 64px; }}
  .grid, .qgrid {{ grid-template-columns:1fr; }} }}
</style>

<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">프로젝트 기획서 · 근거출처</p>
    <h1>A-COP 근거 지도</h1>
    <p class="lede">기획서의 주장이 무엇에 기대고 있는지, 그 근거가 얼마나 단단한지를 한 장에 편다.
      제출표 {n_base}건 중 본문이 인용한 것은 {n_cited}건이고,
      <strong>2026-09-01에 세그먼트 검증용 {n_new}건을 보강했다.</strong> 쓰지 않은 것도 숨기지 않고 함께 둔다.</p>
    <div class="stats">
      <div class="stat"><b>{n_base}</b><span>제출표 근거</span></div>
      <div class="stat"><b>{n_cited}</b><span>본문에서 인용</span></div>
      <div class="stat stat--gap"><b>{n_gap}</b><span>미인용 · 보강 후보</span></div>
      <div class="stat stat--new"><b>+{n_new}</b><span>세그먼트 검증 보강</span></div>
    </div>
    <div class="bar">{seg("g1",grades["g1"])}{seg("g2",grades["g2"])}{seg("gx",grades["gx"])}{seg("gn",grades["gn"])}</div>
    <ul class="legend">
      <li><span class="dot dot--g1"></span>1차 · 원 발행처 {grades["g1"]}건</li>
      <li><span class="dot dot--g2"></span>2차 · 재인용 {grades["g2"]}건</li>
      <li><span class="dot dot--gx"></span>원출처 미확인 {grades["gx"]}건</li>
      <li><span class="dot dot--gn"></span>등급 미기재 {grades["gn"]}건</li>
    </ul>
    <p class="note"><strong>등급을 밝히는 이유는 2차 인용을 1차 근거처럼 쓰지 않기 위해서다.</strong>
      국내 AICC 시장 수치(C3)는 원출처를 확인하지 못했고, 에이전트 도입 실패율 847건 조사(J6)는
      표본 선정 기준이 공개돼 있지 않다. 둘 다 핵심 근거로 쓰지 않는다. 경쟁 제품 항목(G군)은
      공개 자료 기준이라 “기능이 없다”가 아니라 “공개 자료로는 확인되지 않는다”로 읽어야 한다.</p>
  </header>

  <section class="qsec">
    <h2>세그먼트 검증 12문</h2>
    <p>제출표 41건은 “시장이 크다”와 “격차가 있다”까지만 받친다. 누구에게 무엇을 어떻게 파는가는
      받치지 못했다. 아래 12개가 그 빈자리이고, 각 답 밑의 근거번호를 누르면 원문으로 간다.</p>
    <div class="qgrid">
{chr(10).join(q_rows)}
    </div>
  </section>

{chr(10).join(sections)}

  <footer>
    근거번호와 기관 링크를 누르면 원문이 열린다. 제출표 41건은
    <code>team_branch/output/A-COPilot_제출표.xlsx</code>, 본문 인용 위치는
    <code>program/산출물양식/[기획] 프로젝트 기획서_A-COPilot.docx</code>,
    보강 {n_new}건은 <code>program/briefing/_근거지도_보강.json</code>에서 읽었다.
    손으로 옮기지 않고 세 파일에서 직접 읽어 만든다 —
    <code>python program/scripts/build_evidence_map.py</code>
  </footer>
</div>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"작성: {OUT.relative_to(ROOT)}  ({len(page):,} bytes)")
    print(f"  제출표 {n_base} (인용 {n_cited} · 미인용 {n_gap} · 방법론 {n_meta})")
    print(f"  보강 {n_new} · 질문 {len(extra['questions'])}개")
    print(f"  등급 {grades}")


if __name__ == "__main__":
    main()
