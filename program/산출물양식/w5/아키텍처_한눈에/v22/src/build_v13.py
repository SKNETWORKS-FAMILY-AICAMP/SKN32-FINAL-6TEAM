# -*- coding: utf-8 -*-
"""v13 — 멘토링 문서 규칙대로 만든 에이전트 흐름 (UC-1 · UC-2) + 에이전트 명세 카드 + 랭그래프 확인 (2026-10-03)

    python build_v13.py [--no-png]
"""
import re
import sys
from html import escape
from pathlib import Path

import build as base
from fig_uc import fig_uc1, fig_uc2

OUT = Path(__file__).resolve().parent.parent
base.OUT = OUT
base.VER = VER = "v13"
ALL = [("UC2_에이전트흐름_일정지키기", fig_uc2), ("UC1_에이전트흐름_계획확인", fig_uc1)]

TITLE = "triPilot 에이전트 흐름 — 누가 다음 단계를 정하나"

from doc_data import CARD_FIELDS, CARD_INTRO, CARDS, DEFECTS, HONEST, LANGGRAPH, RULES, SECTIONS


def card_table(name, vals):
    rows = "".join(f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in zip(CARD_FIELDS, vals))
    return f'<h3>{escape(name)}</h3><table class="card-table"><tbody>{rows}</tbody></table>'


def doc_html(figs):
    p = [f'<p class="eyebrow">triPilot · Agent Flow · {VER} · 2026-10-03 · 멘토링 문서 「유스케이스 &amp; 멀티 에이전트 다이어그램」 규칙 반영</p>',
         f"<h1>{escape(TITLE)}</h1>", f'<p class="lead">{HONEST}</p>',
         "<h2>멘토링 문서 규칙 → 이 그림에서</h2>",
         "<table><thead><tr><th>규칙(문서 7~14쪽)</th><th>이 그림에서</th></tr></thead><tbody>"
         + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in RULES) + "</tbody></table>"]
    for name, f in figs:
        h, body, cap = SECTIONS[name]
        p.append(f'<h2>{escape(h)}</h2><p>{body}</p><figure class="fig-wide">{f.svg()}<figcaption>{cap}</figcaption></figure>')
    p.append(f"<h2>에이전트 명세 카드 — 그림이 못 담는 것</h2><p>{escape(CARD_INTRO)}</p>")
    for name, vals in CARDS.items():
        p.append(card_table(name, vals))
    p.append("<h2>랭그래프 확인 — 원래 계획에 있었나, 왜 지금 없나</h2>")
    p.append("<table><thead><tr><th>질문</th><th>답</th></tr></thead><tbody>"
             + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in LANGGRAPH) + "</tbody></table>")
    p.append("<h2>이번 검토로 드러난 제품 결함 — 그림에 그대로 적었다</h2>")
    p.append('<div class="status"><ul>' + "".join(f"<li>{escape(d)}</li>" for d in DEFECTS) + "</ul></div>")
    p.append(f"<footer>triPilot · A-COPilot · 그림: diagram-design 스킬(acop 스킨) · 사실: v12 합의본 + 코드 · {VER}</footer>")
    css = base.CSS + " .card-table td:first-child{width:180px;white-space:nowrap} h3{margin:1.5rem 0 .4rem;font-size:16px}"
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f"<title>triPilot 에이전트 흐름 {VER}</title>{base.FONT_LINK}<style>{css}</style></head><body><div class=\"frame\">"
            + "\n".join(p) + "</div></body></html>")


def strip(s):
    return re.sub(r"<[^>]+>", "", s)


def md_text(figs):
    md = [f"# {TITLE}", "", strip(HONEST), "", "## 멘토링 문서 규칙 → 이 그림에서", "", "| 규칙 | 이 그림에서 |", "|---|---|"]
    md += [f"| {a} | {b} |" for a, b in RULES]
    for name, f in figs:
        h, body, cap = SECTIONS[name]
        md += ["", f"## {h}", "", strip(body), "", f"![{f.title}]({name}_{VER}.png)", "", f"> {strip(cap)}"]
    md += ["", "## 에이전트 명세 카드", "", CARD_INTRO]
    for name, vals in CARDS.items():
        md += ["", f"### {name}", "", "| 항목 | 내용 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in zip(CARD_FIELDS, vals)]
    md += ["", "## 랭그래프 확인", "", "| 질문 | 답 |", "|---|---|"] + [f"| {a} | {b} |" for a, b in LANGGRAPH]
    md += ["", "## 이번 검토로 드러난 제품 결함", ""] + [f"- {d}" for d in DEFECTS] + [""]
    return "\n".join(md)


def main():
    figs = [(n, fn()) for n, fn in ALL]
    bad = False
    for n, f in figs:
        e = f.check()
        if e:
            bad = True
            print(n, *e, sep="\n  - ")
    if bad:
        sys.exit("규칙 검사 실패 — 내보내지 않음")
    for n, f in figs:
        (OUT / f"{n}_{VER}.html").write_text(base.fig_html(n, f), encoding="utf-8")
        (OUT / f"{n}_{VER}.svg").write_text(base.svg_file(f), encoding="utf-8")
    doc = OUT / f"triPilot_에이전트흐름_{VER}.html"
    doc.write_text(doc_html(figs), encoding="utf-8")
    (OUT / f"triPilot_에이전트흐름_{VER}.md").write_text(md_text(figs), encoding="utf-8")
    if "--no-png" not in sys.argv:
        base.export(figs, doc)


if __name__ == "__main__":
    main()
