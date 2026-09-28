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

from . import ask
from . import defects as defects_mod
from . import progress
from . import review
from . import tracks as tracks_mod
from .sandbox import Sandbox

SEPARATOR = "─" * 62


def playable(catalog: dict) -> list[str]:
    """게이트를 통과한 결함만 문제로 낸다."""
    return sorted(
        did for did, entry in catalog.get("entries", {}).items()
        if entry.get("gates", {}).get("kills_tests") and entry.get("failed")
        and not _excluded(did)
    )


def _excluded(defect_id: str) -> str:
    """게이트를 통과해도 문제로 내지 않는 것이 있다. 이유가 있으면 그 문자열이다."""
    try:
        return defects_mod.by_id(defect_id).excluded
    except SystemExit:
        return ""


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


def new_failures(catalog: dict, failed: list[str]) -> list[str]:
    """결함 없이도 깨지는 테스트를 뺀 실패. 수리 판정은 이것이 비었는지로 한다.

    사본에는 .git 이 없고, RAG 테스트는 외부 API 잔액에 달려 있다. 이것들까지
    초록이어야 통과라고 하면 아무도 통과하지 못한다(2026-09-14 기준선 5건 실측).
    """
    known = set((catalog.get("baseline") or {}).get("failed") or [])
    return sorted(set(failed) - known)


def _pick(catalog: dict, options: list[str]) -> str:
    """결함 하나를 고른다. 보통·어려움은 안 본 결함을 먼저 낸다 — 본 결함은 답을 외워 넘길 수 있다."""
    everything = distinct(catalog, options) or options
    if ask.level() == "easy":
        return random.choice(everything)
    seen = progress.load().get("defects", {})
    fresh = [d for d in everything if d not in seen]
    if not fresh:
        print(f"이 트랙의 결함 {len(everything)}개를 모두 한 번씩 봤다. 본 결함이 다시 나온다.")
        return random.choice(everything)
    print(f"아직 안 본 결함 {len(fresh)}/{len(everything)}개 가운데서 고른다.")
    return random.choice(fresh)


def _mark_seen(defect_id: str, *, fixed: bool | None = None) -> None:
    """본 결함을 적는다. 고쳤으면 고쳤다고도 적는다(한 번 고친 기록은 지우지 않는다)."""
    data = progress.load()
    entry = data.setdefault("defects", {}).setdefault(defect_id, {"seen": 0, "fixed": False})
    entry["seen"] += 1
    entry["fixed"] = bool(entry.get("fixed") or fixed)
    progress.save(data)


def play(target: Path, *, defect_id: str | None = None, fix: Path | None = None,
         track: str = "all") -> int:
    catalog = defects_mod.load_catalog()
    track_def = tracks_mod.get(track)
    # 자기 파트의 코드에서만 문제를 낸다. 남의 디렉터리는 배울 대상이 아니다.
    options = [d for d in playable(catalog)
               if tracks_mod.owns(track_def, defects_mod.by_id(d).path)]
    if not options:
        print(f"{track_def.title}에서 출제할 수 있는 결함이 없다.")
        print("결함 카탈로그가 비어 있다면 먼저 `python dojo.py defects --rebuild`를 실행한다.")
        return 1
    chosen = defect_id or _pick(catalog, options)
    if chosen not in options:
        print(f"{chosen}은 게이트(출제 가능 여부 검사)를 통과하지 못했다. 출제할 수 있는 결함: {', '.join(options)}")
        return 1

    defect = defects_mod.by_id(chosen)
    entry = catalog["entries"][chosen]
    patch = defects_mod.PATCH_DIR / f"{chosen}.patch"

    print(f"\n3단계 · 결함 찾고 고치기   {chosen}")
    print("코드 한 곳에 결함을 넣었다. 실패한 테스트를 보고 원인을 찾는다.")
    print(SEPARATOR)

    with Sandbox(target) as sandbox:
        assert sandbox.root is not None
        applied, message = sandbox.apply(patch)
        if not applied:
            print(f"결함을 적용하지 못했다. 원인: {message}")
            return 1

        for nodeid in entry["failed"]:
            print(f"  FAILED  {nodeid}")
        print(f"  표시하지 않은 테스트는 통과했다. (기준선: {catalog.get('baseline', {}).get('summary', '?')})")

        if fix is not None:
            print(f"\n  제출한 패치를 적용한다: {fix}")
            ok, message = sandbox.apply(fix)
            if not ok:
                print(f"  패치를 적용하지 못했다. 원인: {message}")
                return 1
            print("  전체 테스트를 실행한다. 약 40초가 걸린다.")
            result = sandbox.pytest()
            print(f"  {result.summary}")
            remaining = new_failures(catalog, result.failed)
            passed = not remaining
            print("\n  통과했다. 결함 때문에 실패한 테스트를 모두 복구했다." if passed
                  else f"\n  아직 통과하지 못했다. 남은 실패: {remaining[:4]}")
            progress.record_stage("3", status="passed" if passed else "partial",
                                  detail={"defect": chosen, "oracle": "pytest",
                                          "remaining": remaining})
            _mark_seen(chosen, fixed=passed)
            if passed:
                progress.claim_ability("불변식 복구", evidence=f"defect:{chosen}", confirmed=True)
                # 같은 규칙을 나중에 다른 코드에서 다시 묻는다.
                review.schedule(defect.invariant, source=chosen)
            return 0 if passed else 1

    print(f"\n{SEPARATOR}")
    tally = ask.Tally()
    pool = [defects_mod.by_id(d).path for d in playable(catalog)]
    options, right = ask.file_choices(defect.path, pool)
    guess = tally.add(ask.free(
        "결함이 들어간 파일을 쓴다. 경로의 일부만 써도 된다.",
        hints=[f"깨진 규칙: {defect.invariant}",
               f"그 파일은 {ask.layer_of(defect.path)}에 있다.",
               f"바뀐 줄의 원래 코드: {defect.old.strip().splitlines()[0][:70]}"],
        fallback=(options, right)))
    hit = (guess.index == right) if guess.via_choices else (
        bool(guess.text) and guess.text.lower() in defect.path.lower())
    print(f"  {'맞다.' if hit else '아니다.'}  실제로는 {defect.path} 다.")

    # 설명 보기는 정답 설명 하나와 흔한 오해로 만든다. 오해가 모자라면 다른 규칙의 설명으로 채운다.
    wrongs = list(defect.counterfactuals)
    others = [d.lesson for d in defects_mod.DEFECTS
              if d.defect_id != chosen and d.invariant != defect.invariant]
    while len(wrongs) < 3 and others:
        wrongs.append(others.pop(0))
    reasons = sorted(wrongs[:3] + [defect.lesson])
    said = tally.add(ask.free(
        "이 변경이 규칙을 어긴 이유를 한 줄로 쓴다.",
        hints=[f"원래 지키던 규칙: {defect.invariant}",
               f"코드 변경: {defect.old.strip().splitlines()[0][:60]} → {(defect.new.strip() or '(삭제)')[:60]}",
               "그 줄이 사라지거나 바뀌었을 때 검사 없이 통과하는 요청을 찾는다."],
        fallback=(reasons, reasons.index(defect.lesson))))
    explanation = said.text

    print(f"\n{SEPARATOR}")
    print(f"  깨진 규칙   {defect.invariant}")
    print(f"  바뀐 것     {defect.old.strip()}")
    print(f"       →      {defect.new.strip() or '(삭제)'}")
    print(f"\n  {defect.lesson}")
    if defect.counterfactuals:
        print("\n  아래 설명은 이 결함의 원인이 아니다.")
        for item in defect.counterfactuals:
            print(f"    - {item}")
    print("\n  본인 답과 위 설명을 비교하고, 핵심 원인이 들어 있는지 확인한다.")
    print(f"  직접 고치기:  acop-dojo defect {chosen} --fix 내패치.patch")

    print(f"\n  {tally.summary()}")
    progress.record_stage("3", status="explored",
                          detail={"defect": chosen, "file_guess_ok": hit,
                                  "explanation": explanation, "grading": "self",
                                  **tally.detail()})
    progress.claim_ability("불변식 설명", evidence=f"defect:{chosen}", confirmed=False)
    _mark_seen(chosen)
    review.schedule(defect.invariant, source=chosen)
    return 0
