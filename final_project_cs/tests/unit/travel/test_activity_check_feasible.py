# -*- coding: utf-8 -*-
"""activity.check_feasible — 운영시간·재난문자 판정 검증.

★`test_activity_input_validation.py`가 예약·정책·장소 누락과 과거 예약을,
  `test_activity_weather*.py`가 기상을 커버한다. 이 파일은 그 나머지 두 축을 담당한다.

① 운영시간(`_weekday_closure_match`)
   - TourAPI 원문은 boolean 으로 해석하지 않는다(근거·안내문으로만 전한다).
   - 예외: "매주 <요일> 휴무" 패턴이 요청 요일과 일치하면 feasible=False.
   - 예외 조건(공휴일 등)은 반영하지 않고 안내문에 반드시 캐비앗을 남긴다.

② 재난문자(`_disaster_blocks`)
   - 날씨와 달리 실내외 구분 없이 항상 조회한다.
   - 위급재난 등급만 feasible 을 바꾼다. 나머지는 근거로만 전한다.
   - 지역·주제 관련성은 확인하지 않고 그 사실을 안내문에 반드시 남긴다.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam

from .helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
UTC = timezone.utc
KST = timezone(timedelta(hours=9))


def _upcoming(when: datetime) -> datetime:
    """고정 시각을 **요일·시각은 그대로 둔 채** 주 단위로 미래로 민다.

    ★`[2026-09-26]` 날짜를 그대로 박아 두면 그날이 지나는 순간 `remaining < 0`
      (「이미 시작됨」)으로 먼저 끝나 운영시간·재난문자 판정까지 가지 못한다 —
      실제로 2026-09-22 고정값 테스트 6건이 이렇게 깨졌다. 이 파일의 테스트가
      보는 것은 **요일**(화요일 휴무 대조)이라, 주 단위로만 옮기면 의미가 유지된다.
      취소 기한(24시간)과도 안 겹치게 최소 이틀 뒤로 잡는다.
    """
    floor = datetime.now(UTC) + timedelta(days=2)
    while when < floor:
        when += timedelta(weeks=1)
    return when


#: 토요일 — 기본 "화요일" 휴무 텍스트와 절대 안 겹친다(flaky 방지).
DEFAULT_STARTS_AT = _upcoming(datetime(2026, 10, 3, 15, tzinfo=UTC))


def _task():
    context = pack("activity", scope=["activity"])
    return task("activity", "activity.check_feasible", context, ALLOWED)


def _operating(**overrides):
    base = {"content_id": "126508",
            "usetime_text": "09:00~18:00(입장마감 17:00)",
            "restdate_text": "매주 화요일 휴무. 단 공휴일과 겹치면 개방",
            "parsed": False, "answers_open_at_slot": False,
            "source": "tour_api", "confirmed_at": "2026-09-20T12:00:00+00:00"}
    base.update(overrides)
    return base


def _values(*, operating=None, disaster=None, starts_at=DEFAULT_STARTS_AT,
            party=2, capacity=4):
    place: dict = {"place_id": "p1", "weather_sensitive": False,
                   "latitude": 37.5796, "longitude": 126.9770}
    if operating is not None:
        place["operating"] = operating
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": starts_at, "party_size": party,
                         "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": None,
        "read.disaster": disaster,
    }


# ══════════════════════════════════════════════════════════════════
# ① 운영시간
# ══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_operating_text_appears_in_answer_and_evidence():
    """운영시간 원문이 있으면 안내 문구·근거·decisions 에 실린다."""
    result = await ActivityTeam(
        FakeTools(_values(operating=_operating()))).execute(_task())

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is True
    assert "09:00~18:00" in result.answer
    assert "매주 화요일 휴무" in result.answer
    assert "자동 해석하지 않았습니다" in result.answer
    assert any("자동 판정에 쓰지 않았다" in w for w in result.warnings)
    assert result.decisions[0]["operating"]["usetime_text"] == "09:00~18:00(입장마감 17:00)"
    evidence_ids = [e.evidence_id for e in result.evidence]
    assert "tool:activity:read.place.operating" in evidence_ids


@pytest.mark.asyncio
async def test_non_weekday_pattern_does_not_flip_feasibility():
    """읽지 못한 휴무 원문은 feasible 을 바꾸지 않는다 — 다만 「휴무 아님」으로 **확정하지도 않는다**.

    ★`[2026-10-06]` 전에는 `weekday_match is False`(휴무 아님)를 기대했다. 「오늘은 임시휴무입니다」를 읽고
      「아님」으로 확정하는 것은 틀린 답일 수 있다 — 이제 모름(`None`)이고 답변이 그 사실을 밝힌다
      (결함 2026-10-06_1610).
    """
    closed = _operating(usetime_text="", restdate_text="오늘은 임시휴무입니다")
    result = await ActivityTeam(
        FakeTools(_values(operating=closed))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["operating"]["weekday_match"] is None
    assert "확정하지 않았습니다" in result.answer
    assert "불가" not in result.answer
    assert "임시휴무" in result.answer


@pytest.mark.asyncio
async def test_no_operating_info_omits_tourapi_mention():
    """operating 자체가 없으면 TourAPI 언급 없이 성립 판정만 내린다."""
    result = await ActivityTeam(
        FakeTools(_values(operating=None))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert "TourAPI" not in result.answer
    assert "operating" not in result.decisions[0]
    evidence_ids = [e.evidence_id for e in result.evidence]
    assert "tool:activity:read.place.operating" not in evidence_ids


@pytest.mark.asyncio
async def test_operating_with_empty_fields_does_not_claim_checked():
    """소스가 응답했지만 쓸 만한 필드가 없으면 '확인했다'고 말하지 않는다."""
    empty = _operating(usetime_text=None, restdate_text=None)
    result = await ActivityTeam(
        FakeTools(_values(operating=empty))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert "정보를 받지 못해" in result.answer
    assert result.decisions[0]["operating"]["weekday_match"] is None


@pytest.mark.asyncio
async def test_non_closure_weekday_stays_feasible():
    """경복궁 · 토요일 — 정기휴무 요일(화)이 아니므로 원문은 근거로만."""
    operating = _operating(usetime_text="09:00~18:00",
                           restdate_text="매주 화요일 휴무")
    vals = _values(operating=operating,
                   starts_at=_upcoming(datetime(2026, 10, 3, 15, tzinfo=KST)))
    vals["read.place"]["name"] = "경복궁"

    result = await ActivityTeam(FakeTools(vals)).execute(_task())

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["operating"]["weekday_match"] is False


@pytest.mark.asyncio
async def test_closure_weekday_marks_infeasible_with_caveat():
    """경복궁 · 화요일 — 정기휴무 요일 일치 → feasible=False + 캐비앗."""
    operating = _operating(usetime_text="09:00~18:00",
                           restdate_text="매주 화요일 휴무")
    vals = _values(operating=operating,
                   starts_at=_upcoming(datetime(2026, 9, 22, 15, tzinfo=KST)))
    vals["read.place"]["name"] = "경복궁"

    result = await ActivityTeam(FakeTools(vals)).execute(_task())

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["operating"]["weekday_match"] is True
    assert "정기휴무 요일" in result.answer
    assert "공휴일과 겹치는 경우" in result.answer   # 예외 미반영 캐비앗
    assert any("예외 조건" in w for w in result.warnings)


# ══════════════════════════════════════════════════════════════════
# ② 재난문자
# ══════════════════════════════════════════════════════════════════

DISASTER_EMPTY = {
    "confirmed_at": "2026-09-21T10:00:00+00:00",
    "for_region": [],
    "source": "data_go_kr",
}

DISASTER_NON_CRITICAL = {
    "confirmed_at": "2026-09-21T10:00:00+00:00",
    "for_region": [
        {"serial": "1001", "step": "안전안내", "kind": "기타재난",
         "regions": ["서울특별시 종로구"], "text": "[안전안내] 기상 특보 예상. 외출 시 주의하세요.",
         "weather": False},
    ],
    "source": "data_go_kr",
}

DISASTER_CRITICAL = {
    "confirmed_at": "2026-09-21T10:00:00+00:00",
    "for_region": [
        {"serial": "2001", "step": "위급재난", "kind": "홍수",
         "regions": ["서울특별시 종로구"], "text": "[위급재난] 종로구 일대 홍수 위험. 즉시 대피하세요.",
         "weather": True},
    ],
    "source": "data_go_kr",
}


@pytest.mark.asyncio
async def test_disaster_structure_invariants():
    """재난문자가 있을 때 outcome·decisions·answer 구조 불변량."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=DISASTER_NON_CRITICAL))).execute(_task())

    assert result.outcome == "completed"
    assert result.decisions
    assert "feasible" in result.decisions[0]
    assert "disaster" in result.decisions[0]
    assert result.answer


@pytest.mark.asyncio
async def test_empty_messages_note():
    """재난문자 목록이 비어 있으면 '없습니다' 안내가 answer 에 실린다."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=DISASTER_EMPTY))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["disaster"]["blocks"] is False
    assert "확인 범위 내 재난문자는 없습니다" in result.answer


@pytest.mark.asyncio
async def test_non_critical_grade_does_not_block():
    """위급재난 아닌 등급(안전안내)은 feasible 을 바꾸지 않는다."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=DISASTER_NON_CRITICAL))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["disaster"]["blocks"] is False
    assert f"재난문자 {len(DISASTER_NON_CRITICAL['for_region'])}건" in result.answer
    assert "판정에 영향을 주는 등급은 아닙니다" in result.answer
    assert not any("지역·주제 관련성" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_critical_disaster_blocks_feasible():
    """위급재난은 feasible=False·blocks=True 이고 '위급재난'이 answer 에 실린다."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=DISASTER_CRITICAL))).execute(_task())

    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["disaster"]["blocks"] is True
    assert "위급재난" in result.answer


@pytest.mark.asyncio
async def test_critical_disaster_blocks_regardless_of_kind_or_content():
    """★`[결정 2026-10-08]` 위급재난은 유형 · 내용과 관계없이 막는다 — 그 사실을 경고로 밝힌다."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=DISASTER_CRITICAL))).execute(_task())

    assert result.decisions[0]["disaster"]["blocks"] is True
    assert "위급재난 문자(" in result.answer and "성립하지 않습니다" in result.answer
    assert any("유형·내용과 관계없이 막는다" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_infeasible_answer_does_not_open_with_feasible():
    """★`[2026-10-08]` 성립하지 않으면 답이 「확인한 범위에서는 성립합니다」로 시작하지 않는다.
    예전에는 점검 전에 그 문장을 먼저 넣어 「성립합니다 … 성립하지 않습니다」로 어긋났다."""
    blocked = await ActivityTeam(FakeTools(_values(disaster=DISASTER_CRITICAL))).execute(_task())
    assert blocked.decisions[0]["feasible"] is False
    assert "성립합니다(" not in blocked.answer and blocked.answer.startswith("시작까지 ")
    fine = await ActivityTeam(FakeTools(_values(disaster=DISASTER_NON_CRITICAL))).execute(_task())
    assert fine.decisions[0]["feasible"] is True
    assert fine.answer.startswith("확인한 범위에서는 성립합니다(")


@pytest.mark.asyncio
async def test_disaster_decision_fields_all_present():
    """decisions.disaster 에 messages·blocks·confirmed_at·source 가 모두 있다."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=DISASTER_NON_CRITICAL))).execute(_task())
    dis = result.decisions[0].get("disaster", {})
    for field in ("messages", "blocks", "confirmed_at", "source"):
        assert field in dis, f"decisions.disaster.{field} 없음"


@pytest.mark.asyncio
async def test_disaster_and_weather_are_read_at_the_booking_time():
    """★`[2026-10-07]` 시각은 `at` 으로 넘긴다 — 도구(`read_tools.disaster`·`weather`)가 읽는 이름이다.
    예전에는 `starts_at` 으로 넘겨 도구가 버렸고, 일정 시각이 아니라 **지금** 기준으로 봤다."""
    values = _values(disaster=DISASTER_NON_CRITICAL)
    values["read.place"] = {**values["read.place"], "weather_sensitive": True}   # 실외라 기상도 읽는다
    tools = FakeTools(values)
    await ActivityTeam(tools).execute(_task())
    args = {name: arguments for name, arguments in tools.calls}
    for name in ("read.disaster", "read.weather"):
        assert args[name].get("at") == DEFAULT_STARTS_AT, name
        assert "starts_at" not in args[name], name


@pytest.mark.asyncio
async def test_disaster_lookup_carries_the_place_address():
    """★`[2026-10-07]` 장소 주소(CSV `addr1`)를 넘겨 도구가 주소의 자치구로 거르게 한다 — 좌표 상자는 자주 틀린다."""
    values = _values(disaster=DISASTER_NON_CRITICAL)
    values["read.place"] = {**values["read.place"], "source_content_id": "126508"}   # 경복궁
    tools = FakeTools(values)
    await ActivityTeam(tools).execute(_task())
    args = dict(tools.calls)["read.disaster"]
    assert args["address"].startswith("서울특별시 종로구")


@pytest.mark.asyncio
async def test_disaster_evidence_recorded():
    """read.disaster 결과가 evidence 에 기록된다."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=DISASTER_NON_CRITICAL))).execute(_task())
    evidence_ids = [e.evidence_id for e in result.evidence]
    assert any("read.disaster" in eid for eid in evidence_ids)


@pytest.mark.asyncio
async def test_disaster_none_omits_decision_key():
    """read.disaster 가 None 이면 decisions 에 disaster 키가 없다."""
    result = await ActivityTeam(
        FakeTools(_values(disaster=None))).execute(_task())

    assert "disaster" not in result.decisions[0]


# ══════════════════════════════════════════════════════════════════
# ③ 고객 일정 시나리오 — customer_travel.json
# ══════════════════════════════════════════════════════════════════
#
# JSON 이 바뀌어도(일정 항목 추가·변경·단건만 존재) 이 절이 유효하도록
# 두 단계로 구성한다.
#
#   A. 불변량 — 모든 활동에 대해 구조를 검사 (parametrize, 자동 확장)
#   B. 시나리오 — 특정 act_id 가 있을 때만 실행 (skipif)

_ITINERARY_FILE = Path(__file__).parent / "customer_travel.json"
CUSTOMER_ITINERARY: list[dict] = (
    json.loads(_ITINERARY_FILE.read_text(encoding="utf-8"))["itinerary"]
    if _ITINERARY_FILE.exists() else []
)


def _activity(act_id: str) -> dict | None:
    """고객 일정에서 id 로 활동 하나를 꺼낸다. 없으면 None."""
    return next((a for a in CUSTOMER_ITINERARY if a["id"] == act_id), None)


def _vals_from(act: dict, *, operating=None, disaster=None,
               party: int = 2, capacity: int = 4) -> dict:
    """customer_travel.json 활동 항목 하나 → FakeTools 입력값.

    JSON 이 바뀌면 place·예약 정보(name·lat·lng·starts_at)가 자동 반영된다.
    operating·disaster 는 테스트별로 주입한다. ★JSON 시각은 요일을 유지한 채
    미래로 민다(`_upcoming`) — JSON 날짜가 지나도 테스트가 안 깨진다.
    """
    starts_at = _upcoming(datetime.fromisoformat(act["time"]))
    place: dict = {
        "place_id": act["id"],
        "name": act["name"],
        "weather_sensitive": False,
        "latitude": act.get("lat"),
        "longitude": act.get("lng"),
    }
    if operating is not None:
        place["operating"] = operating
    return {
        "read.booking": {
            "booking_id": act["id"],
            "place_id": act["id"],
            "starts_at": starts_at,
            "party_size": party,
            "capacity": capacity,
        },
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": None,
        "read.disaster": disaster,
    }


#: 비위급(안전안내) — feasible 을 바꾸지 않는다
CUSTOMER_SAFE_DISASTER = {
    "confirmed_at": "2026-09-22T01:00:00+00:00",
    "for_region": [
        {"serial": "8001", "step": "안전안내", "kind": "기상특보",
         "regions": ["서울특별시 성동구"], "text": "[안전안내] 오전 중 강풍 특보. 외출 시 주의하세요.",
         "weather": True},
    ],
    "source": "data_go_kr",
}

#: 위급재난 — feasible=False 로 만든다
CUSTOMER_CRITICAL_DISASTER = {
    "confirmed_at": "2026-09-22T10:30:00+00:00",
    "for_region": [
        {"serial": "9001", "step": "위급재난", "kind": "홍수",
         "regions": ["서울특별시 중구"], "text": "[위급재난] 중구 일대 침수 위험. 즉시 대피하세요.",
         "weather": True},
    ],
    "source": "data_go_kr",
}


# ── A. 불변량 — 모든 활동에 대해 ─────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("act", CUSTOMER_ITINERARY,
                          ids=[a["id"] for a in CUSTOMER_ITINERARY])
async def test_customer_all_activities_structure_invariants(act):
    """JSON 의 모든 활동 항목 — completed + feasible 키 구조 불변량."""
    result = await ActivityTeam(FakeTools(_vals_from(act))).execute(_task())

    assert result.outcome == "completed"
    assert "feasible" in result.decisions[0]
    assert result.answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "act",
    [a for a in CUSTOMER_ITINERARY if a.get("tour_api_content_id")],
    ids=[a["id"] for a in CUSTOMER_ITINERARY if a.get("tour_api_content_id")],
)
async def test_customer_with_tourapi_content_id_operating_key_present(act):
    """tour_api_content_id 있는 활동 — operating 주입 시 decisions·evidence 에 기록."""
    operating = _operating(content_id=act["tour_api_content_id"])
    result = await ActivityTeam(
        FakeTools(_vals_from(act, operating=operating))).execute(_task())

    assert result.outcome == "completed"
    assert "operating" in result.decisions[0]
    assert any("read.place.operating" in e.evidence_id for e in result.evidence)


# ── B. 시나리오 — act_id 가 JSON 에 있을 때만 실행 ─────────────────

@pytest.mark.asyncio
@pytest.mark.skipif(_activity("act_001") is None, reason="act_001 이 일정에 없음")
async def test_customer_act001_no_tourapi_feasible():
    """act_001 — TourAPI 없음·재난없음 → TourAPI 언급 없이 성립."""
    result = await ActivityTeam(
        FakeTools(_vals_from(_activity("act_001")))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert "TourAPI" not in result.answer
    assert "operating" not in result.decisions[0]
    assert "disaster" not in result.decisions[0]


@pytest.mark.asyncio
@pytest.mark.skipif(_activity("act_002") is None, reason="act_002 이 일정에 없음")
async def test_customer_act002_noncritical_disaster_stays_feasible():
    """act_002 — TourAPI 없음 + 안전안내(비위급) → feasible, 등급 안내만."""
    result = await ActivityTeam(
        FakeTools(_vals_from(_activity("act_002"),
                             disaster=CUSTOMER_SAFE_DISASTER))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["disaster"]["blocks"] is False
    assert "안전안내" in result.answer
    assert "판정에 영향을 주는 등급은 아닙니다" in result.answer
    assert not any("지역·주제 관련성" in w for w in result.warnings)


@pytest.mark.asyncio
@pytest.mark.skipif(_activity("act_003") is None, reason="act_003 이 일정에 없음")
async def test_customer_act003_gyeongbokgung_tuesday_infeasible():
    """act_003 — JSON 의 실제 시각(화요일) + 화요일 휴무 → feasible=False + 캐비앗."""
    act = _activity("act_003")
    operating = _operating(
        content_id=act.get("tour_api_content_id") or "126508",
        usetime_text="09:00~18:00(입장마감 17:00)",
        restdate_text="매주 화요일 휴무. 단 공휴일과 겹치면 개방",
    )
    result = await ActivityTeam(
        FakeTools(_vals_from(act, operating=operating))).execute(_task())

    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["operating"]["weekday_match"] is True
    assert "정기휴무 요일" in result.answer
    assert "공휴일과 겹치는 경우" in result.answer
    assert any("예외 조건" in w for w in result.warnings)


@pytest.mark.asyncio
@pytest.mark.skipif(_activity("act_004") is None, reason="act_004 이 일정에 없음")
async def test_customer_act004_critical_disaster_blocks():
    """act_004 — 위급재난 발령 → feasible=False. 유형 · 내용과 관계없이 막는다(2026-10-08)."""
    result = await ActivityTeam(
        FakeTools(_vals_from(_activity("act_004"),
                             disaster=CUSTOMER_CRITICAL_DISASTER))).execute(_task())

    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["disaster"]["blocks"] is True
    assert "위급재난" in result.answer
    assert any("유형·내용과 관계없이 막는다" in w for w in result.warnings)


@pytest.mark.asyncio
@pytest.mark.skipif(_activity("act_003") is None, reason="act_003 이 일정에 없음")
async def test_customer_act003_saturday_noncritical_both_pass():
    """act_003 — 토요일(비휴무일) + 안전안내 → 성립(TourAPI·재난 두 축 모두 통과)."""
    act = _activity("act_003")
    operating = _operating(
        content_id=act.get("tour_api_content_id") or "126508",
        usetime_text="09:00~18:00(입장마감 17:00)",
        restdate_text="매주 화요일 휴무",
    )
    # JSON 의 시각(화요일)을 토요일로 재정의 — 같은 장소의 비휴무일 시나리오
    act_saturday = dict(act, time="2026-10-03T15:00:00+09:00")
    result = await ActivityTeam(
        FakeTools(_vals_from(act_saturday, operating=operating,
                             disaster=DISASTER_NON_CRITICAL))).execute(_task())

    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["operating"]["weekday_match"] is False
    assert result.decisions[0]["disaster"]["blocks"] is False
    assert "판정에 영향을 주는 등급은 아닙니다" in result.answer
