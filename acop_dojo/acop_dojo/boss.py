"""4단계 — 보스전.

학습에 쓰지 않은 모듈에서 같은 규칙을 찾게 한다. 앞 단계와 같은 모듈에서 한 번 더
물으면 그 코드를 외웠는지만 알 수 있다. 전이는 다른 코드에서 재현될 때만 확인된다.

기록도 나눈다. 처음 성공은 acquisition, 재시도는 retention, 안 배운 모듈에서의
성공은 transfer 다. 셋을 한 점수로 합치면 무엇을 아는지 알 수 없게 된다.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from . import defect_stage
from . import defects as defects_mod
from . import progress
from .sandbox import Sandbox

SEPARATOR = "─" * 62
BOSS_SCENARIO = "return-refund-no-side-effect-v1"

#: 역할 이름 → 트레이스에서 그 역할을 하는 심볼의 조각
ROLES = {
    "결과가 계약에 맞는지 검사하는 곳": "_next_action_consistency",
    "중복 실행을 막는 키를 만드는 곳": "idempotency_key",
    "근거를 모으는 곳": "_evidence",
}
#: 이 트레이스에 나오면 안 되는 것. 나온다면 Team 이 상태를 직접 바꿨다는 뜻이다.
FORBIDDEN = "transition_case"


def _teachable(steps: list[dict[str, Any]]) -> list[str]:
    return [f"{s['path'].split('/')[-1]}::{s['symbol']}" for s in steps
            if "<locals>" not in s["symbol"]]


def _ready(data: dict[str, Any]) -> bool:
    stages = data.get("stages", {})
    return all(stage in stages for stage in ("0", "1", "2", "3"))


def _transfer_questions(labels: list[str]) -> int:
    correct = 0
    for question, needle in ROLES.items():
        print(f"\n  {question}? 번호로 답한다.")
        raw = input("  > ").strip()
        picked = labels[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(labels) else ""
        ok = needle in picked
        correct += ok
        answer = next((label for label in labels if needle in label), "(이 트레이스에 없다)")
        print(f"  {'맞다.' if ok else '아니다.'}  {answer}")
    return correct


def _outcome_question(trace: dict[str, Any]) -> int:
    """결과 계약을 값으로 묻는다.

    학습 시나리오(배송 조회)는 respond 에 제안 0건이었다. 여기서는 다르다.
    같은 계약이 상황에 따라 어떻게 갈리는지가 전이의 핵심이다.
    """
    result = next((step["domain"] for step in trace["steps"]
                   if step["symbol"].endswith("_next_action_consistency")
                   and step.get("domain")), None)
    if not result:
        return 0
    options = ["respond", "wait_for_approval", "wait_for_input", "escalate", "handoff"]
    print("")
    print("  이 Team 이 돌려준 next_action 은? 번호로 답한다.")
    for index, option in enumerate(options, start=1):
        print(f"    {index}  {option}")
    raw = input("  > ").strip()
    picked = options[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(options) else ""
    actual = result.get("next_action")
    ok = picked == actual
    print(f"  {'맞다.' if ok else '아니다.'}  {actual} 이고 제안은 {result.get('proposals')}건이다.")
    print("  배송 조회에서는 respond 에 제안 0건이었다. 조회는 제안이 필요 없고")
    print("  환불은 승인이 필요하다 — 같은 계약이 상황에 따라 다르게 채워진다.")
    return int(ok)


def play(target: Path, trace: dict[str, Any], *, fix: Path | None = None,
         force: bool = False, defect_id: str | None = None) -> int:
    data = progress.load()
    if not _ready(data) and not force:
        missing = [s for s in ("0", "1", "2", "3") if s not in data.get("stages", {})]
        print(f"보스전은 0~3단계를 지난 뒤에 연다. 아직 안 한 단계: {', '.join(missing)}")
        print("그래도 열려면 --force 를 준다.")
        return 1

    labels = _teachable(trace["steps"])
    print("\n4단계 · 보스전")
    print("여기는 0~2단계에서 한 번도 지나가지 않은 모듈이다.")
    print("해설은 없다. 배운 규칙이 이 코드에서 어떻게 지켜지는지 직접 찾는다.")
    print(SEPARATOR)
    for index, label in enumerate(labels, start=1):
        print(f"  {index:2d}  {label}")

    correct = _transfer_questions(labels)
    correct += _outcome_question(trace)

    print(f"\n{SEPARATOR}")
    print(f"  이 트레이스에 {FORBIDDEN} 이 나오나? (y/n)")
    raw = input("  > ").strip().lower()
    appears = any(FORBIDDEN in label for label in labels)
    ok = raw.startswith("y") == appears
    correct += ok
    print(f"  {'맞다.' if ok else '아니다.'}  {'나온다.' if appears else '나오지 않는다.'}")
    print("  이게 핵심이다. Team 은 상태를 직접 바꾸지 않는다 — 제안만 돌려주고,")
    print("  상태 전이는 Controller 가 transition_case 로 한다. 배송 시나리오에서 본 규칙이")
    print("  이름도 팀도 다른 이 코드에서 똑같이 지켜지고 있다.")

    already = {entry.split("::")[-1] for entry in data.get("discovered", [])}
    overlap = [label for label in labels if label.split("::")[-1] in already]
    print(f"\n  앞 단계에서 이미 지나간 함수가 여기 {len(overlap)}개 다시 나온다.")
    for label in overlap:
        print(f"    {label}")

    total = len(ROLES) + 2
    print(f"\n  전이 문제 {correct}/{total}")
    return _repair(target, correct, total, fix, defect_id)


def _repair(target: Path, correct: int, total: int, fix: Path | None,
            defect_id: str | None = None) -> int:
    """마지막 관문. 안 배운 모듈의 결함을 직접 고친다. 판정은 pytest 가 한다."""
    catalog = defects_mod.load_catalog()
    playable = [d.defect_id for d in defects_mod.DEFECTS
                if d.path.startswith("app/modules/")
                and d.defect_id in defect_stage.playable(catalog)]
    if not playable:
        print("\n  이 모듈에서 게이트를 통과한 결함이 아직 없다.")
        print("  `acop-dojo defects --rebuild` 를 돌린 뒤 다시 온다.")
        progress.record_stage("4", status="partial",
                              detail={"transfer_correct": correct, "of": total})
        return 1

    # 한 번에 통과하는 경우가 드물어 같은 결함을 다시 받을 수 있어야 한다.
    if defect_id and defect_id in playable:
        chosen = defect_id
    else:
        chosen = random.choice(defect_stage.distinct(catalog, playable))
    defect = defects_mod.by_id(chosen)
    entry = catalog["entries"][chosen]
    patch = defects_mod.PATCH_DIR / f"{chosen}.patch"

    print(f"\n{SEPARATOR}")
    print(f"  마지막이다. 이 모듈에 결함 하나를 심었다: {chosen}")
    with Sandbox(target) as sandbox:
        applied, message = sandbox.apply(patch)
        if not applied:
            print(f"  결함을 심지 못했다: {message}")
            return 1
        print(f"  파일: {defect.path}")
        for nodeid in entry["failed"]:
            print(f"  FAILED  {nodeid}")
        if fix is None:
            print("\n  고칠 패치를 만들어 다시 부른다:")
            print("    acop-dojo boss --fix 내패치.patch")
            print("  힌트는 없다. 깨진 테스트를 읽고 무엇이 규칙인지 먼저 말로 정리한다.")
            progress.record_stage("4", status="in_progress",
                                  detail={"transfer_correct": correct, "of": total,
                                          "defect": chosen})
            return 0

        ok, message = sandbox.apply(fix)
        if not ok:
            print(f"  패치가 적용되지 않는다: {message}")
            return 1
        print("\n  전체 테스트를 돌린다")
        result = sandbox.pytest()
        print(f"  {result.summary}")
        passed = not result.failed
        remaining = result.failed[:4]

    print(SEPARATOR)
    if passed and correct == total:
        print("  통과. 안 배운 모듈에서 규칙을 찾아내고 고쳤다.")
    elif passed:
        print("  수리는 통과했다. 전이 문제에서 틀린 것은 다시 본다.")
    else:
        print(f"  아직이다. 남은 실패: {remaining}")
    progress.record_stage("4", status="passed" if passed else "partial",
                          detail={"transfer_correct": correct, "of": total,
                                  "defect": chosen, "oracle": "pytest"})
    progress.claim_ability("안 배운 모듈로 전이", evidence=f"boss:{chosen}:{correct}/{total}",
                           confirmed=passed and correct == total)
    return 0 if passed else 1
