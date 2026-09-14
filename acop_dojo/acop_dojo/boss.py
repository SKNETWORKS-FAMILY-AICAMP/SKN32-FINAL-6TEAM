"""4단계 — 보스전.

학습에 쓰지 않은 코드에서 같은 규칙을 찾게 한다. 앞 단계와 같은 코드에서 한 번 더
물으면 그 코드를 외웠는지만 알 수 있다. 전이는 다른 코드에서 재현될 때만 확인된다.

보스는 베이스먼트(도메인을 모르는 코어)의 검증 엔진 `app/core/verification.py` 다.
전이가 두 겹이다.
  ① 학습 트랙(상태 조회·체크포인트·리듀서)은 이 파일을 지나가지 않는다.
  ② 테스트가 엔진에 물리는 선언은 제품 도메인(여행)이 아니라 커머스다.
     엔진을 한 줄도 안 고치고 다른 도메인이 돈다는 것이 베이스먼트의 주장이고,
     그 대조군이 `tests/architecture/test_engine_serves_another_domain.py` 다.

2026-09-14 까지의 보스는 커머스 환불 Team(`customer_ops/return_refund.py`)이었다.
도메인이 여행으로 바뀌면서 그 파일이 지워져 보스가 열리지 않았다.
Team 은 도메인이 바뀌면 통째로 바뀐다 — 보스는 바뀌지 않는 쪽에 둔다.

기록도 나눈다. 처음 성공은 acquisition, 재시도는 retention, 안 배운 코드에서의
성공은 transfer 다. 셋을 한 점수로 합치면 무엇을 아는지 알 수 없게 된다.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Callable

from . import defect_stage
from . import defects as defects_mod
from . import progress
from . import review
from .sandbox import Sandbox

SEPARATOR = "─" * 62
BOSS_SCENARIO = "engine-serves-another-domain-v1"

#: 역할 이름 → 트레이스에서 그 역할을 하는 심볼의 조각
ROLES = {
    "제안 하나를 받아 검사를 시작하는 입구": "verify_proposal",
    "금액·개수가 상한을 넘는지 재는 곳": "_verify_quantities",
    "문자열·정수를 같은 단위의 숫자로 맞추는 곳": "_to_decimal",
}
#: 엔진 실행부에 있으면 안 되는 도메인 어휘. 대조군 테스트가 쓰는 목록과 같다.
DOMAIN_WORDS = ("payment_id", "subscription_id", "order_id", "amount_cents", "total_cents")
ENGINE = "app/core/verification.py"


def _teachable(steps: list[dict[str, Any]]) -> list[str]:
    """번호로 고를 목록. 같은 함수가 여러 번 불려도 한 번만 싣는다."""
    labels: list[str] = []
    for step in steps:
        if "<locals>" in step["symbol"]:
            continue
        label = f"{step['path'].split('/')[-1]}::{step['symbol']}"
        if label not in labels:
            labels.append(label)
    return labels


def _ready(data: dict[str, Any]) -> bool:
    stages = data.get("stages", {})
    return all(stage in stages for stage in ("0", "1", "2", "3"))


def _pick(prompt: str, options: list[str]) -> str:
    print(f"\n  {prompt} 번호로 답한다.")
    for index, option in enumerate(options, start=1):
        print(f"    {index}  {option}")
    raw = input("  > ").strip()
    return options[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(options) else ""


def _yes_no(prompt: str) -> bool:
    print(f"\n  {prompt} (y/n)")
    return input("  > ").strip().lower().startswith("y")


def _role_questions(labels: list[str]) -> list[Callable[[], bool]]:
    """역할 문제. 답이 트레이스에 없는 역할은 묻지 않는다 — 묻지 않은 것을 분모에 넣지 않는다."""
    asked = []
    for question, needle in ROLES.items():
        answer = next((label for label in labels if label.endswith(f"::{needle}")), None)
        if answer is None:
            continue

        def ask(question: str = question, needle: str = needle, answer: str = answer) -> bool:
            picked = _pick(f"{question}은?", labels)
            ok = picked.endswith(f"::{needle}")
            print(f"  {'맞다.' if ok else '아니다.'}  {answer}")
            return ok
        asked.append(ask)
    return asked


def _outcome_question(trace: dict[str, Any]) -> Callable[[], bool] | None:
    """판정을 묻는다. 답은 트레이스가 아니라 그 테스트의 단언이다 — 테스트가 통과했을 때만 묻는다."""
    if trace.get("outcome", {}).get("status") != "passed":
        return None

    def ask() -> bool:
        options = ["통과 — 문제 없음",
                   "refund_amount 에서 걸린다",
                   "order_id 에서 걸린다",
                   "선언되지 않은 필드라서 걸린다"]
        print("\n  상황: 5만원짜리 주문(ord-1001)에 7만원 환불 제안이 들어왔다.")
        picked = _pick("엔진은 어떻게 판정하나?", options)
        ok = picked == options[1]
        print(f"  {'맞다.' if ok else '아니다.'}  {options[1]}.")
        print("  주문은 있으니 order_id 는 통과한다. 금액 규칙이 주문 총액(total_cents)을")
        print("  상한으로 잡고, 원 단위 제안을 scale 100 으로 맞춰 비교한다.")
        print("  이 규칙을 엔진이 아는 게 아니다 — 테스트가 넘긴 선언(QuantityRule)에 적혀 있다.")
        return ok
    return ask


def _layer_question(labels: list[str]) -> Callable[[], bool]:
    appears = any(label.startswith(("activity", "dining", "mobility")) or "/modules/" in label
                  for label in labels)

    def ask() -> bool:
        ok = _yes_no("이 트레이스에 app/modules/ 아래 파일(Team 코드)이 나오나?") == appears
        print(f"  {'맞다.' if ok else '아니다.'}  {'나온다.' if appears else '나오지 않는다.'}")
        print("  12단계 전부가 verification.py 안이다. 검증은 Team 이 아니라 코어가 한다 —")
        print("  Team 이 낸 제안을 코어가 사실과 대조하고, 틀리면 실행 전에 막는다.")
        return ok
    return ask


def _vocabulary_question(target: Path) -> Callable[[], bool] | None:
    """엔진 파일을 직접 읽어 답을 낸다. 대조군 테스트와 같은 방식으로 주석을 뺀다."""
    source_path = target / ENGINE
    if not source_path.exists():
        return None
    code = "\n".join(line for line in source_path.read_text(encoding="utf-8").splitlines()
                     if not line.strip().startswith(("#", "★", '"""')))
    found = [word for word in DOMAIN_WORDS if word in code]

    def ask() -> bool:
        ok = _yes_no("그러면 verification.py 실행부에 order_id 같은 커머스 어휘가 있나?") == bool(found)
        print(f"  {'맞다.' if ok else '아니다.'}  "
              f"{'있다: ' + ', '.join(found) if found else '없다.'}")
        print("  이게 핵심이다. 엔진은 '어떤 필드를 어느 표와 대조하라'는 선언만 받는다.")
        print("  여행 선언을 물리면 여행이, 커머스 선언을 물리면 커머스가 돈다.")
        print("  2026-08-16 이전 엔진은 order_id 를 거부 목록에 박아 두어, 그때 제품이던")
        print("  쇼핑몰의 가장 중요한 식별자가 자동으로 거부됐다.")
        return ok
    return ask


def play(target: Path, trace: dict[str, Any], *, fix: Path | None = None,
         force: bool = False, defect_id: str | None = None) -> int:
    data = progress.load()
    if not _ready(data) and not force:
        missing = [s for s in ("0", "1", "2", "3") if s not in data.get("stages", {})]
        print(f"보스전은 0~3단계를 지난 뒤에 연다. 아직 안 한 단계: {', '.join(missing)}")
        print("그래도 열려면 --force 를 준다.")
        return 1

    labels = _teachable(trace["steps"])
    print("\n4단계 · 보스전 — 베이스먼트의 검증 엔진")
    print("여기는 학습 트랙에서 한 번도 지나가지 않은 코드다. 게다가 물린 선언은")
    print("여행이 아니라 커머스다. 해설은 없다. 배운 규칙을 직접 찾는다.")
    print(SEPARATOR)
    for index, label in enumerate(labels, start=1):
        print(f"  {index:2d}  {label}")

    questions = _role_questions(labels)
    questions += [q for q in (_outcome_question(trace), _layer_question(labels),
                              _vocabulary_question(target)) if q is not None]
    correct = sum(bool(ask()) for ask in questions)
    total = len(questions)

    already = {entry.split("::")[-1] for entry in data.get("discovered", [])}
    overlap = [label for label in labels if label.split("::")[-1] in already]
    print(f"\n  앞 단계에서 이미 지나간 함수가 여기 {len(overlap)}개 다시 나온다.")
    for label in overlap:
        print(f"    {label}")

    print(f"\n  전이 문제 {correct}/{total}")
    paths = {step["path"] for step in trace["steps"]}
    return _repair(target, correct, total, fix, defect_id, paths)


def _repair(target: Path, correct: int, total: int, fix: Path | None,
            defect_id: str | None, paths: set[str]) -> int:
    """마지막 관문. 보스 트레이스가 지나간 파일의 결함을 직접 고친다. 판정은 pytest 가 한다."""
    catalog = defects_mod.load_catalog()
    playable = [d.defect_id for d in defects_mod.DEFECTS
                if d.path in paths and d.defect_id in defect_stage.playable(catalog)]
    if not playable:
        print(f"\n  {', '.join(sorted(paths))} 에서 게이트를 통과한 결함이 아직 없다.")
        print("  `acop-dojo defects` 를 돌린 뒤 다시 온다.")
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
    print(f"  마지막이다. 이 엔진에 결함 하나를 심었다: {chosen}")
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
        remaining = defect_stage.new_failures(catalog, result.failed)
        passed = not remaining

    print(SEPARATOR)
    if passed and correct == total:
        print("  통과. 안 배운 코드에서 규칙을 찾아내고 고쳤다.")
    elif passed:
        print("  수리는 통과했다. 전이 문제에서 틀린 것은 다시 본다.")
    else:
        print(f"  아직이다. 남은 실패: {remaining[:4]}")
    progress.record_stage("4", status="passed" if passed else "partial",
                          detail={"transfer_correct": correct, "of": total,
                                  "defect": chosen, "oracle": "pytest"})
    progress.claim_ability("안 배운 코드로 전이", evidence=f"boss:{chosen}:{correct}/{total}",
                           confirmed=passed and correct == total)
    review.schedule(defect.invariant, source=chosen)
    return 0 if passed else 1
