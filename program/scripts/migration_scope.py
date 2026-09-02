"""이관 범위 목록 생성.

governance/migration.md 가 요구하는 표를 만든다.

    원본 경로 | 추정 type | 목표 영역 | 판정 | 분할 신호 | 줄 수

★이 결과는 **초안이다.** 사람이 판정 열을 확정해야 한다.
  휴리스틱은 폴더·파일명·본문 신호로 추정할 뿐이고,
  5차 blind 검증에서 확인됐듯 애매한 것이 30% 가까이 나온다.

    python program/scripts/migration_scope.py            # 요약
    python program/scripts/migration_scope.py --full     # 전체 목록
    python program/scripts/migration_scope.py --tsv      # 작업용 TSV

결과: program/scripts/_migration_scope.tsv
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = "program/scripts/_migration_scope.tsv"

#: 아예 세지 않는다. 이관 후보가 아니다.
SKIP_DIRS = (
    "wiki/",                        # 우리가 만든 새 구조
    "_backup/", "archive/",
    "__pycache__", "node_modules", ".git", ".tmp",
    # ★9차. `_prompts/` 는 어디에 있든 작업 지시 티켓이다. 세 번 확인했다.
    #   handoff 114 · sample 99 · ui 11 · research 2 · datasets 1 = 227건.
    #   ★단 하나 예외가 있다 — `program/research/_prompts/문서병합_지침.md` 는
    #     루트 CLAUDE.md 21행이 경로로 직접 참조한다. 옮기면 링크가 깨진다.
    #     "이관 안 함"이라는 결론은 같으므로 여기서 함께 건너뛴다.
    #     근거: governance/type-verification/round-7.md
    "_prompts/",
    "final_project_cs/legacy/",     # 옛 sample 코드 사본 42건
    "final_project_cs/knowledge/",  # RAG 코퍼스 25건. 문서가 아니라 데이터
    "final_project_cs/prompts/",    # 프롬프트 파일
    "team_branch/",                 # 팀원 개인 폴더
    "final_project_ui/",            # 별도 프로그램
    # ★9차. CLAUDE.md — datasets 의 raw/ processed/ 는 본인 실제 구매 기록이라
    #   git 에 올리지 않는다. 버전관리 밖이므로 이관 대상이 아니다.
    #   (final_project_sample/ 도 gitignore 이지만 그건 자체 저장소라서다. 다르다)
    "datasets/commerce/coupang_order_history/raw/",
    "datasets/voc/nikl_ne_2022/processed/",
)

#: 이관하지 않는다. 이유와 함께 센다.
EXCLUDE = [
    ("docs/history/",        "제외", "git 으로 복원 가능. 결정만 추출"),
    ("docs/reports/",        "제외", "그 시점 기록. 결정·증거만 추출"),
    ("docs/TODO/",           "제외", "완료된 TODO"),
    ("docs/submission/",     "제외", "제출 산출물. 별도 관리"),
    ("final_project_sample/", "선별", "계약 선검증분만 승격"),
]

#: 폴더 → (type, 목표 영역)
BY_DIR = [
    ("docs/evidence/",  "evidence", "cs/quality"),
    ("docs/handoff/",   "contract", "cs/teams·external·data"),
    ("docs/vision/",    "decision",  "hub/decisions"),
    ("docs/manuals/",   "runbook",   "cs/operations"),
    ("docs/plans/",     "plan",      "hub/delivery 또는 cs/decisions"),
    ("program/plan/",   "?",         "hub/*"),
    # ★research 전건 판정(26건)에서 이 줄이 24건 틀렸다. 폴더는 주제가 아니라
    #   "여기서 조사 문서를 쓴다"는 작성 경로다. 실제로는 report 12·reference 5 였다.
    #   그래서 type 을 찍지 않고 사람에게 넘긴다.
    ("program/research/", "?", "hub/research — 전건 판정 완료. _verify_research.tsv"),
    ("datasets/",       "dataset",   "data/catalog"),
]

#: 파일명 신호
BY_NAME = [
    (r"_일일작업_|_주말작업_|_밤샘작업_|_주간작업_", "report", "제외 후보"),
    (r"_정합성점검|_잔여작업_점검|_현황정리",        "report", "hub/delivery"),
    (r"_원본_|_법령사실|WBS원본",                    "reference", "hub/research"),
    (r"_결정\.md$|_경계\.md$",                       "decision", "hub/decisions"),
    (r"_계획\.md$|_실행계획|_배분안|init_plan",      "plan",     "hub/delivery"),
    (r"^CLAUDE\.md$",                                "policy",   "루트 유지"),
    (r"^README\.md$",                                "guide",    "각 폴더 유지"),
    (r"REPORT\.md$",                                 "dataset",  "data/catalog"),
]

#: 본문에서 "여러 일을 한다"를 잡는 신호. 두 종류 이상이면 분할 대상.
#: 제목 어디에나 나오면 잡는다. 번호·기호가 섞여 있어 앞부분만 고정하지 않는다.
SPLIT_SIGNALS = {
    "decision": r"^#{2,4} .*(결론|결정|선택지|안 [ABC]|기각|왜 (안|하지)|하지 않는 이유|판정)",
    "plan":     r"^#{2,4} .*(순서|실행 계획|완료 기준|일정|배분|다음|남은|앞으로|착수|도입 트리거|해야)",
    "report":   r"^#{2,4} .*(실측|현황|결과|무엇을 했나|이날|완료된|받은 것|전처리|검증 상태|이력)",
    "research": r"^#{2,4} .*(조사|비교|외부|출처|근거 자료|선택 이유)",
    "concept":  r"^#{2,4} .*(구조|개념|용어|책임|무엇인가|어떻게 동작)",
    "policy":   r"^#{2,4} .*(규칙|원칙|기준|하면 안|금지|반드시)",
}

EVIDENCE_MARK = re.compile(r"^##+ *재현 명령|^##+ *재현$", re.M)

#: ★9차. datasets/ 의 REPORT 는 "데이터가 무엇인가"(안 변함)와
#: "지금 어디까지 됐나"(계속 변함)를 한 파일에 담는 일이 잦다.
#: → program/datasets/wiki/report-split.md
#:
#: 28건 전건 판정에 맞춰 조정했다. 줄수 하한 80 에서 놓침 0 · 오탐 3.
#: 하한을 100 으로 올리면 놓침이 3 생긴다. 놓치는 것보다 오탐이 낫다.
DS_DATE = re.compile(r"^#{1,4} .*20\d\d[-.]\d\d[-.]\d\d", re.M)
DS_STATUS = re.compile(
    r"^#{1,4} .*(지금 몇|현황|아직 안 한|전처리 결과|갱신|알려진 문제|결과 \d)", re.M)
H1_MARK = re.compile(r"^# ", re.M)

#: `docs/evidence/_raw/` 는 판정본이 "실측 원문"으로 인용하는 수집 원문이다.
#: 인용된 것을 끊으면 근거 사슬이 끊긴다. 인용되지 않은 것은 중간판이다.
#: ★8차 검증에서 확인. 24건 중 11건만 인용된다.
RAW_CITE = re.compile(r"_raw/([A-Za-z0-9_\-]+\.md)")


def cited_raw_files() -> set[str]:
    """판정본이 실제로 인용하는 _raw 파일명 집합."""
    out: set[str] = set()
    for f in glob.glob("**/evidence/*.md", recursive=True):
        try:
            out |= set(RAW_CITE.findall(open(f, encoding="utf-8", errors="replace").read()))
        except OSError:
            continue
    return out


def scan() -> list[dict]:
    rows: list[dict] = []
    cited = cited_raw_files()
    for f in sorted(glob.glob("**/*.md", recursive=True)):
        n = f.replace("\\", "/")
        if any(s.strip("/\\") in n for s in SKIP_DIRS):
            continue
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        lines = text.count("\n") + 1
        base = os.path.basename(n)

        verdict, why = "유지", ""
        for pat, v, reason in EXCLUDE:
            if pat in n:
                verdict, why = v, reason
                break

        # type 추정 — 파일명이 폴더보다 우선
        t, area = "?", "?"
        for pat, tt, aa in BY_NAME:
            if re.search(pat, base):
                t, area = tt, aa
                break
        if t == "?":
            for pat, tt, aa in BY_DIR:
                if pat in n:
                    t, area = tt, aa
                    break
        if EVIDENCE_MARK.search(text):
            t = "evidence"

        # 분할 신호
        #   ★ 자동으로 "분할"이라고 단정하지 않는다.
        #     blind 검증에서 사람 둘도 갈렸다. 정규식이 더 잘할 수 없다.
        #     신호가 여럿이고 문서가 크면 "판정필요"로 사람에게 넘긴다.
        hits = [k for k, pat in SPLIT_SIGNALS.items()
                if re.search(pat, text, re.M)]
        if verdict == "유지" and len(hits) >= 3 and lines >= 100:
            verdict, why = "판정필요", f"신호 {len(hits)}종·{lines}줄"

        if lines < 10:
            verdict, why = "제외", "내용 없음"
        elif verdict == "유지" and lines < 40:
            # ★6차 검증에서 드러났다. 짧은 문서는 작업 로그·폐기 기록일 때가 많고
            #   휴리스틱이 폴더만 보고 dataset·guide 로 잘못 찍는다.
            verdict, why = "판정필요", f"{lines}줄 — 작업 로그·폐기 기록 후보"

        if "datasets/" in n and verdict == "유지":
            # H1 이 둘 이상이면 규칙 이전의 문제다 — 한 파일에 두 문서가 있다.
            if len(H1_MARK.findall(text)) >= 2:
                verdict, why = "판정필요", "★H1 이 2개 이상 — 한 파일에 두 문서"
            elif lines >= 80 and (DS_DATE.search(text) or DS_STATUS.search(text)):
                verdict, why = "판정필요", "REPORT 분할 신호 (report-split.md)"

        # ★맨 마지막에 온다. 인용 여부는 줄 수보다 강한 신호다.
        #   실측 원문은 원래 짧다 — 명령과 출력만 담기 때문이다.
        #   길이 하한이 이 판정을 덮으면 근거 사슬이 "판정필요"로 묻힌다.
        if "/evidence/_raw/" in n:
            if base in cited:
                verdict, why = "유지", "판정본이 인용하는 실측 원문. 끊으면 근거 사슬이 끊긴다"
            else:
                verdict, why = "제외", "인용되지 않은 중간판"

        rows.append({
            "path": n, "type": t, "area": area,
            "verdict": verdict, "why": why,
            "split": "+".join(hits) if len(hits) >= 2 else "",
            "lines": lines,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--tsv", action="store_true")
    args = ap.parse_args()

    rows = scan()
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("원본경로\t추정type\t목표영역\t판정\t분할신호\t줄수\t비고\n")
        for r in rows:
            fh.write(f"{r['path']}\t{r['type']}\t{r['area']}\t{r['verdict']}\t"
                     f"{r['split']}\t{r['lines']}\t{r['why']}\n")

    vc = Counter(r["verdict"] for r in rows)
    print(f"전체 {len(rows)}건")
    print()
    for v in ("유지", "판정필요", "선별", "제외"):
        print(f"  {v:5} {vc.get(v,0):5}건")
    keep = vc.get("유지", 0) + vc.get("판정필요", 0)
    print(f"\n이관 대상 (유지+판정필요)  {keep}건")
    if keep:
        print(f"그중 사람 판정 필요       {vc.get('판정필요',0)}건 "
              f"({vc.get('판정필요',0)/keep*100:.0f}%)")

    print("\ntype 분포 (이관 대상):")
    tc = Counter(r["type"] for r in rows if r["verdict"] in ("유지", "판정필요"))
    for k, v in tc.most_common():
        print(f"  {k:12} {v:4}")

    print("\n분할 신호 조합:")
    sc = Counter(r["split"] for r in rows if r["split"])
    for k, v in sc.most_common(10):
        print(f"  {k:28} {v:4}")

    if args.full or args.tsv:
        print(f"\n{'경로':70} {'type':10} {'판정':5} {'줄':>5}")
        print("-" * 95)
        for r in rows:
            if r["verdict"] in ("유지", "판정필요"):
                print(f"{r['path'][:70]:70} {r['type']:10} {r['verdict']:5} {r['lines']:5}")

    print(f"\n→ {OUT}")
    print("★ 판정 열은 초안이다. 사람이 확정해야 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
