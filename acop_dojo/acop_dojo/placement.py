"""사전진단.

전원을 0단계부터 시작시키면 안 된다. 초보자에게는 해설된 완주가 유리하지만
(worked example effect), 이미 아는 사람에게 같은 것을 다시 보여주면 지루하고
학습도 안 된다. 숙련도가 오르면 발판을 걷어내야 한다는 것이 여러 연구의 결론이다.

자기 보고로 묻지 않는다. 저장소 실측에서 뽑은 문제로 잰다 — "나 좀 안다"와
"실제로 아는 것"은 다르다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import defect_stage
from . import defects as defects_mod
from . import progress
from . import tracks as tracks_mod

SEPARATOR = "─" * 62

#: 점수 → 어디부터 시작할지
ENTRY = {
    0: ("0", "해설된 완주부터. 먼저 전체가 도는 것을 본다."),
    1: ("0", "해설된 완주부터. 아는 것이 있지만 전체 그림을 한 번 보고 가는 편이 낫다."),
    2: ("1", "복원부터. 완주 해설은 건너뛰고 빈칸을 채우며 확인한다."),
    3: ("2", "대조부터. 예상 경로를 먼저 그리고 실측과 겹친다."),
}


def _first_symbols(trace: dict[str, Any], count: int = 4) -> list[str]:
    seen: list[str] = []
    for step in trace["steps"]:
        if "<locals>" in step["symbol"]:
            continue
        label = f"{step['path'].split('/')[-1]}::{step['symbol']}"
        if label not in seen:
            seen.append(label)
        if len(seen) >= count:
            break
    return seen


def run(track_id: str, trace: dict[str, Any]) -> int:
    track = tracks_mod.get(track_id)
    print("")
    print(f"사전진단 · {track.title}")
    print("세 문제다. 맞히려고 하지 말고 지금 아는 만큼만 답한다.")
    print(SEPARATOR)
    score = 0

    print("")
    print("  1. 이 저장소에서 Case 의 상태를 바꾸는 함수는 하나뿐이다. 이름은?")
    answer = input("  > ").strip().lower()
    ok = "transition_case" in answer.replace(" ", "")
    score += ok
    print(f"  {'맞다.' if ok else '아니다.'}  transition_case (app/core/transition.py)")

    options = _first_symbols(trace)
    print("")
    print("  2. 이 트랙의 대표 시나리오에서 가장 먼저 불리는 것은? 번호로 답한다.")
    for index, option in enumerate(options, start=1):
        print(f"    {index}  {option}")
    raw = input("  > ").strip()
    picked = options[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(options) else ""
    ok = picked == options[0]
    score += ok
    print(f"  {'맞다.' if ok else '아니다.'}  {options[0]}")

    catalog = defects_mod.load_catalog()
    mine = [d for d in defect_stage.playable(catalog)
            if tracks_mod.owns(track, defects_mod.by_id(d).path)]
    if mine:
        chosen = mine[0]
        entry = catalog["entries"][chosen]
        print("")
        print("  3. 규칙 하나를 깨뜨렸더니 이 테스트가 깨졌다. 어느 파일이겠나?")
        for nodeid in entry["failed"][:3]:
            print(f"      FAILED  {nodeid}")
        guess = input("  > ").strip()
        actual = defects_mod.by_id(chosen).path
        ok = bool(guess) and guess.lower() in actual.lower()
        score += ok
        print(f"  {'맞다.' if ok else '아니다.'}  {actual}")
    else:
        print("")
        print("  3. 이 트랙에 낼 결함이 아직 없어 두 문제로만 잰다.")

    stage, advice = ENTRY[min(score, 3)]
    print("")
    print(SEPARATOR)
    print(f"  {score}점. {advice}")
    print(f"  시작:  python dojo.py learn {stage} --track {track_id}")
    data = progress.load()
    data.setdefault("placement", {})[track_id] = {"score": score, "entry_stage": stage}
    progress.save(data)
    print("")
    print("  이 결과는 권고일 뿐이다. 어느 단계든 직접 열 수 있다.")
    return 0
