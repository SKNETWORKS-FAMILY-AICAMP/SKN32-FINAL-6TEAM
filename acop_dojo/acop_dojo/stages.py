"""학습 단계.

순서에 근거가 있다. 처음 보는 사람에게 곧바로 예측을 시키면 탐색 부담이 학습으로
오인된다(worked example effect). 또 예측 퀴즈는 물어본 것만 남고 안 물어본 것으로는
거의 전이되지 않는다(prequestion 메타분석, 특정 g=0.54 / 일반 g=0.04).
그래서 0단계는 해설된 완주, 1단계는 복원, 2단계는 예측 뒤 반드시 자기설명이다.
"""
from __future__ import annotations

import json
import random
import textwrap
from typing import Any

from . import ask
from . import progress
from .config import data_dir

SEPARATOR = "─" * 62


def _annotations() -> dict[str, str]:
    return json.loads((data_dir() / "annotations.json").read_text(encoding="utf-8"))


def _key(step: dict[str, Any]) -> str:
    return f"{step['path']}::{step['symbol']}"


def _short(step: dict[str, Any]) -> str:
    """대조 표에 넣을 짧은 이름. 앞을 자르면 무슨 파일인지 사라져서 뒤를 자른다."""
    label = f"{step['path'].split('/')[-1]}::{step['symbol']}"
    return label if len(label) <= 40 else label[:39] + "…"


def _wrap(text: str, indent: str = "      ") -> str:
    return textwrap.fill(text, width=78, initial_indent=indent, subsequent_indent=indent)


def _is_teachable(step: dict[str, Any]) -> bool:
    """genexpr·lambda·생성자처럼 이야기가 안 되는 프레임은 문제로 쓰지 않는다."""
    symbol = step["symbol"]
    return not ("<locals>" in symbol or symbol.endswith("__init__"))


def stage0_worked_example(trace: dict[str, Any]) -> None:
    """해설된 완주. 채점하지 않는다. 먼저 전체를 보여주는 것이 목적이다."""
    notes = _annotations()
    steps = trace["steps"]
    print(f"\n0단계 · 해설을 보며 전체 경로 따라가기   {trace['entry'].split('::')[-1]}")
    print(f"{len(steps)}개의 실행 지점에서 서로 다른 함수 {trace['summary']['unique_symbols']}개를 호출한다. "
          f"기준 코드 버전(revision): {trace.get('code_revision', '?')}")
    print(SEPARATOR)
    shown = 0
    told: set[str] = set()
    for step in steps:
        note = notes.get(_key(step))
        if not note:
            continue
        shown += 1
        repeat = f"  (연속 {step['repeat']}회)" if step.get("repeat") else ""
        print(f"\n  {step['i']:3d}  {step['path']}:{step['line']}")
        print(f"       {step['symbol']}{repeat}")
        if step.get("domain"):
            values = "  ".join(f"{k}={v}" for k, v in sorted(step["domain"].items()))
            print(f"       [{values}]")
        # 같은 함수를 다시 지날 때 해설을 통째로 반복하면 읽는 흐름이 끊긴다.
        if _key(step) in told:
            print("       (앞에서 설명한 함수다.)")
        else:
            told.add(_key(step))
            print(_wrap(note))
    flow = [step for step in steps if (step.get("domain") or {}).get("event")]
    if flow:
        print("")
        print(SEPARATOR)
        print("  상태가 바뀐 지점만 아래에 모았다.")
        for step in flow:
            domain = step["domain"]
            index = step["i"]
            event = domain["event"]
            if step["symbol"] == "next_status":
                origin = domain.get("from")
                print(f"    {index:3d}  {origin}  --{event}-->  ?   (전이표: 현재 상태와 이벤트로 다음 상태를 정하는 표)")
            else:
                version = domain.get("expected_version")
                print(f"    {index:3d}  {event}   (읽은 시점 version {version})")
        print("  version(변경 횟수)이 하나씩 오른다. 상태는 이벤트를 순서대로 반영해 얻은 결과다.")
    print(f"\n{SEPARATOR}")
    print(f"해설이 있는 지점 {shown}개를 모두 확인했다. 나머지는 같은 함수의 반복이거나 내부 표현식이다.")
    progress.record_stage("0", status="passed", detail={"scenario": trace["entry"], "shown": shown})
    progress.discover(sorted({_key(s) for s in steps}))
    progress.claim_ability(
        "실행경로 따라읽기", evidence=f"trace:{trace['entry']}", confirmed=True)


def stage1_reconstruct(trace: dict[str, Any], *, seed: int = 7, blanks: int = 5) -> None:
    """복원. 빈칸에 들어갈 함수를 같은 트레이스 안의 후보에서 고른다.

    빈 편집기에 쓰게 하지 않고 후보를 주는 것은 생성 부담을 낮추기 위해서다
    (Parsons 문제와 같은 이유). 맞힌 뒤에는 반드시 왜인지 쓰게 한다.
    """
    steps = [s for s in trace["steps"] if _is_teachable(s)]
    if len(steps) < blanks + 4:
        raise SystemExit("이 트레이스는 복원 문제로 쓰기엔 너무 짧다.")
    rng = random.Random(seed)
    pool = sorted({_key(s) for s in steps})
    # 빈칸은 아무 데나 뚫지 않는다. 해설이 붙은 지점 중, 트레이스 안에서 드물게
    # 나오는 함수를 고른다. 자주 반복되는 함수는 앞뒤만 보고도 찍히기 때문이다.
    notes = _annotations()
    frequency: dict[str, int] = {}
    for step in steps:
        frequency[_key(step)] = frequency.get(_key(step), 0) + 1
    candidates = [
        index for index in range(2, len(steps) - 1)
        if _key(steps[index]) in notes and frequency[_key(steps[index])] <= 3
    ]
    if len(candidates) < blanks:
        candidates = list(range(2, len(steps) - 1))
    targets = sorted(rng.sample(candidates, blanks))

    print(f"\n1단계 · 실행 경로 복원   빈칸 {blanks}개")
    print("각 문제에서 앞뒤 실행 흐름을 보고 빈칸에 들어갈 함수를 고른다.")
    print(SEPARATOR)
    correct = 0
    tally = ask.Tally()
    answers: list[dict[str, Any]] = []
    for position in targets:
        before, target, after = steps[position - 1], steps[position], steps[position + 1]
        right = _key(target)
        wrong = [c for c in pool if c != right]
        options = rng.sample(wrong, min(3, len(wrong))) + [right]
        rng.shuffle(options)
        print(f"\n  {before['i']:3d}  {_key(before)}")
        print(f"  {target['i']:3d}  ???")
        print(f"  {after['i']:3d}  {_key(after)}\n")
        caller = target.get("caller")
        answer = tally.add(ask.choice(
            "빈칸에 들어갈 함수를 고른다.", options, letters=True,
            answer_index=options.index(right),
            hints=[f"{ask.layer_of(right.split('::')[0])}의 함수다.",
                   (f"{caller}가 부르는 함수다." if caller
                    else f"파일은 {right.split('::')[0]}이다.")]))
        picked = answer.text
        ok = picked == right
        correct += ok
        print("  맞다." if ok else f"  아니다. 정답은 {right} 다.")
        answers.append({"position": position, "expected": right, "picked": picked, "ok": ok})

    print(f"\n{SEPARATOR}")
    print(f"{correct}/{blanks} 맞혔다.")
    explanation = tally.add(ask.free(
        "이 경로에서 상태를 바꾸는 함수가 하나뿐인 이유를 한 줄로 쓴다.",
        hints=["Case 상태를 저장하는 표(customer_cases)를 수정하는 SQL이 어디 있는지 찾는다.",
               "app/core/transition.py의 transition_case를 확인한다.",
               "그 함수 하나가 버전 대조, payload(요청 데이터) 검사, 이벤트 기록을 모두 한다."])).text
    print("\n  모범답안: customer_cases를 UPDATE 하는 곳은 transition.py 한 군데뿐이다.")
    print("  따라서 모든 상태 변경이 버전 대조, payload(요청 데이터) 검증, 이벤트 기록을 거친다.")
    print("  본인 답과 비교하고 빠진 내용이 있으면 메모한다.")
    progress.record_stage(
        "1", status="passed" if correct == blanks else "partial",
        detail={"correct": correct, "of": blanks, "answers": answers,
                "explanation": explanation, "grading": "self", **tally.detail()})
    print(f"  {tally.summary()}")
    progress.claim_ability(
        "실행경로 복원", evidence=f"stage1:{correct}/{blanks}", confirmed=correct == blanks)


def stage2_contrast(trace: dict[str, Any], *, seed: int = 7, count: int = 7) -> None:
    """대조. 먼저 예상 순서를 세우고 실측과 겹쳐 차이를 설명한다.

    맞히는 것이 목적이 아니다. 차이가 어디서 났는지 말하게 하는 것이 목적이다.
    """
    steps = [s for s in trace["steps"] if _is_teachable(s)]
    rng = random.Random(seed)
    # 같은 함수가 카드로 두 번 나오면 순서를 물어도 답이 하나로 정해지지 않는다.
    # 해설이 붙은 함수의 첫 등장만 카드로 쓴다.
    notes = _annotations()
    first: dict[str, dict[str, Any]] = {}
    for step in steps:
        key = _key(step)
        if key in notes and key not in first:
            first[key] = step
    unique = sorted(first.values(), key=lambda s: s["i"])
    if len(unique) < count:
        raise SystemExit("대조 문제로 쓸 만한 지점이 모자란다.")
    chosen = sorted(rng.sample(range(len(unique)), count))
    cards = [unique[i] for i in chosen]
    shuffled = cards[:]
    rng.shuffle(shuffled)

    print(f"\n2단계 · 예상과 실제 경로 대조   카드 {len(cards)}장")
    print("아래 함수를 실행 순서대로 나열한다. 함수 대신 번호를 쓴다. 예: 3 1 5 2 4 7 6")
    print(SEPARATOR)
    for index, step in enumerate(shuffled, start=1):
        print(f"  {index}  {_key(step)}")
    tally = ask.Tally()
    number = {id(step): index for index, step in enumerate(shuffled, start=1)}
    truth = " ".join(str(number[id(step)]) for step in cards)
    # 보기는 정답 순서 하나와, 정답을 조금씩 흐트러뜨린 순서 셋이다.
    shaken = []
    for k in range(1, len(cards)):
        swapped = cards[:]
        swapped[k - 1], swapped[k] = swapped[k], swapped[k - 1]
        shaken.append(" ".join(str(number[id(step)]) for step in swapped))
    orderings = sorted(set([truth] + rng.sample(shaken, min(3, len(shaken)))))
    reply = tally.add(ask.free(
        "실행 순서대로 번호를 한 번씩 입력한다.",
        hints=[f"가장 먼저 실행되는 것은 {number[id(cards[0])]}번이다.",
               f"가장 나중에 실행되는 것은 {number[id(cards[-1])]}번이다.",
               f"{number[id(cards[0])]}번 바로 다음에는 {number[id(cards[1])]}번이 실행된다."],
        fallback=(orderings, orderings.index(truth))))
    raw = reply.text
    try:
        order = [int(token) for token in raw.replace(",", " ").split()]
    except ValueError:
        order = []
    if sorted(order) != list(range(1, len(shuffled) + 1)):
        print("  모든 번호를 한 번씩 입력해야 한다. 입력 형식이 맞지 않아 이번에는 정답과의 대조만 보여 준다.")
        order = list(range(1, len(shuffled) + 1))

    guessed = [shuffled[i - 1] for i in order]
    print(f"\n{SEPARATOR}")
    print("  내 예상                                     실측")
    hits = 0
    for mine, real in zip(guessed, cards):
        same = _key(mine) == _key(real)
        hits += same
        mark = "=" if same else "≠"
        print(f"  {_short(mine):<40} {mark} {_short(real)}")
    print(f"\n  {hits}/{len(cards)} 자리가 맞았다.")
    explanation = tally.add(ask.free(
        "예상과 실제가 다른 자리 하나를 고른다. 예상한 순서가 틀린 이유를 쓴다.",
        hints=["라우팅(요청을 담당 모듈로 보내는 과정)은 status(현재 처리 상태)가 routing(담당 모듈로 보내는 상태)일 때만 일어난다.",
               "ContextPack(Team에게 넘기는 맥락 묶음)은 Team(작업을 수행하는 모듈)을 부르기 전에 만들어진다.",
               "상태는 Team 결과를 받은 뒤에 반영한다."])).text
    print("\n  확인할 점: 이 시나리오에서는 status(현재 처리 상태)가 routing(담당 모듈로 보내는 상태)일 때만 라우팅한다.")
    print("  ContextPack(Team에게 넘기는 맥락 묶음)은 Team을 부르기 전에 만들고, 상태는 결과를 받은 뒤 반영한다.")
    progress.record_stage(
        "2", status="passed" if hits >= len(cards) - 1 else "partial",
        detail={"hits": hits, "of": len(cards), "explanation": explanation, "grading": "self",
                **tally.detail()})
    print(f"  {tally.summary()}")
    progress.claim_ability(
        "경로 예측과 대조", evidence=f"stage2:{hits}/{len(cards)}", confirmed=False)
