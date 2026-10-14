# -*- coding: utf-8 -*-
"""장소 닫힘(closure) — 휴관 · 폐쇄 · 관람 중단 문자를 버리지 않는다 `[2026-10-13 활동 팀 요청 1번]`.

전에는 「임시 휴관」 · 「오늘 폐쇄」 · 「운영 중단」이 어느 영향 종류에도 안 걸려 「기타」로 온 문자가 버려졌다 —
활동 팀이 그 장소를 막지 못했다. 「관람 전면 중단」만 「관람」 낱말 때문에 인파(crowd)로 우연히 넘어갔다.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.ports.data_sources import disaster_msg, notice_impact
from app.domains.travel_ops.ports.data_sources.notice_impact import rule_impact


@pytest.fixture(autouse=True)
def _rule_only():
    notice_impact.set_second_opinion(None)
    yield
    notice_impact.set_second_opinion(None)


@pytest.mark.parametrize("text", [
    "[국가유산청] 경복궁 관람 전면 중단",
    "[국가유산청] 경복궁 임시 휴관합니다",
    "창덕궁 오늘 폐쇄",
    "국립중앙박물관 운영 중단 안내",
    "덕수궁 출입을 통제합니다",
    "덕수궁 출입 금지",
    "섬진강 홍수에 따른 안전 점검으로 오늘 송림공원 물놀이장은 휴장함을 알려드립니다. [하동군]",
    "남산서울타워 전망대 입장 일시 중지",
    "Gyeongbokgung Palace is temporarily closed",
])
def test_place_closure_is_kept(text):
    assert rule_impact(text) == "closure"


@pytest.mark.parametrize("text, kind", [
    # 인파 — 축구장 출입 금지라도 불꽃축제 인파 때문이다(정답 세트 dev k225717)
    ("18:40분 부터 불꽃축제 관람을 위한 유동인구 급증으로 노량진 축구장 출입을 금지합니다.[동작구]", "crowd"),
    ("한강 불꽃축제 관람객이 몰려 혼잡합니다", "crowd"),
    # 도로 폐쇄는 장소 닫힘이 아니다 — 가는 길에 걸린다
    ("도로 공사로 OO로 2개 차로 폐쇄", "road"),
    ("올림픽공원 앞 도로 폐쇄, 우회 바랍니다", "road"),
    ("OO터널 양방향 폐쇄", "road"),
    # 역 폐쇄는 지하철
    ("시청역 출입구 폐쇄, 무정차 통과", "rail"),
    # 호우 문자의 하천변 · 해안가 출입금지는 장소 닫힘이 아니다 — 전국 원본 5만 건 중 372건이 처음 판에서 바뀌어 버렸다
    ("[논산시] 오늘 7시5분 우리지역 호우주의보. 저지대, 위험지역 등 출입금지. 호우피해가 없도록 안전에 유의 하시기 바랍니다.", "outdoor"),
    ("[경상남도] 하동 호우주의보 발효. 지하차도 통행자제, 농배수로 물꼬작업 금지, 산림지역, 급경사지, 하천변, 해안가 출입금지", "road"),
    ("금일 16:30부로 동천 산책로 출입을 통제하오니 주민 여러분께서는 안전사고에 유의하시기 바랍니다.[부산진구]", "road"),
    ("금일 15:50분 호우경보 발효. 많은 비가 예상되오니 하천변, 급경사지, 계곡, 노후시설물 등 출입금지 및 외출 자제. [고창군]", "outdoor"),
    ("오늘 02:00 경북지역 황사경보 발령. 문을 닫아 황사 유입을 막고, 외출 시 보건용 마스크를 쓰세요. [경북도청]", "outdoor"),
])
def test_other_kinds_keep_their_label(text, kind):
    assert rule_impact(text) == kind


@pytest.mark.parametrize("text", [
    "실종자 김OO(80세) 찾습니다 키 160cm",
    "투표소 위치는 선관위 누리집에서 확인하세요",
])
def test_life_notices_stay_out(text):
    assert rule_impact(text) is None


@pytest.mark.parametrize("text", [
    # 「창문을 닫아」 · 「밀폐장소」의 「폐장」 · 「노후시설물 등 출입금지」 · 「차량 진출입 통제」는 장소가 문을 닫는 말이 아니다
    "울산 남구 일대 가스냄새가 확산되고 있으니 창문을 닫아주시고, 안전에 유의 바랍니다. [남구]",
    "낮 최고기온 33도로 무더위 날씨가 지속. 밀폐장소 및 야외에서 작업 자제. [인천 서구청]",
    "안산시 호우, 강풍주의보 발효, 지하차도, 하천, 해안가 등 위험시설 출입을 금지하여 주시고 낙하물 안전사고에 유의하여 주시기 바랍니다.[안산시청]",
    "현 시간부로 화명생태공원 일대 차량진출입 통제가 전면 해제되었음을 알려드립니다. [북구]",
])
def test_not_a_place_closure(text):
    assert rule_impact(text) != "closure"


def test_gita_closure_message_reaches_watch():
    """재해구분 「기타」로 온 휴관 문자가 감시로 넘어간다(전에는 버려졌다). 날씨형이 아니라 모든 장소에 건다."""
    at = datetime(2026, 10, 20, 10, tzinfo=timezone(timedelta(hours=9)))
    rows = [{"kind": "기타", "step": "안전안내", "text": "[국가유산청] 경복궁 임시 휴관합니다",
             "created_at": at, "regions": ["서울특별시 전체"], "serial": 1}]
    messages, unclassified = disaster_msg.judge(rows, region="서울특별시", district=None,
                                                window_start=at - timedelta(hours=1), at=at)
    assert unclassified == []
    assert len(messages) == 1
    assert messages[0]["impact"] == "closure" and messages[0]["impact_by"] == "rule"
    assert messages[0]["weather"] is False


def test_model_may_not_answer_closure_but_rule_does():
    """2차 확인 모델의 종류 목록에는 closure 가 없다 — 장소 닫힘은 규칙이 먼저 잡으므로 모델에 묻지 않는다."""
    calls = []
    notice_impact.set_second_opinion(lambda text: calls.append(text) or "none")
    assert notice_impact.impact_detail("창덕궁 오늘 폐쇄") == {"impact": "closure", "by": "rule"}
    assert calls == []
