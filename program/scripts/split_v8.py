"""v8 계획서를 wiki 구조로 쪼갠다.

★원본(`program/plan/A-COP_구현계획서_v8.md`)은 **읽기만 한다.**
  결과는 `program/wiki/_migration/v8/` 에만 쓴다.

    python program/scripts/split_v8.py            # 매핑 확인
    python program/scripts/split_v8.py --write    # 실제로 쓴다
"""
from __future__ import annotations

import argparse
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = "program/plan/A-COP_구현계획서_v8.md"
DST = "program/wiki/_migration/v8"

#: 절 번호 → (목표 파일, type, 제목, 한 줄 설명)
#:   "—" 는 옮기지 않는다. 이유를 SKIP 에 적는다.
MAP: dict[str, tuple[str, str, str, str]] = {
    "1":    ("product/positioning.md",        "concept",  "포지셔닝", "무엇을 팔고 무엇을 팔지 않는가"),
    "2":    ("product/problem.md",            "concept",  "문제 정의", "단계별 LLM 호출로는 표현할 수 없는 것"),
    "3":    ("product/goals.md",              "concept",  "프로젝트 목표", "여섯 가지 목표와 부트캠프 요구사항 대응"),
    "3-A":  ("product/goals.md",              "concept",  "", ""),
    "4":    ("product/positioning.md",        "concept",  "", ""),
    "5":    ("product/scope.md",              "concept",  "범위", "In/Out of Scope"),
    "6":    ("product/scope.md",              "concept",  "", ""),
    "10":   ("product/scenarios.md",          "concept",  "핵심 사용자 시나리오", "대표 시나리오와 착수 목록에서 뺀 것"),

    "7":    ("architecture/team-principles.md", "concept", "Team 구성 원칙", "Team 을 언제 만드는가"),
    "7-A":  ("architecture/team-principles.md", "concept", "", ""),
    "7-B":  ("architecture/system-context.md",  "concept", "", ""),
    "8":    ("architecture/core-design.md",     "concept", "Core 설계", "Basement 8개 구성요소"),
    "8-A":  ("architecture/core-design.md",     "concept", "", ""),
    "8-B":  ("architecture/pack-model.md",      "concept", "", ""),
    "8-C":  ("architecture/concurrency.md",     "concept", "경합과 동시성 책임", "Agent·Team 경합을 누가 처리하는가"),
    "9":    ("architecture/external-ai.md",     "concept", "외부 소비자 AI 연동", "Personal AI 와 기업 Agent 경로"),
    "9-C":  ("architecture/external-ai.md",     "concept", "", ""),
    "11":   ("architecture/data-model.md",      "concept", "데이터 구조", "핵심 관계와 단일 원천"),
    "22":   ("architecture/data-model.md",      "concept", "", ""),
    "12":   ("architecture/tech-stack.md",      "reference","기술 스택", "쓰는 것과 안 쓰는 것"),
    "13":   ("architecture/repository-map.md",  "concept", "", ""),

    "9-D":  ("research/graphrag.md",          "research", "", ""),
    "9-E":  ("decisions/D-005-evidence-gate.md", "decision", "쓰기 권한의 전제 조건", "근거 대조가 통과해야 쓰기를 연다"),

    "14":   ("delivery/timeline.md",          "plan",     "", ""),
    "25":   ("delivery/timeline.md",          "plan",     "", ""),
    "16":   ("delivery/roles.md",             "plan",     "", ""),
    "27":   ("delivery/dod.md",               "plan",     "", ""),
    "18":   ("delivery/risks.md",             "plan",     "예상 리스크", "범위 과대와 결정사항의 주의점"),
    "18-A": ("delivery/risks.md",             "plan",     "", ""),

    "15":   ("evaluation/protocol.md",        "concept",  "", ""),

    "19":   ("cs/runtime/case-lifecycle.md",  "contract", "", ""),
    "20":   ("cs/runtime/conflict-retry.md",  "contract", "", ""),
    "21":   ("cs/teams/team-contract/index.md",     "contract", "", ""),
    "23":   ("cs/context/context-budget.md",  "contract", "", ""),
    "24":   ("cs/external/auth-boundary.md",  "contract", "", ""),

    "26":   ("delivery/review-qa.md",         "guide",    "심사 대응 질문", "예상 질문과 답변"),
    "부록 A": ("decisions/contract-changes.md", "decision", "v5 대비 계약 변경점", "무엇이 바뀌었고 코드에 어떤 영향이 있나"),
}

#: 옮기지 않는 절과 이유
SKIP = {
    "0":   "문서 상태·변경 이력. wiki 는 log.md 가 대신한다",
    "0-1": "한 줄 요약. quickstart.md 가 대신한다",
    "0-2": "절 색인. index.md 가 대신한다",
    "17":  "개인 어필 문장. 문서 표준 범위 밖",
    "28":  "엑셀 입력용 요약. 제출 양식이라 별도 관리",
    "참고 출처": "각 문서의 sources 로 분산",
}

HEAD = re.compile(r"^## ([\w\-. ]+?)\. ")


def sections() -> list[tuple[str, str, list[str]]]:
    """(번호, 제목, 본문줄) 목록."""
    lines = open(SRC, encoding="utf-8").read().splitlines()
    marks = [(i, l) for i, l in enumerate(lines) if l.startswith("## ")]
    out = []
    for k, (i, title) in enumerate(marks):
        j = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        m = HEAD.match(title)
        num = m.group(1) if m else title[3:].split(".")[0].strip()
        out.append((num, title[3:].strip(), lines[i:j]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    secs = sections()
    groups: dict[str, list] = {}
    unmapped = []

    for num, title, body in secs:
        if num in SKIP:
            continue
        hit = MAP.get(num)
        if not hit:
            unmapped.append((num, title, len(body)))
            continue
        groups.setdefault(hit[0], []).append((num, title, body, hit))

    print(f"절 {len(secs)}개 → 파일 {len(groups)}개")
    print(f"  옮김 {sum(len(v) for v in groups.values())}절 · "
          f"건너뜀 {len(SKIP)}절 · 매핑없음 {len(unmapped)}절\n")

    for path in sorted(groups):
        nums = ", ".join(f"§{n}" for n, _, _, _ in groups[path])
        ln = sum(len(b) for _, _, b, _ in groups[path])
        print(f"  {path:42} {ln:5}줄  {nums}")

    if unmapped:
        print("\n★ 매핑 없음:")
        for n, t, ln in unmapped:
            print(f"  §{n} {t[:50]} ({ln}줄)")

    if not args.write:
        print(f"\n(--write 를 주면 {DST}/ 에 쓴다)")
        return 0

    for path, items in groups.items():
        full = os.path.join(DST, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        _, typ, title, desc = items[0][3]
        title = title or os.path.basename(path)[:-3]
        desc = desc or f"v8 에서 이관: {', '.join('§'+n for n,_,_,_ in items)}"
        with open(full, "w", encoding="utf-8") as fh:
            fh.write("---\n")
            fh.write(f"type: {typ}\ntitle: {title}\ndescription: {desc}\n")
            fh.write("status: draft\n")
            fh.write("owners: [human:미배정]\n---\n\n")
            fh.write(f"# {title}\n\n")
            fh.write("> **v8 에서 쪼갠 초안이다.** 원본은 "
                     "`program/plan/A-COP_구현계획서_v8.md` 이고 건드리지 않았다.\n"
                     "> 기존 wiki 문서와 합칠 때 중복을 걷어내야 한다.\n\n")
            for n, t, body, _ in items:
                fh.write(f"## v8 §{n} — {t}\n\n")
                fh.write("\n".join(body[1:]).strip() + "\n\n")
    print(f"\n→ {DST}/ 에 {len(groups)}개 파일")
    return 0


if __name__ == "__main__":
    sys.exit(main())
