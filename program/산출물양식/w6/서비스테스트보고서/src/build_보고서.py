"""[모델배포] 서비스 테스트 계획 및 결과 보고서(6주차) 빌더 (2026-10-06).

재료: ../_재료/본문_초안.md (RAG 세션이 평가 리포트 표를 양식 칸에 맞춰 쓴 마크다운 초안)
겉틀: program/산출물양식/[모델배포] 서비스 테스트 계획 및  결과 보고서_양식.docx (표지 · 정보 표 · 절 제목 띠는 그대로 두고 띠 사이 본문만 채움)
공용 빌더: w5/_공용/w5_docx.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FORMS = ROOT.parents[1]
sys.path.insert(0, str(FORMS / "w5" / "_공용"))
import w5_docx as W  # noqa: E402
import term_pass as TP  # noqa: E402

TEMPLATE = FORMS / "[모델배포] 서비스 테스트 계획 및  결과 보고서_양식.docx"
DRAFT = ROOT / "_재료" / "본문_초안.md"
OUT = ROOT / "[모델배포] 서비스 테스트 계획 및 결과 보고서_6팀.docx"

INTRO = [
    ["note", "이 보고서의 질문 · 시험 자료는 모두 모델이 쓴 합성(Codex · Claude)이다. 표의 값은 합성 시험 기준 점수이며 실서비스 점수가 아니다. 사람 평가는 평가자 1명이 35행을 매긴 첫 결과뿐이다(4.9절). "
             "수치의 출처 · 조건 · 한계는 final_project_cs/wiki/records/reports/2026-10-06_서비스_평가_베이스라인과_개선_전후.md 와 2026-10-06_RAG_평가지표_리포트.md 에 있다."],
]
FIX = [
    ("유료 Jev API", "Jev API(유료)"),
    ("연결 시험 서버:", "GPU 서버 C(연결 시험):"),
    ("학습 서버:", "GPU 서버 B(학습):"),
]


def clean(t: str) -> str:
    t = t.replace("★", "").replace("**", "").replace("`", "")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    for a, b in FIX:
        t = t.replace(a, b)
    t = t.replace("— (기준 없음, 기록)", "기록(기준 없음)").replace("목표 미정 — 기록", "목표 미정, 기록")
    t = t.strip()
    if t == "—":
        return "없음"
    t = re.sub(r"\s*—\s*", ", ", t)
    t = t.replace("–", "~").replace("…", "")
    return t


def parse(md: str):
    secs, cur, rows, head = [], None, None, None

    def flush_table():
        nonlocal rows, head
        if head is not None:
            n = len(head)
            body = [r + [""] * (n - len(r)) for r in rows]
            ratio = []
            for j in range(n):
                lens = [len(head[j])] + [len(r[j]) for r in body]
                # 짧은 칸(예: 「답할지 거절할지」 · 「에이전트 일관성」)이 낱말 중간에서 끊기지 않게, 가장 긴 칸 길이(9자까지)를 바닥으로 둔다
                ratio.append(round(max(max(4.0, sum(lens) / len(lens)) ** 0.7, min(max(lens), 9) * 0.78), 2))
            cur.append(["t", head, body, ratio])
        rows, head = None, None

    for line in md.splitlines():
        s = line.rstrip()
        if s.startswith("## "):
            if cur is not None:
                flush_table()
            cur = []
            secs.append(cur)
            continue
        if cur is None:
            continue
        if s.startswith("|"):
            cells = [clean(c) for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in s.strip("|").split("|")):
                continue
            if head is None:
                head, rows = cells, []
            else:
                rows.append(cells)
            continue
        flush_table()
        if not s.strip():
            continue
        mi = re.match(r"!\[(.+?)\]\((.+?)\)\s*$", s.strip())
        if mi:  # 그림 줄(RAG 세션이 넣은 6주차 그림): 경로는 초안(_재료/) 기준
            img = (DRAFT.parent / mi.group(2)).resolve()
            if not img.exists():
                raise FileNotFoundError(img)
            cur.append(["img", str(img), clean(mi.group(1)), 11.0])
            continue
        if s.startswith("### "):
            cur.append(["h", clean(s[4:])])
        elif s.startswith("- "):
            body = s[2:]
            m = re.match(r"\*\*(.+?)\*\*\s*:\s*(.*)", body)
            if m:
                cur.append(["b", clean(m.group(1)) + ":", clean(m.group(2)), 0])
            else:
                cur.append(["b", "", clean(body), 0])
        elif s.startswith("※"):
            cur.append(["note", clean(s.lstrip("※ "))])
        elif s.startswith(">"):
            continue
        else:
            cur.append(["p", clean(s)])
    if cur is not None:
        flush_table()
    return secs


def main():
    # 용어 정비(2026-10-06 사용자 지적 「독립실험 A 가 뭔지 어떻게 알아」): 초안 문장을 실무 용어로 다시 쓰고(코덱스 점검 → Claude 검토),
    # 공통 용어를 바꾼 뒤 1절 맨 앞에 「용어 정의」 표를 둔다. 초안 파일은 RAG 세션 것이라 고치지 않고 빌드할 때만 바꾼다.
    md = TP.apply_raw(DRAFT.read_text(encoding="utf-8"), "w6")
    secs = parse(md)
    if len(secs) != 5:
        raise ValueError(f"절 {len(secs)}개")
    secs[0] = INTRO + secs[0]
    secs, _ = TP.run_blocks(secs, "w6", rewrites=False)
    out = W.build(TEMPLATE, OUT, stage="모델 배포", sections=secs)
    print("saved", out)


if __name__ == "__main__":
    main()
