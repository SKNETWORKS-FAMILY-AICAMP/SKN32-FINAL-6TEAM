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
# ★`[2026-10-16]` 구글 호텔(SerpApi — 하루 8 · 월 250회)을 시험이 쓰지 않게 키를 비운다. 확인 화면의 숙소 후보(숙소 팀)가 이 키가 있을 때만 바깥에 나간다.
#   숙소 시험은 메모리 객체를 넣어 키 없이 돈다. 셸에서 직접 내보내면 그 값이 이긴다(setdefault).
os.environ.setdefault("ACOP_SERPAPI_API_KEY", "")


import pytest  # noqa: E402


#: 항로 지킴이 기본값(꺼짐 — `[2026-10-23 사용자 지시]`) 자체를 재거나 스위치를 직접 켜고 끄는 시험 파일 — 이 파일들은 켜짐으로 고정하지 않는다
GUARDIAN_DEFAULT_FILES = (
    "tests/unit/travel/test_guardian_switch.py",
    "tests/e2e/test_guardian_admin_switch.py",
    "tests/e2e/test_trip_risk_panel_admin_switch.py",
    "tests/unit/travel/test_classification_execution_plan.py",
)


@pytest.fixture(autouse=True)
def _guardian_switch_on_for_feature_tests(request, monkeypatch):
    """항로 지킴이 기능(자동 일정 변경 · 감시 · 알림)을 재는 시험은 운영 스위치가 **켜진** 상태로 돈다.

    ☆`[2026-10-23 사용자 지시]` 기본값이 켜짐 → 꺼짐으로 바뀌었다. 이 기능을 쓰는 시험은 전부 켜짐을 가정하고 쓰였으므로 공용으로 켠다.
      기본값 자체를 재는 파일(`GUARDIAN_DEFAULT_FILES`)만 고정하지 않는다."""
    path = str(request.node.fspath).replace("\\", "/")
    if path.endswith(GUARDIAN_DEFAULT_FILES):
        return
    monkeypatch.setattr("app.core.settings.guardian_enabled", lambda: True)
    monkeypatch.setattr("app.domains.travel_ops.components.settings_hook.guardian_enabled", lambda tenant_id: True)


#: 「모든 일정이 오늘 이전」 등록 거절(`itinerary_checks.all_dates_before_today`)이 쓰는 **시험의 오늘**.
#: ★`[2026-10-26]` 시험 대본·접수 fixture 는 날짜가 고정돼 있다(대본 2026-09-23 등, 가장 이른 날 2026-08-17).
#:   가드가 실제 시계를 읽으면 그 날이 지나는 순간 실행 날짜만으로 시험이 깨진다 — 날짜가 지난 대본은 지금 이미 422, 오늘·내일 날짜의
#:   fixture 는 다음 날부터 422. 그래서 가드의 시계만 모든 고정 날짜보다 앞선 하루로 고정한다(제품 가드는 그대로).
#:   실제 오늘보다 앞선 날이라 상대 날짜(어제 · 내일) fixture 의 판정도 바꾸지 않는다.
ALL_PAST_GUARD_TEST_TODAY = (2026, 8, 1)


@pytest.fixture(autouse=True)
def _pin_all_past_guard_today(monkeypatch):
    """가드 자체를 재는 시험은 이 고정 위에 자기 시계(`monkeypatch.setattr(checks, "datetime", ...)` · `now=`)를 다시 넣는다."""
    from datetime import datetime

    from app.domains.travel_ops.components.itinerary import itinerary_checks as checks

    pinned = datetime(*ALL_PAST_GUARD_TEST_TODAY, 12, tzinfo=checks.KST)

    class _PinnedToday(datetime):
        @classmethod
        def now(cls, tz=None):
            return pinned.astimezone(tz) if tz else pinned.replace(tzinfo=None)

    monkeypatch.setattr(checks, "datetime", _PinnedToday)


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
    from app.core.service_bindings import standalone_services

    wire_domain_teams()
    with standalone_services():
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


# ★DB(PostgreSQL)가 있어야 도는 시험 파일 — develop 빠른 단계는 `-m "not live and not db"` 로 건너뛰고
#   DB 가 있는 main 전체 관문이 돌린다. `[2026-10-22]` DB 없이 돌려 실제로 연결 시간 초과가 난 파일만 올렸다.
#   목록에 없는 파일이 DB 를 쓰기 시작하면 빠른 단계가 DB 없이 깨지므로, 그때 여기에 더한다.
DB_TEST_FILES = (
    "tests/contract/test_active_prompts_are_the_deployed_set.py",
    "tests/contract/test_consumer_idempotency_contract.py",
    "tests/security/test_admin_json_gateway.py",
    "tests/security/test_pii_redaction_runtime.py",
    "tests/security/test_query_scope.py",
    "tests/unit/infrastructure/test_graph_v7_axes.py",
    "tests/unit/travel/test_cache_only_sources.py",
    "tests/unit/travel/test_feedback.py",
    "tests/unit/travel/test_planner_badges.py",
    "tests/unit/travel/test_seoul_bus_shared_cache_v1.py",
    "tests/unit/travel/test_shared_source_cache.py",
    "tests/unit/voc/test_feedback_runtime.py",
)


# ★파일 하나가 몇 초씩 걸리는 시험(자식 프로세스 · 실제 대기 · 저장소 전체 훑기) — 빠른 단계는
#   `-m "not slow"` 로 건너뛰고 main 전체 관문이 돌린다. `[2026-10-22]` 시험 시간을 재어 파일당 5초 넘는 것만 올렸다.
SLOW_TEST_FILES = (
    "tests/unit/travel/mobility/test_review_fixes_runtime.py",  # 자식 파이썬 프로세스를 띄운다
    "tests/unit/infrastructure/test_llm_failover.py",  # 재시도 대기(sleep)를 실제로 기다린다
    "tests/contract/test_retired_domain_assets.py",  # 저장소 전체를 훑는다
    "tests/unit/travel/test_plugin_read_boundaries.py",  # 자식 프로세스를 띄운다
    "tests/unit/travel/mobility/test_check_scripts.py",  # 검사 스크립트를 자식 프로세스로 돌린다
    "tests/unit/travel/test_trip_api_plugin_boundaries.py",  # 앱 전체를 가져온다
)


def pytest_collection_modifyitems(items):
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if path.endswith(DB_TEST_FILES):
            item.add_marker(pytest.mark.db)
        if path.endswith(SLOW_TEST_FILES):
            item.add_marker(pytest.mark.slow)
