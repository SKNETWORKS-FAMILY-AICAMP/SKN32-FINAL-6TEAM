"""3단계 — 결함.

채점 질문이 "어디가 깨졌나"가 아니다. 이 저장소에서는 그 질문이 원리적으로
답이 하나가 아닌 경우가 있다 — transition_case 와 _load_projection 은 무엇을
망가뜨려도 깨지는 테스트가 완전히 같다(자카드 1.00, 실측).

그래서 통과 판정은 "테스트를 다시 전부 통과시키는 패치를 냈는가"다. 파일 지목은
채점이 아니라 해설을 여는 중간 단계다.
"""
from __future__ import annotations

import random
from pathlib import Path

from . import defects as defects_mod
from . import progress
from .sandbox import Sandbox

SEPARATOR = "─" * 62


def playable(catalog: dict) -> list[str]:
    """게이트를 통과한 결함만 문제로 낸다."""
    return sorted(
        did for did, entry in catalog.get("entries", {}).items()
        if entry.get("gates", {}).get("kills_tests") and entry.get("failed")
    )


def distinct(catalog: dict, candidates: list[str]) -> list[str]:
    """실패 집합이 똑같은 결함끼리는 하나만 남긴다.

    실측에서 INV-PII-002 와 INV-PII-004 는 깨뜨리는 테스트가 완전히 같았다(자카드 1.00).
    한 판에서 둘 다 나오면 같은 실패 화면을 보고 같은 원인이라고 착각한다.
    """
    seen: dict[tuple[str, ...], str] = {}
    for defect_id in candidates:
        signature = tuple(catalog["entries"][defect_id]["failed"])
        seen.setdefault(signature, defect_id)
    return sorted(seen.values())


def play(target: Path, *, defect_id: str | None = None, fix: Path | None = None) -> int:
    catalog = defects_mod.load_catalog()
    options = playable(catalog)
    if not options:
        print("낼 수 있는 결함이 없다. 먼저 `acop-dojo defects --rebuild` 로 카탈로그를 만든다.")
        return 1
    chosen = defect_id or random.choice(distinct(catalog, options))
    if chosen not in options:
        print(f"{chosen} 은 게이트를 통과하지 못했다. 낼 수 있는 것: {', '.join(options)}")
        return 1

    defect = defects_mod.by_id(chosen)
    entry = catalog["entries"][chosen]
    patch = defects_mod.PATCH_DIR / f"{chosen}.patch"

    print(f"\n3단계 · 결함   {chosen}")
    print("코드 한 곳을 바꿨다. 깨진 테스트만 보여준다.")
    print(SEPARATOR)

    with Sandbox(target) as sandbox:
        assert sandbox.root is not None
        applied, message = sandbox.apply(patch)
        if not applied:
            print(f"결함을 심지 못했다: {message}")
            return 1

        for nodeid in entry["failed"]:
            print(f"  FAILED  {nodeid}")
        print(f"  passed  {424 - len(entry['failed'])}")

        if fix is not None:
            print(f"\n  낸 패치를 적용한다: {fix}")
            ok, message = sandbox.apply(fix)
            if not ok:
                print(f"  패치가 적용되지 않는다: {message}")
                return 1
            print("  전체 테스트를 돌린다 (40초쯤 걸린다)")
            result = sandbox.pytest()
            print(f"  {result.summary}")
            passed = not result.failed
            print("\n  통과. 테스트가 전부 초록으로 돌아왔다." if passed
                  else f"\n  아직이다. 남은 실패: {result.failed[:4]}")
            progress.record_stage("3", status="passed" if passed else "partial",
                                  detail={"defect": chosen, "oracle": "pytest",
                                          "remaining": result.failed})
            if passed:
                progress.claim_ability("불변식 복구", evidence=f"defect:{chosen}", confirmed=True)
            return 0 if passed else 1

    print(f"\n{SEPARATOR}")
    print("어느 파일이 바뀌었나? (경로 일부만 써도 된다)")
    guess = input("  > ").strip()
    hit = bool(guess) and guess.lower() in defect.path.lower()
    print(f"  {'맞다.' if hit else '아니다.'}  실제로는 {defect.path} 다.")

    print("\n왜 이것이 규칙 위반인지 한 줄로 쓴다.")
    explanation = input("  > ").strip()

    print(f"\n{SEPARATOR}")
    print(f"  깨진 규칙   {defect.invariant}")
    print(f"  바뀐 것     {defect.old.strip()}")
    print(f"       →      {defect.new.strip() or '(삭제)'}")
    print(f"\n  {defect.lesson}")
    if defect.counterfactuals:
        print("\n  다음처럼 답했다면 아직 이해한 게 아니다.")
        for item in defect.counterfactuals:
            print(f"    - {item}")
    print("\n  스스로 대조한다. 본인 답이 위 설명의 핵심을 담고 있나?")
    print(f"  직접 고쳐 보려면:  acop-dojo defect {chosen} --fix 내패치.patch")

    progress.record_stage("3", status="explored",
                          detail={"defect": chosen, "file_guess_ok": hit,
                                  "explanation": explanation, "grading": "self"})
    progress.claim_ability("불변식 설명", evidence=f"defect:{chosen}", confirmed=False)
    return 0
