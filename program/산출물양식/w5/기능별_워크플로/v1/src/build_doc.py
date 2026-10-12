# -*- coding: utf-8 -*-
"""기능별 워크플로 문서 — ../spec/*.md 와 ../그림/*.svg 를 묶어 ../triPilot_기능별_워크플로_v1.{html,md,pdf} 를 만든다.

계획 확인(F02) · 일정 고치기(F09)는 새로 그리지 않고 「아키텍처 한눈에 v26」 그림 1 · 2 를 그대로 쓴다.
"""
import re
import shutil
from html import escape
from pathlib import Path

import markdown

from split_specs import flow_of

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC, FIG = ROOT / "spec", ROOT / "그림"
V26 = ROOT.parents[1] / "아키텍처_한눈에" / "v26"
VER = "v1"
TITLE = "triPilot 기능별 워크플로"
CODE_BASE = "final_project_cs 9e99c46c (2026-10-07)"

ORDER = ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10", "F11", "F12", "F13", "F14", "A01", "A02", "A03"]
REUSED = {
    "F02": dict(name="쓰던 계획으로 여행을 등록한다 (계획 확인)", uc="UC-02", png="그림1_계획확인_v26.png",
                start="고객이 글 · 사진 · 파일로 계획을 올리거나, 개인 AI 비서가 일정 JSON 을 제출한다",
                note="「아키텍처 한눈에 v26」 그림 1 을 그대로 실었다. 단계별 설명은 그 문서 1절에 있다."),
    "F09": dict(name="일정이 깨졌는지 검증하고 다시 맞춘다 (일정 고치기)", uc="UC-09 · UC-10 · UC-11", png="그림2_일정고치기_v26.png",
                start="3분마다 일정 위험 모니터링이 곧 시작할 일정을 외부 정보 6종으로 점검한다",
                note="「아키텍처 한눈에 v26」 그림 2 를 그대로 실었다. 에이전트 안쪽 단계는 이 문서의 A01 · A02 · A03 에 있다."),
}
WHO = {"에이전트": "에이전트", "언어 모델": "언어 모델 보조", "공용 도구": "공용 도구"}

CSS = """
body{margin:0;background:#fbfcfd;color:#161c28;font-family:'Noto Sans KR','Malgun Gothic',sans-serif;font-size:15px;line-height:1.7}
main{max-width:1180px;margin:0 auto;padding:48px 32px 96px}
h1{font-size:28px;margin:0 0 4px} .eyebrow{color:#6b7488;font-size:13px;letter-spacing:.08em;margin:0}
h2{font-size:21px;margin:56px 0 8px;padding-top:24px;border-top:1px solid #dbe0ea}
h3{font-size:16px;margin:24px 0 6px;color:#2a3242}
table{border-collapse:collapse;width:100%;margin:8px 0 16px;font-size:13.5px}
th,td{border:1px solid #dbe0ea;padding:6px 10px;vertical-align:top;text-align:left}
th{background:#f1f4f8} td:first-child{white-space:nowrap}
figure{margin:12px 0 8px;border:1px solid #dbe0ea;border-radius:8px;background:#fbfcfd;overflow-x:auto}
figure img,figure svg{display:block;width:100%;height:auto}
.lead{color:#3a4356} .muted{color:#6b7488;font-size:13px}
code{font-family:'Geist Mono',ui-monospace,monospace;font-size:12.5px;background:#f1f4f8;padding:1px 4px;border-radius:3px}
@media print{main{padding:0 8mm} h2{break-before:page;border-top:none} h2.nobreak{break-before:auto} figure{break-inside:avoid} tr{break-inside:avoid}}
"""


def section(md, title):
    m = re.search(rf"### {re.escape(title)}[^\n]*\n(.*?)(?=\n### |\Z)", md, re.S)
    return m.group(1).strip() if m else ""


def meta(md, key):
    m = re.search(rf"^- {key}: (.*)$", md, re.M)
    return m.group(1).strip() if m else ""


def inline(text):
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text).strip())


def who(fid, md):
    tags = {n.get("tag") for n in flow_of(md)["nodes"]}
    out = [v for k, v in WHO.items() if k in tags]
    return " · ".join(out) or "코드만"


def figure_stem(fid):
    hits = sorted(FIG.glob(f"{fid}_*_v1.svg"))
    return hits[0].stem if hits else None


def main():
    for fid, r in REUSED.items():
        shutil.copyfile(V26 / r["png"], FIG / f"{fid}_{r['png']}")
    rows, parts, md_out = [], [], []
    for fid in ORDER:
        if fid in REUSED:
            r = REUSED[fid]
            rows.append((fid, r["name"], r["uc"], "에이전트 · 언어 모델 보조" if fid == "F09" else "언어 모델 보조", "v26 그림"))
            img = f"그림/{fid}_{r['png']}"
            parts.append(f'<h2 id="{fid}">{fid} {escape(r["name"])}</h2><p class="lead">시작: {escape(r["start"])}</p>'
                         f'<figure><img src="{img}" alt="{escape(r["name"])}"></figure><p class="muted">{escape(r["note"])}</p>')
            md_out += [f"## {fid} {r['name']}", "", f"시작: {r['start']}", "", f"![{r['name']}]({img})", "", r["note"], ""]
            continue
        md = (SPEC / f"{fid}.md").read_text(encoding="utf-8")
        name = md.splitlines()[0][3:].split(" ", 1)[1].strip()
        uc = meta(md, "유스케이스") or "—"
        rows.append((fid, name, uc, who(fid, md), "새로 그림"))
        stem = figure_stem(fid)
        svg = (FIG / f"{stem}.svg").read_text(encoding="utf-8")
        table = section(md, "표")
        diff = section(md, "차이")
        unknown = section(md, "확인 못 한 것")
        body = (f'<h2 id="{fid}">{fid} {escape(name)}</h2>'
                f'<p class="lead"><b>시작</b> {inline(meta(md, "시작시키는 것"))}<br><b>관여자</b> {inline(meta(md, "관여자"))}</p>'
                f'<figure>{svg}</figure>'
                f'<h3>입력 · 출력 · 예외 · 상한 · 시험</h3>{markdown.markdown(table, extensions=["tables"])}'
                f'<h3>유스케이스 v7 과 다른 점 (지금 코드 기준)</h3>{markdown.markdown(diff)}'
                f'<h3>확인 못 한 것</h3>{markdown.markdown(unknown)}')
        parts.append(body)
        md_out += [f"## {fid} {name}", "", f"- 시작: {meta(md, '시작시키는 것')}", f"- 관여자: {meta(md, '관여자')}", "",
                   f"![{name}](그림/{stem}.png)", "", "### 입력 · 출력 · 예외 · 상한 · 시험", "", table, "",
                   "### 유스케이스 v7 과 다른 점 (지금 코드 기준)", "", diff, "", "### 확인 못 한 것", "", unknown, ""]

    intro_md = f"""멘토링(2026-10-03)에서 받은 숙제 「기능별 워크플로 다 작성해서 공유」 · 「각 에이전트에 대한 플로우」 · 「사람이 보고 따를 규정 문서로 각 플로우와 유스케이스 — 통합 및 정리」에 답하는 문서다.
유스케이스 v7(2026-10-03)의 기능마다 흐름 그림 한 장과, 입력 · 출력 · 예외 · 상한 · 시험을 적은 표를 둔다.

- 사실 기준: `{CODE_BASE}`. 흐름은 코드를 읽어 만들었고, 유스케이스 v7 과 달라진 곳은 기능마다 「다른 점」에 적었다.
- 그림은 사람이 1분 안에 따라 읽게 줄였다 — 위에서 아래로 큰 줄기 하나, 상자 11개 · 선 13개 이하. 줄인 것(접수 확인 안의 인증 · 중복 · 횟수 제한 등)은 표에 있다.
- 그림 읽는 법: 상자 테두리가 누가 판단하는지를 말한다 — 얇은 실선 [코드], 굵은 실선 [에이전트], 긴 점선 [공용 도구], 파란 점선 [언어 모델], 회색 [고객 · 개인 AI]. 마름모는 코드의 판단, 갈색 선은 반복.
- 이름: F 는 기능(Feature), A 는 에이전트 · 공용 도구 한 번의 실행 안쪽이다. 번호는 유스케이스 순서를 따른다(F02 · F09 는 「아키텍처 한눈에 v26」 그림을 다시 실었다)."""
    table_rows = "".join(f'<tr><td><a href="#{a}">{a}</a></td><td>{escape(b)}</td><td>{escape(c)}</td><td>{escape(d)}</td><td>{e}</td></tr>'
                         for a, b, c, d, e in rows)
    html = (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>{TITLE} {VER}</title><link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Noto+Sans+KR:wght@400;500;600&display=swap" rel="stylesheet">'
            f'<style>{CSS}</style></head><body><main><p class="eyebrow">triPilot · 6팀 A-COPilot · {VER} · 2026-10-07</p><h1>{TITLE}</h1>'
            f'{markdown.markdown(intro_md)}<h2 id="list" class="nobreak">기능 목록</h2><table><tr><th>ID</th><th>기능</th><th>유스케이스</th><th>판단에 쓰는 것</th><th>그림</th></tr>{table_rows}</table>'
            + "".join(parts) + "</main></body></html>")
    out = ROOT / f"triPilot_기능별_워크플로_{VER}.html"
    out.write_text(html, encoding="utf-8")
    md_doc = [f"# {TITLE} {VER}", "", intro_md, "", "## 기능 목록", "", "| ID | 기능 | 유스케이스 | 판단에 쓰는 것 | 그림 |", "|---|---|---|---|---|"]
    md_doc += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows] + [""] + md_out
    out.with_suffix(".md").write_text("\n".join(md_doc), encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        page = br.new_page()
        page.goto(out.as_uri(), wait_until="load", timeout=60000)
        page.wait_for_timeout(2500)
        page.pdf(path=str(out.with_suffix(".pdf")), format="A4", print_background=True,
                 margin=dict(top="12mm", bottom="12mm", left="10mm", right="10mm"))
        br.close()
    print("saved", out.name, len(rows), "기능")


if __name__ == "__main__":
    main()
