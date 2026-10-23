# -*- coding: utf-8 -*-
"""v14 — 처음 보는 사람용 에이전트 흐름 문서 (2026-10-03)

    python build_v14.py [--no-png]

순서(코덱스 읽기 검토 B 제안 + 전역 설명 규칙): 위층 5줄 → 그림 읽는 법 → 1. 계획 확인 → 2. 일정 고치기 → 역할 요약 카드 → 현재 한계
→ 부록 A 상세 명세 카드 · B 멘토링 규칙 대응표 · C 결함 상세 · D 랭그래프 확인.
"""
import re
import sys
from html import escape
from pathlib import Path

import build as base
import doc14 as T
from doc_data import CARD_FIELDS, CARDS, DEFECTS, LANGGRAPH, RULES
from fig_uc import fig_uc1, fig_uc2

OUT = Path(__file__).resolve().parent.parent
base.OUT = OUT
base.VER = VER = "v20"
ALL = [("UC1_계획확인_v20fig", fig_uc1), ("UC2_일정고치기_v20fig", fig_uc2)]
NAMES = {"UC1_계획확인_v20fig": "그림1_계획확인", "UC2_일정고치기_v20fig": "그림2_일정고치기"}

CSS_EXTRA = (" .top li{margin:.15rem 0} .guide td:first-child{white-space:nowrap;font-weight:600}"
             " .ends{font-size:14px;color:var(--muted)} .appendix{margin-top:3rem;border-top:3px solid var(--rule);padding-top:1rem}"
             " .card-table td:first-child{width:170px;white-space:nowrap} h3{margin:1.4rem 0 .4rem;font-size:16px}"
             " .note{font-size:13px;color:var(--muted)}")


def ul(items, cls=""):
    return f'<ul class="{cls}">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def table(head, rows, cls=""):
    return (f'<table class="{cls}"><thead><tr>' + "".join(f"<th>{escape(h)}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>")


def flow_section(uc, f):
    return (f"<h2>{escape(uc['title'])}</h2>" + "".join(f"<p>{s}</p>" for s in uc["lead"])
            + f"<p><strong>{escape(uc['example'])}</strong></p>"
            + f'<figure class="fig-wide">{f.svg()}</figure>'
            + "<p><strong>끝나는 길 · 예외</strong></p>" + ul([escape(e) for e in uc["ends"]], "ends"))


def doc_html(figs):
    f1, f2 = figs[0][1], figs[1][1]
    p = [f'<p class="eyebrow">guguroute · 에이전트 흐름 · {VER} · 2026-10-03</p>', f"<h1>{escape(T.TITLE)}</h1>",
         ul(T.TOP, "top lead"),
         "<h2>그림 읽는 법</h2>", table(["모양", "뜻"], T.READ_GUIDE, "guide"),
         flow_section(T.UC1, f1), flow_section(T.UC2, f2),
         "<h2>3. 역할 요약 — 누가 무엇을 맡나</h2>", "<p>아래는 두 그림에 나오는 다섯 역할입니다(에이전트 둘 · 공용 도구 하나 · 언어 모델 도우미 둘). 고객 채팅을 처리하는 흐름은 이 문서 범위 밖입니다. 숙박 · 항공 · 예약 인계 담당도 등록돼 있지만 이 두 그림에서는 일하지 않습니다(다음 단계 — 그대로 두기로 함).</p>",
         table(["역할"] + T.ROLE_FIELDS, [[k] + v for k, v in T.ROLES.items()]),
         '<p class="note">이동은 에이전트가 아니라 공용 도구로 정했습니다(2026-10-02 팀 결정). 코드에는 아직 이동이 담당 팀으로도 등록돼 있습니다 — 설계와 코드가 다른 곳입니다. 각 에이전트 · 도우미의 15항목 명세(입력 · 출력 형식 · 도구 · 실패 처리 · 코드 위치)는 부록 A.</p>',
         "<h2>4. 고객에게 미치는 현재 한계</h2>", ul([escape(x) for x in T.LIMITS]), f'<p class="note">{escape(T.LIMITS_NOTE)}</p>',
         '<div class="appendix"><h2>부록 A. 상세 명세 카드 (멘토링 문서 10쪽 14항목 + 코드 위치)</h2>']
    for name, vals in CARDS.items():
        rows = "".join(f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in zip(CARD_FIELDS, vals))
        p.append(f'<h3>{escape(name)}</h3><table class="card-table"><tbody>{rows}</tbody></table>')
    p += ["<h2>부록 B. 멘토링 문서 규칙 → 이 그림에서</h2>", table(["규칙(문서 7~14쪽)", "이 그림에서"], RULES),
          "<h2>부록 C. 결함 — 고친 것 · 남은 것 · 정할 것</h2>", ul([escape(d) for d in DEFECTS]),
          "<h2>부록 D. 랭그래프 확인</h2>", table(["질문", "답"], LANGGRAPH), "</div>",
          f"<footer>guguroute · A-COPilot · 그림: diagram-design 스킬(acop 스킨) · 글: 전역 설명 규칙 + technical-writing 검토 기준 · "
          f"사실: v13(코덱스 적대 검토 3회) · 읽기: 코덱스 읽기 검토 2회 · {VER}</footer>"]
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f"<title>guguroute 에이전트 흐름 {VER}</title>{base.FONT_LINK}<style>{base.CSS}{CSS_EXTRA}</style></head><body><div class=\"frame\">"
            + "\n".join(p) + "</div></body></html>")


def strip(s):
    return re.sub(r"<[^>]+>", "", s)


def md_text(figs):
    md = [f"# {T.TITLE}", ""] + [f"- {strip(s)}" for s in T.TOP] + ["", "## 그림 읽는 법", "", "| 모양 | 뜻 |", "|---|---|"]
    md += [f"| {a} | {b} |" for a, b in T.READ_GUIDE]
    for uc, (name, f) in ((T.UC1, figs[0]), (T.UC2, figs[1])):
        md += ["", f"## {uc['title']}", ""] + uc["lead"] + ["", f"**{uc['example']}**", "", f"![{f.title}]({NAMES[name]}_{VER}.png)", "",
                                                          "**끝나는 길 · 예외**", ""] + [f"- {e}" for e in uc["ends"]]
    md += ["", "## 3. 역할 요약 — 누가 무엇을 맡나", "", "| 역할 | " + " | ".join(T.ROLE_FIELDS) + " |", "|---" * (len(T.ROLE_FIELDS) + 1) + "|"]
    md += [f"| {k} | " + " | ".join(v) + " |" for k, v in T.ROLES.items()]
    md += ["", "## 4. 고객에게 미치는 현재 한계", ""] + [f"- {x}" for x in T.LIMITS] + ["", T.LIMITS_NOTE, "", "---", "", "## 부록 A. 상세 명세 카드"]
    for name, vals in CARDS.items():
        md += ["", f"### {name}", "", "| 항목 | 내용 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in zip(CARD_FIELDS, vals)]
    md += ["", "## 부록 B. 멘토링 문서 규칙 → 이 그림에서", "", "| 규칙 | 이 그림에서 |", "|---|---|"] + [f"| {a} | {b} |" for a, b in RULES]
    md += ["", "## 부록 C. 결함 — 고친 것 · 남은 것 · 정할 것", ""] + [f"- {d}" for d in DEFECTS]
    md += ["", "## 부록 D. 랭그래프 확인", "", "| 질문 | 답 |", "|---|---|"] + [f"| {a} | {b} |" for a, b in LANGGRAPH] + [""]
    return "\n".join(md)


def main():
    figs = [(n, fn()) for n, fn in ALL]
    for n, f in figs:
        e = f.check()
        if e:
            sys.exit(f"{n} 규칙 검사 실패: {e}")
    for n, f in figs:
        (OUT / f"{NAMES[n]}_{VER}.html").write_text(base.fig_html(n, f), encoding="utf-8")
        (OUT / f"{NAMES[n]}_{VER}.svg").write_text(base.svg_file(f), encoding="utf-8")
    doc = OUT / f"triPilot_에이전트흐름_{VER}.html"
    doc.write_text(doc_html(figs), encoding="utf-8")
    (OUT / f"triPilot_에이전트흐름_{VER}.md").write_text(md_text(figs), encoding="utf-8")
    if "--no-png" not in sys.argv:
        base.export([(NAMES[n], f) for n, f in figs], doc)


if __name__ == "__main__":
    main()
