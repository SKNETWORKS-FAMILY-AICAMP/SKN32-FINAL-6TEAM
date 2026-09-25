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

from . import ask
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


def _missing(data: dict[str, Any]) -> list[str]:
    """보스전 앞에 남은 것. 0~2단계는 해 봤으면 된다 — 자기 채점이라 통과 표시가 약하다.
    3단계는 pytest 가 판정하니 **통과**해야 한다. 예전엔 기록이 있기만 하면 열려,
    결함을 못 고친 채로도 들어왔다(2026-09-14 codex-alt 지적)."""
    stages = data.get("stages", {})
    missing = [f"{s}단계" for s in ("0", "1", "2") if s not in stages]
    if stages.get("3", {}).get("status") != "passed":
        missing.append("3단계 통과(결함 수리를 pytest 가 인정해야 한다)")
    return missing


#: 보스전 한 판 동안 받은 도움. 도움을 받고 맞힌 전이는 확정으로 치지 않는다.
TALLY = ask.Tally()


def _pick(prompt: str, options: list[str], *, hints: list[str] | None = None,
          answer: str | None = None) -> str:
    index = options.index(answer) if answer in options else None
    return TALLY.add(ask.choice(prompt, options, hints=hints or [], answer_index=index)).text


def _yes_no(prompt: str, *, hints: list[str] | None = None) -> bool:
    return TALLY.add(ask.yes_no(prompt, hints=hints or [])).text == "y"


def _notes() -> dict:
    import json
    from .config import data_dir
    try:
        return json.loads((data_dir() / "annotations.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _full(label: str) -> str:
    """`verification.py::f` 를 해설 사전의 키(`app/core/verification.py::f`)로 바꾼다."""
    return f"app/core/{label}" if not label.startswith("app/") else label


def _role_questions(labels: list[str]) -> list[Callable[[], bool]]:
    """역할 문제. 답이 트레이스에 없는 역할은 묻지 않는다 — 묻지 않은 것을 분모에 넣지 않는다."""
    asked = []
    for question, needle in ROLES.items():
        answer = next((label for label in labels if label.endswith(f"::{needle}")), None)
        if answer is None:
            continue

        def ask(question: str = question, needle: str = needle, answer: str = answer) -> bool:
            note = _notes().get(_full(answer), "")
            picked = _pick(f"{question}은?", labels, answer=answer,
                           hints=["함수 이름에 하는 일이 드러난다"]
                                 + ([f"그 함수는 이런 일을 한다 — {note}"] if note else []))
            ok = picked.endswith(f"::{needle}")
            print(f"  {'맞다.' if ok else '아니다.'}  {answer}")
            return ok
        asked.append(ask)
    return asked


#: 판정 문항에 쓰는 세 번째 도메인. 트레이스(커머스)에도 제품(여행)에도 없는 선언이다.
_LESSON_POLICY = {"references": {"lesson_id": "lessons"},
                  "quantity": {"field": "refund_fee", "reference": "lesson_id",
                               "limit_key": "price_won", "scale": 1}}
_ENGINE_PROBE = """
import json, sys
from decimal import Decimal
from app.core.verification import Facts, QuantityRule, VerificationPolicy, verify_proposal
spec = json.loads(sys.argv[1])
q = spec["policy"]["quantity"]
policy = VerificationPolicy(references=spec["policy"]["references"],
                            quantities=(QuantityRule(field=q["field"], reference=q["reference"],
                                                     limit_key=q["limit_key"], scale=Decimal(q["scale"])),))
facts = Facts(collections={"lessons": spec["lessons"]}, evidence_ids=frozenset({"ev-1"}))
problems = verify_proposal(arguments=spec["arguments"], rationale_evidence_ids=["ev-1"],
                           facts=facts, policy=policy)
print(json.dumps([[p.field, p.reason] for p in problems], ensure_ascii=False))
"""


def _lesson_case(rng: random.Random) -> tuple[str, dict[str, Any], int]:
    """매번 다른 상황을 만든다. 같은 문항을 외워 다시 통과하지 못하게 한다.

    돌려주는 것: 화면에 보일 상황 · 제안 인자 · 수업 L-7 의 가격
    """
    price = rng.choice([30_000, 45_000, 60_000, 80_000])
    kind = rng.choice(["over", "within", "unknown_ref", "no_ref", "undeclared"])
    if kind == "over":
        amount = price + rng.choice([5_000, 10_000, 20_000])
        return (f"{price:,}원 수업 L-7 에 {amount:,}원 환불",
                {"lesson_id": "L-7", "refund_fee": amount}, price)
    if kind == "within":
        amount = rng.choice([price // 2, price - 5_000, price])
        return (f"{price:,}원 수업 L-7 에 {amount:,}원 환불",
                {"lesson_id": "L-7", "refund_fee": amount}, price)
    if kind == "unknown_ref":
        return "등록되지 않은 수업 L-99 를 가리키는 제안", {"lesson_id": "L-99"}, price
    if kind == "no_ref":
        return f"수업 id 없이 {price // 2:,}원 환불", {"refund_fee": price // 2}, price
    return (f"{price:,}원 수업 L-7 에 쿠폰 코드를 붙인 제안",
            {"lesson_id": "L-7", "coupon_code": "SPRING"}, price)


def _outcome_question(target: Path) -> Callable[[], bool] | None:
    """판정을 묻는다. 정답은 사람이 적지 않는다 — 대상 저장소의 엔진을 실제로 돌려 얻는다.

    ★처음 판은 트레이스의 커머스 상황을 그대로 묻고 답을 코드에 박았다. 재도전하면 외워서
    통과한다(2026-09-14 codex-alt 지적). 지금은 트레이스에 없는 도메인(수업 예약)의
    선언과 값을 매번 새로 만든다 — 배운 규칙을 새 입력에 적용해야 맞힌다.
    """
    import json
    import subprocess
    import sys

    situation, arguments, price = _lesson_case(random.Random())
    spec ={"policy": _LESSON_POLICY, "lessons": {"L-7": {"lesson_id": "L-7", "price_won": price}},
            "arguments": arguments}
    try:
        run = subprocess.run([sys.executable, "-c", _ENGINE_PROBE,
                              json.dumps(spec, ensure_ascii=False)],
                             cwd=target, capture_output=True, text=True, encoding="utf-8",
                             timeout=60, check=True)
        problems = json.loads(run.stdout.strip().splitlines()[-1])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None  # 엔진을 못 돌리면 묻지 않는다 — 묻지 않은 것은 분모에 넣지 않는다

    options = ["검사를 통과한다", "refund_fee 필드에서 거부된다",
               "lesson_id 필드에서 거부된다", "coupon_code 필드에서 거부된다"]
    fields = {field for field, _ in problems}
    answer = options[0] if not fields else next(
        (o for o in options[1:] if o.split()[0] in fields), None)
    if answer is None or len(fields) > 1:
        return None

    def ask() -> bool:
        print("\n  이번에는 수업 예약 규칙을 선언했다. 검증 엔진은 바꾸지 않았다.")
        print("    references(참조 규칙)  lesson_id → lessons")
        print("    quantities(상한 규칙)  refund_fee ≤ lessons[lesson_id].price_won  (scale: 배율 1)")
        print(f"  검사할 상황: {situation}")
        picked = _pick("검증 엔진의 판정을 고른다.", options, answer=answer,
                       hints=["선언에서 어떤 필드를 어느 표와 대조하는지 먼저 확인한다.",
                               "상황의 값을 선언한 규칙에 하나씩 대조한다."])
        ok = picked == answer
        print(f"  {'맞다.' if ok else '아니다.'}  {answer}.")
        for field, reason in problems:
            print(f"  검증 엔진의 판단 근거 — {field}: {reason}")
        print("  이 정답은 방금 이 저장소의 verification.py를 실행해 얻었다.")
        return ok
    return ask


def _layer_question(labels: list[str]) -> Callable[[], bool]:
    appears = any(label.startswith(("activity", "dining", "mobility")) or "/modules/" in label
                  for label in labels)

    def ask() -> bool:
        ok = _yes_no("이 트레이스(실행 기록)에 app/modules/ 아래의 Team(작업 수행 모듈) 코드가 나오는가?",
                     hints=["위 목록에서 파일 이름을 확인한다.", "모든 단계가 같은 파일에 있는지 확인한다."]) == appears
        print(f"  {'맞다.' if ok else '아니다.'}  {'나온다.' if appears else '나오지 않는다.'}")
        print("  위 실행 지점은 모두 verification.py 안에 있다. 검증은 Team(작업 수행 모듈)이 아니라 코어가 한다.")
        print("  코어는 Team이 낸 제안을 사실과 대조하고, 틀리면 실행 전에 막는다.")
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
        ok = _yes_no("verification.py 실행부에 order_id 같은 커머스 전용 용어가 있는가?",
                     hints=["엔진은 대조할 필드를 선언으로 받는다.",
                             "엔진이 도메인 이름을 직접 알면 다른 도메인에 재사용할 수 없다."]) == bool(found)
        print(f"  {'맞다.' if ok else '아니다.'}  "
              f"{'있다: ' + ', '.join(found) if found else '없다.'}")
        print("  핵심은 엔진이 '어떤 필드를 어느 표와 대조하라'는 선언만 받는다는 점이다.")
        print("  여행 규칙을 선언하면 여행을 검증하고, 커머스 규칙을 선언하면 커머스를 검증한다.")
        print("  2026-08-16 이전 엔진은 order_id 를 거부 목록에 박아 두어, 그때 제품이던")
        print("  쇼핑몰의 가장 중요한 식별자가 자동으로 거부됐다.")
        return ok
    return ask


def play(target: Path, trace: dict[str, Any], *, fix: Path | None = None,
         force: bool = False, defect_id: str | None = None) -> int:
    data = progress.load()
    missing = _missing(data)
    if missing and not force:
        print(f"보스전을 열려면 0~2단계를 진행하고 3단계를 통과해야 한다. 남은 것: {', '.join(missing)}")
        print("선행 단계를 건너뛰려면 --force를 사용한다.")
        return 1

    labels = _teachable(trace["steps"])
    print("\n4단계 · 보스전 — 베이스먼트(도메인을 모르는 코어)의 검증 엔진")
    print("학습 트랙에서 다루지 않은 코드에 배운 규칙을 적용한다.")
    print("여행이 아닌 커머스 규칙을 선언한 검증 엔진을 해설 없이 분석한다.")
    print(SEPARATOR)
    for index, label in enumerate(labels, start=1):
        print(f"  {index:2d}  {label}")

    questions = _role_questions(labels)
    questions += [q for q in (_outcome_question(target), _layer_question(labels),
                              _vocabulary_question(target)) if q is not None]
    correct = sum(bool(ask()) for ask in questions)
    total = len(questions)

    already = {entry.split("::")[-1] for entry in data.get("discovered", [])}
    overlap = [label for label in labels if label.split("::")[-1] in already]
    print(f"\n  앞 단계에서 확인한 함수 중 {len(overlap)}개가 이 실행 경로에도 나온다.")
    for label in overlap:
        print(f"    {label}")

    print(f"\n  전이(배운 규칙을 새 코드에 적용하기) 문제 정답 수: {correct}/{total}")
    paths = {step["path"] for step in trace["steps"]}
    return _repair(target, correct, total, fix, defect_id, paths)


def _repair(target: Path, correct: int, total: int, fix: Path | None,
            defect_id: str | None, paths: set[str]) -> int:
    """마지막 관문. 보스 트레이스가 지나간 파일의 결함을 직접 고친다. 판정은 pytest 가 한다."""
    catalog = defects_mod.load_catalog()
    playable = [d.defect_id for d in defects_mod.DEFECTS
                if d.path in paths and d.defect_id in defect_stage.playable(catalog)]
    if not playable:
        print(f"\n  {', '.join(sorted(paths))}에서 게이트(출제 가능 여부 검사)를 통과한 결함이 아직 없다.")
        print("  먼저 `acop-dojo defects`를 실행한 뒤 다시 시도한다.")
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
    print(f"  마지막 문제다. 이 엔진에 넣은 결함을 고친다: {chosen}")
    with Sandbox(target) as sandbox:
        applied, message = sandbox.apply(patch)
        if not applied:
            print(f"  결함을 적용하지 못했다. 원인: {message}")
            return 1
        print(f"  파일: {defect.path}")
        for nodeid in entry["failed"]:
            print(f"  FAILED  {nodeid}")
        if fix is None:
            print("\n  결함을 고치는 패치를 만든 뒤 아래 명령을 실행한다.")
            print("    acop-dojo boss --fix 내패치.patch")
            print("  힌트는 제공하지 않는다. 실패한 테스트를 읽고 지켜야 할 규칙을 먼저 정리한다.")
            progress.record_stage("4", status="in_progress",
                                  detail={"transfer_correct": correct, "of": total,
                                          "defect": chosen})
            return 0

        ok, message = sandbox.apply(fix)
        if not ok:
            print(f"  패치를 적용하지 못했다. 원인: {message}")
            return 1
        print("\n  전체 테스트를 실행한다.")
        result = sandbox.pytest()
        print(f"  {result.summary}")
        remaining = defect_stage.new_failures(catalog, result.failed)
        passed = not remaining

    print(SEPARATOR)
    if passed and correct == total:
        print("  통과했다. 학습에서 다루지 않은 코드에 규칙을 적용해 결함을 고쳤다.")
    elif passed:
        print("  결함 수리는 통과했다. 틀린 전이 문제를 다시 확인한다.")
    else:
        print(f"  아직 통과하지 못했다. 남은 실패: {remaining[:4]}")
    progress.record_stage("4", status="passed" if passed else "partial",
                          detail={"transfer_correct": correct, "of": total,
                                  "defect": chosen, "oracle": "pytest"})
    # 힌트나 보기를 쓰고 맞힌 전이는 잠정으로 둔다. 전이는 혼자 찾아낸 것만 확정이다.
    progress.claim_ability("안 배운 코드로 전이", evidence=f"boss:{chosen}:{correct}/{total}",
                           confirmed=passed and correct == total and not TALLY.hints
                           and not TALLY.via_choices)
    review.schedule(defect.invariant, source=chosen)
    return 0 if passed else 1
