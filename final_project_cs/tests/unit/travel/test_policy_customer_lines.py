# -*- coding: utf-8 -*-
"""규정 문서의 **고객용 문장**(`customer_answers`) 규칙. `[2026-09-28 사용자 결정]`

★규정 문서 12개는 직원에게 쓴 글이라 조각 원문을 고객 답에 실으면 직원용 문장이 나간다(ui 세션 실서버 시험).
  그래서 절마다 고객에게 하는 말을 문서 머리에 따로 두고 답에는 그것만 싣는다(`itinerary_team.customer_lines`).
  이 시험은 그 문장이 **규정 본문에 없는 수치를 만들지 않고**, 내부 말을 쓰지 않고, 절 제목과 짝이 맞는지 본다."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from knowledge.ingest import load_corpus

MANIFEST = Path(__file__).resolve().parents[3] / "knowledge" / "travel" / "manifest.json"
DOCUMENTS = load_corpus(MANIFEST)
#: 고객 답에 나오면 안 되는 내부 말 — 직원 절차 · 사람 대기(사용자 결정: 사람 대기 답을 하지 않는다)
INTERNAL = ("판정", "갈래", "Case", "케이스", "소스", "가드레일", "코어", "원장", "에스컬레이션", "업무 규칙",
            "우리 몫", "담당자", "사람이 확인")


def _pairs():
    for document in DOCUMENTS:
        answers = document.frontmatter.get("customer_answers") or {}
        titles = {s.title: s for s in document.sections}
        for title, line in answers.items():
            yield document.frontmatter["document_id"], title, str(line), titles.get(title)


PAIRS = list(_pairs())


def test_every_document_has_customer_lines_and_most_sections_are_covered():
    covered = {doc for doc, *_ in PAIRS}
    assert covered == {d.frontmatter["document_id"] for d in DOCUMENTS}
    sections = sum(len(d.sections) for d in DOCUMENTS)
    assert len(PAIRS) >= sections // 2, (len(PAIRS), sections)


@pytest.mark.parametrize("document_id, title, line, section", PAIRS, ids=[f"{d}:{t}" for d, t, *_ in PAIRS])
def test_a_customer_line_matches_its_section_and_adds_no_numbers(document_id, title, line, section):
    assert section is not None, f"{document_id}: 「{title}」 절이 없다(제목이 바뀌었나)"
    assert 0 < len(line) <= 130
    assert not [word for word in INTERNAL if word in line], line
    for number in re.findall(r"\d[\d,]*(?:\.\d+)?", line):
        assert number in section.content, f"{document_id} 「{title}」 — 본문에 없는 수치 {number}"
