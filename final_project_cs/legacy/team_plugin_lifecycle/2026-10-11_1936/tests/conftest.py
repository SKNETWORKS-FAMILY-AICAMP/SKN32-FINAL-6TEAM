# -*- coding: utf-8 -*-
"""시험 공통 설정 — 로컬 `.env` 가 시험 결과를 바꾸지 않게 한다.

☆`[2026-09-29 자료 폴더 통일]` 이동 자료가 저장소 안(`datasets/mobility/processed`)에 들어오고 로컬 `.env` 에
  `ACOP_MOBILITY_DATA_DIR` 를 켜 두자, 그 값을 읽는 서버 조립(`build_registry`)을 거치는 모든 시험이 이동 계산기를 켰다 —
  일정 짜기가 어림값이 아니라 실제 시간표로 짜여 이동 길이·출발 문구가 달라지고, 시험 5개가 자료를 켠 컴퓨터에서만 실패했다.
  CI 에는 `.env` 가 없어 꺼져 있으니 **컴퓨터마다 결과가 다른** 시험이었다.

기본은 **꺼짐**이다. 계산기를 켜야 하는 시험은 스스로 켠다(`wiring.configure(...)` — 작은 가공 자료나 실제 시간표로).
셸에서 `ACOP_MOBILITY_DATA_DIR` 를 직접 내보내면 그 값이 이긴다(setdefault) — 켠 채로 전체를 돌려 보고 싶을 때.
"""
import os

os.environ.setdefault("ACOP_MOBILITY_DATA_DIR", "")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _wire_domain_teams():
    """시험도 **조립된 상태**로 돈다 — 팀이 자기 계산을 부품의 끼움 자리에 꽂은 상태.

    ★`[2026-10-06]` D-CS-013. 부품은 팀 내부를 직접 부르지 않고 `components/team_hooks/` 를 본다.
      운영은 조립(`app/composition.py` `wire_domain_teams()`)이 꽂지만, 단위 시험은 조립을 거치지
      않고 부품을 바로 부른다 — 꽂지 않으면 이동 계산기도 요식 판정도 없는 상태가 되어 시험이
      운영과 다른 것을 재게 된다. 그래서 여기서 매번 꽂는다.
      팀이 **없는** 상태를 재는 시험은 그 자리의 `clear()` 를 직접 부른다.
    """
    from app.composition import wire_domain_teams

    wire_domain_teams()
    yield


@pytest.fixture(autouse=True)
def _isolate_mobility_engine_state():
    """시험마다 이동 계산기 상태(자료 폴더 출처·켜짐/꺼짐)를 **처음 상태로** 초기화한다.

    ☆`[2026-10-01 이동 담당 보고서 #54]` 서버를 조립하는 것(`build_registry`)은 설정이 비어 있으면 계산기를 「꺼짐」으로 두는데
      (`paths.disable()`), 이 저장소는 시험을 **모으는 단계에서** 이미 앱을 만든다(`app = create_app()` 이 import 때 돈다). 그래서
      꺼짐 상태가 첫 시험이 돌기 전부터 깔려 있었고, 같은 실행 안에서 뒤에 도는 이동 시험이 「꺼져 있다」 오류 → 자료 없음 건너뜀이 됐다
      (CI 는 계약 시험이 단위 시험보다 먼저 돌아 저장소에 자료가 있어도 이동 시험이 건너뛰어졌다).
      「시험 전 상태로 되돌리기」로는 그 깔린 꺼짐을 못 치우므로 **시험 전후에 처음 상태로 초기화**한다. 계산기를 부르는 앱 코드는
      켜짐이 아니면 어림값으로 가므로(`leg_planner`·`team_result` 가 None) 처음 상태와 꺼짐은 같게 동작한다. 이동 시험은 명령줄
      관례(저장소 안 자료 폴더)로 자기 계산기를 올리고, 켜야 하는 시험은 스스로 켠다. 설정 기본값·CI 환경변수는 건드리지 않는다.
    """
    from app.domains.travel_ops.instances.mobility import wiring
    from app.domains.travel_ops.instances.mobility.engine import paths

    def reset():
        paths._layout(paths.UNSET_DIR, "unset")
        wiring._STATE.clear()
        wiring._STATE.update(mode="unconfigured", kw=None, datacheck=None)

    reset()
    yield
    reset()
