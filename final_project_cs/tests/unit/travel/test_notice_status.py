# -*- coding: utf-8 -*-
"""공용 「끝났나」 판정 — 지하철 공지 · 재난 문자 · 안전 정지가 같은 답을 내는지 `[2026-10-12]`."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.planning.safety import SafetyRules, classify
from app.domains.travel_ops.ports.data_sources.disaster_msg import judge, judge_released
from app.domains.travel_ops.ports.data_sources.notice_status import (
    ENDED, NO_END_SIGNAL, PARTIAL, SCHEDULED, UNSETTLED, notice_status)
from app.domains.travel_ops.ports.data_sources.subway_notice import is_nonstop_start

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 10, 12, 15, 0, tzinfo=KST)


@pytest.mark.parametrize("text", [
    "[종로구] 세종대로 집회 종료되어 버스 정상 운행합니다",
    "[서울시] 지하철 파업 철회, 정상 운행합니다",
    "[강남구] 봉은사로 사고 처리, 모든 차로 개방",
    "○○역 승강기 복구완료",
    "[서울시] 호우경보 해제",
    "언주역 인근 봉은사로 차량 통제가 완전 해제되었음을 알려드립니다.",
    "2호선 이대역 열차 정상운행",
    "6호선 이태원역 무정차 통과 해소, 정상화",
    "5호선 운행 재개",
    "집회가 끝나 정상 운행 중입니다",
])
def test_ended(text):
    status = notice_status(text)
    assert status.state == ENDED and status.basis


@pytest.mark.parametrize("text, state", [
    ("[강남구] 봉은사로 1개 차로 개방, 나머지 차로 통제 중", PARTIAL),
    ("[북구] 하상도로 통제, 그 외 구간 해제", PARTIAL),
    ("1호선 일부 구간 운행 재개", PARTIAL),
    ("1호선 서울역 무정차 통과 종료 예정", SCHEDULED),
    ("[강남구] 차량 통제 18시 해제 예정", SCHEDULED),
    ("경계경보 발령, 해제 시까지 대피하십시오", SCHEDULED),
    ("통제가 해제될 것으로 전망", SCHEDULED),
    ("4호선 혜화역 무정차 통과, 복구 작업 중", UNSETTLED),
    ("3호선 경복궁역 무정차 통과 해제 여부 확인 중", UNSETTLED),
    ("노조에 파업 철회 촉구", UNSETTLED),
    ("열차가 정상적으로 운행되지 않고 있습니다", UNSETTLED),
    ("신호 장애 미복구", UNSETTLED),
    ("5호선 광화문역 집회로 무정차 통과", NO_END_SIGNAL),
    ("오늘 열차 운행 종료", NO_END_SIGNAL),
])
def test_not_ended(text, state):
    status = notice_status(text)
    assert status.state == state and not status.ended


#: `[2026-10-12 실측]` 서울 재난문자 956건(datasets/safety/disaster_msg_seoul_2026) 중 **아직 진행 중인데 끝났다고 읽힌** 실제 문자.
#: 이 문자들이 ended 면 사건으로 세지지 않아 일정 감시에 안 간다(정전 · 붕괴 운행 중지가 조용히 사라진다).
REAL_ONGOING = [
    "금일 04:22 차량이 전신주 추돌로 수색동 314-1일대 정전발생. 복구에 장시간(10시간 이상) 소요 예상. 콘센트를 뽑고 안전사고에 유의바랍니다. [은평구]",
    "현재 갈현로33가길 일대 한전 변압기 고장으로 정전 발생. 복구에 장시간 소요 예상. 전기플러그를 뽑고 안전사고에 유의바랍니다. [은평구]",
    "서소문 고가 붕괴사고로 복구완료될 때까지 경의선 서울역~수색역 구간 전동열차 운행을 중지합니다 △1호선 및 경의중앙선(문산~용산~용문) 정상운행 [한국철도공사]",
    "서소문고가 붕괴사고로 복구완료될 때까지 경의선 서울역~수색역 구간 전동열차 운행을 중지합니다. △1호선 및 경의중앙선(문산~용산~용문) 정상운행 [한국철도공사]",
    "서울~신촌 간 서소문 고가도로 철거공사 중 붕괴로 서울~수색 구간 전동열차 운행중지 알림 △1호선 및 경의중앙선(문산~용산~용문) 정상운행 중[한국철도공사]",
    "서소문 고가 붕괴사고 수습을 위해 오늘 첫차부터 경의선 서울~수색 구간 전동열차 운행중지 △1호선 및 경의중앙선(문산~용산~용문) 정상운행 [한국철도공사]",
    "서소문 고가차도 붕괴 복구로 열차운행이 단계적 정상화중이니 이용 전 확인바랍니다. ※KTX 행신~서울/용산 구간, 강릉/중앙선 서울~청량리 구간 운행재개[코레일]",
    "금일 역삼동 602(신논현역에서 언주역 방향) 공사현장 천공기 전도 사고 복구 지연으로 교통이 혼잡하니, 주변 차량은 우회하시기 바랍니다[강남구]",
    "수락산 산불 주불진화 완료, 잔불정리 중. 완전진화를 위해 최선을 다하겠습니다.[노원구]",
    "SK허브수 오피스텔 정전 한파 대피소는 복구될때까지 구로1동 주민센터 인근에 있는 한신아파트,영화참마음아파트 경로당 2곳을 임시로 운영하겠습니다.[구로구]",
    "구로1동 sk 허브수 비상발전기 수리로 엘리베이터와 수도 공급이 되고 있습니다. 세대 전기는 현재 조치중에 있으며 복구 왼료시 재안내 드리겠습니다.[구로구]",
]

#: 같은 데이터에서 **정말 끝난** 문자 — 위 규칙을 더해도 끝남으로 남아야 한다
REAL_ENDED = [
    "오늘 17:15경 서교동 473-12 주변 발생한 정전은 19:56경 복구완료되었습니다. [마포구]",
    "16:54분 구로1동 sk 허브수 세대 정전 복구가 모두 완료 되었습니다. [구로구]",
    "금일 단전되었던 대현동 일대 925세대 전원 복구 완료되었습니다. [서대문구청]",
    "서소문 고가 철거 및 시설물 복구 작업이 완료되어 경의선 서울~문산 구간 전동열차는 현시각부로 정상운행합니다 ▲수도권 광역철도 전 구간 정상운행 중[한국철도공사]",
    "서소문 고가 철거공사 관련 지하철 시설물 점검이 완료되어 현재 2호선 열차가 정상 운행됩니다. 열차 이용에 참고하시기 바랍니다.[서울교통공사]",
    "운행 중지되었던 경의선 서울~수색 구간이 정상 운행합니다",
    "금일 15:12 영천시장(영천동 283 건물) 옥상 위 화재가 완진되었습니다. [서대문구]",
]


@pytest.mark.parametrize("text", REAL_ONGOING)
def test_real_ongoing_notices_are_not_ended(text):
    status = notice_status(text)
    assert not status.ended, (status.state, status.basis)


@pytest.mark.parametrize("text", REAL_ENDED)
def test_real_ended_notices_stay_ended(text):
    assert notice_status(text).state == ENDED


def test_ongoing_outage_reaches_watch():
    """진행 중 정전 문자는 사건으로 남아야 일정 감시가 받는다(전에는 「복구」 낱말 하나로 빠졌다)."""
    row = {**_row(REAL_ONGOING[0]), "kind": "정전"}
    anomaly, _ = judge([row], region="서울", district=None, window_start=AT, at=AT)
    assert anomaly and not judge_released([row], region="서울", district=None, window_start=AT, at=AT)


def test_full_marker_overrides_partial():
    assert notice_status("1개 차로 통제했으나 사고 처리 후 모든 차로 개방").state == ENDED


def test_subway_uses_shared_judgment():
    assert not is_nonstop_start("2호선 강남역 무정차 통과 철회")
    assert is_nonstop_start("1호선 서울역 무정차 통과 종료 예정")
    assert is_nonstop_start("4호선 혜화역 무정차 통과, 복구 작업 중")
    assert not is_nonstop_start("2호선 시청역 무정차 통과 종료되어 정상 운행")


def _row(text):
    return {"created_at": AT, "kind": "교통통제", "step": "안전안내",
            "regions": ["서울특별시 강남구 역삼동"], "text": text, "serial": 1}


@pytest.mark.parametrize("text, ended", [
    ("[종로구] 세종대로 집회 종료되어 버스 정상 운행합니다", True),
    ("[서울시] 지하철 파업 철회, 정상 운행합니다", True),
    ("[강남구] 봉은사로 모든 차로 개방", True),
    ("[강남구] 봉은사로 차량 통제 18시 해제 예정", False),
    ("[북구] 하상도로 통제, 그 외 구간 해제", False),
])
def test_disaster_msg_uses_shared_judgment(text, ended):
    anomaly, _ = judge([_row(text)], region="서울", district=None, window_start=AT, at=AT)
    released = judge_released([_row(text)], region="서울", district=None, window_start=AT, at=AT)
    assert (not anomaly) is ended
    assert bool(released) is ended
    if ended:
        assert released[0]["release_basis"]


def _rules():
    return SafetyRules(pause_enabled=True, day_steps=frozenset({"긴급재난", "위급재난"}), day_kinds=frozenset({"민방위"}),
                       trip_steps=frozenset({"위급재난"}), trip_kinds=frozenset({"민방위"}), trip_keywords=("경계경보",),
                       trip_magnitude_min=6.0, exclude_keywords=("훈련", "실제 상황이 아"))


def test_safety_pause_not_skipped_by_until_release_phrase():
    """「해제 시까지 대피」는 경보가 살아 있다는 말이다 — 전에는 「해제」 낱말 하나로 정지에서 빠졌다."""
    alert = {"category": "disaster_msg", "kind": "민방위", "step": "위급재난", "text": "경계경보 발령, 해제 시까지 대피하십시오", "created_at": AT.isoformat()}
    released = {**alert, "text": "경계경보 해제"}
    assert classify([alert], _rules()) is not None
    assert classify([released], _rules()) is None
