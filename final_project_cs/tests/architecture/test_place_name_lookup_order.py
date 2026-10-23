# -*- coding: utf-8 -*-
"""장소를 **이름으로** 찾는 길은 모두 같은 순서를 지킨다 — 공용 별칭이 카카오보다 먼저다. `[2026-10-22 사용자 지시 · Codex 1회차 합의]`

    ① 그 고객이 고친 별칭 → ② 우리 자료 정확 일치 → ③ 공용 별칭(`team_hooks.place_aliases`) → ④ 자모 오타
    → ⑤ 관광공사 · 요식 원장 → ⑥ 카카오 → ⑦ 유료                (결정 `wiki/decisions/D-CS-021-place-name-lookup-order.md`)

☆왜: 활동 팀 별칭(「MMCA 서울」 → 국립현대미술관 서울)이 배포됐는데 활동 팀 이름 찾기만 읽고, 확인 화면 장소 검색 · 계획 읽기는
  읽지 않아 「mmca 서울」이 카카오 결과로만 나왔다(2026-10-22 x600 서버). 새 길이 카카오를 부르면서 별칭 단계를 빠뜨려도 아무도 몰랐다.

★이 시험이 보는 것: `app/` 안에서 카카오를 부르는 파일(`kakao….search(` · `_kakao_places(`)은 **아래 표에 하나도 빠짐없이** 있어야 한다.
  - `name` — 이름 찾기다. 파일 안에 별칭 단계 표시(`MARKER`)가 있어야 한다.
  - `after` — 이미 별칭을 거친 이름 찾기(`places.resolve`)가 못 찾은 **뒤에만** 부른다.
  - `kind` — 이름이 아니라 종류 · 근처(「숙소」 · 「음식점」 · 역) · 지역 기준점을 찾는다. 이유를 적는다.
  표에 없는 파일이 카카오를 부르기 시작하면 실패한다 — 그 길이 이름 찾기인지 먼저 정하고 표에 적는다.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path("app")
CALL = re.compile(r"kakao\w*\.search\(|_kakao_places\(")

#: 파일 → (분류, 그 파일에 꼭 있어야 하는 별칭 단계 표시 · 또는 이유)
KAKAO_CALLERS: dict[str, tuple[str, str]] = {
    "app/domains/travel_ops/components/intake/places.py":
        ("name", "place_aliases"),            # 계획 읽기 · 이름 고치기 · 채팅 고치기의 `resolve`
    "app/domains/travel_ops/components/intake/candidates.py":
        ("name", "_alias_places"),            # 확인 화면 장소 검색 `search`(+ 종류 · 근처 후보 채우기 `_lodging_places` · `alternatives`)
    "app/domains/travel_ops/instances/activity/place_lookup.py":
        ("name", "find_place_by_name"),       # 활동 팀 이름 찾기 — 원장 → 별칭 → (오타) → 카카오 존재 확인(`db_search/place_by_name.py`)
    "app/domains/travel_ops/components/intake/pipeline.py":
        ("after", "resolve 가 못 찾은 이름 없는 줄을 앞뒤 일정 가운데에서 거리순으로 다시 찾는다(_place_rows)"),
    "app/domains/travel_ops/components/intake/autofix.py":
        ("kind", "앞뒤 일정 근처 「음식점」 — 종류 찾기"),
    "app/domains/travel_ops/instances/dining/agent_tools.py":
        ("kind", "식당 이름 — 요식 원장(`find_place_by_name`)이 먼저다. 활동 별칭 자료의 대상이 아니다"),
    "app/tools/read_tools.py":
        ("kind", "숙소(AD5) 이름 · 지역 기준점 · 둘레 역(SW8) — 활동 별칭 자료의 대상이 아니다"),
}


def _callers() -> set[str]:
    out = set()
    for path in APP.rglob("*.py"):
        if "_backup" in path.parts:
            continue
        if CALL.search(path.read_text(encoding="utf-8")):
            out.add(path.as_posix())
    return out


def test_every_kakao_caller_is_classified():
    found = _callers()
    missing = sorted(found - set(KAKAO_CALLERS))
    assert not missing, ("카카오를 부르는 새 파일 — 이름 찾기면 공용 별칭(`team_hooks.place_aliases`)을 카카오보다 먼저 부르고, "
                         f"아니면 이유와 함께 이 표에 적는다: {missing}")
    gone = sorted(set(KAKAO_CALLERS) - found)
    assert not gone, f"더는 카카오를 부르지 않는 파일 — 표에서 뺀다: {gone}"


def test_name_lookups_carry_the_alias_step():
    for path, (kind, marker) in KAKAO_CALLERS.items():
        if kind == "name":
            assert marker in Path(path).read_text(encoding="utf-8"), f"{path}: 이름 찾기인데 별칭 단계({marker})가 없다"


def test_alias_hook_is_declared_for_the_activity_team():
    project = Path("config/project.yaml").read_text(encoding="utf-8")
    assert "place_aliases" in project, "config/project.yaml 의 활동 팀 hooks 에 place_aliases 가 없다 — 조립 검사가 실패한다"
