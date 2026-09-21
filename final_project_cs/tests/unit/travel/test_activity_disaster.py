# -*- coding: utf-8 -*-
"""예약 인근에 재난문자가 발령됐을 때 일정이 가능한지 — 실 API 통합 테스트.

★이 파일은 실 API 키로만 실행된다. pytest.ini `addopts = -m "not live"` 때문에
  `pytest` 단독 실행 시 자동으로 건너뛴다.
  실행하려면: pytest -m live tests/unit/travel/test_activity_disaster.py

★테스트 설계 원칙:
  - `read.booking`·`read.policy`·`read.place`·`read.weather` 는 FakeTools 로
    고정한다 — DB·TourAPI 없이도 돌아야 한다.
  - `read.disaster` 만 실 API(`DisasterMsgSource`)를 호출한다.
  - 실제 재난 상황에 따라 응답 내용이 달라지므로 **구조 불변량**을 검증하고,
    실제 데이터에 따라 조건부로 내용을 검증한다.

★배선 경위: wiki/teams/activity.md 「재난문자 등급 대조」 §2026-09-20.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.travel_ops.activity import ActivityTeam

from .helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
DEFAULT_STARTS_AT = datetime(2026, 10, 3, 15, tzinfo=UTC)


# ── 키·소스 ────────────────────────────────────────────────────
def _disaster_key() -> str:
    try:
        from app.core.settings import get_settings
        s = get_settings()
        return getattr(s, "disaster_api_key", "") or getattr(s, "data_go_kr_key", "") or ""
    except Exception:
        return ""


@pytest.fixture(scope="module")
def disaster_api_result() -> dict[str, Any]:
    """실 API 를 호출해 최근 6시간 재난문자를 가져온다.

    키가 없거나 호출에 실패하면 테스트 전체를 skip 한다.
    """
    key = _disaster_key()
    if not key:
        pytest.skip("ACOP_DISASTER_API_KEY 미설정 — .env.apikeys 확인")

    from app.infrastructure.travel.disaster_msg import DisasterMsgSource  # noqa: PLC0415
    source = DisasterMsgSource(service_key=key)
    result = source.recent(since_hours=6.0, region_name="서울특별시")
    if result is None:
        pytest.skip(f"재난문자 API 응답 없음 — misses: {dict(source.misses)}")

    msgs = result.get("messages") or []
    print(f"\n{'='*60}")
    print(f"[재난문자 API] confirmed_at={result.get('confirmed_at', '')[:19]}")
    print(f"수신 {len(msgs)}건")
    if msgs:
        for i, m in enumerate(msgs, 1):
            print(f"\n  [{i}] SN={m.get('SN')}  등급={m.get('EMRG_STEP_NM')}  재해={m.get('DST_SE_NM')}")
            print(f"       수신지역={m.get('RCPTN_RGN_NM')}")
            print(f"       발송시각={m.get('CRT_DT')}")
            print(f"       내용={m.get('MSG_CN', '')[:100]}")
    else:
        print("  (현재 발령된 재난문자 없음)")
    print(f"{'='*60}")

    return result


# ── FakeTools 변형 ─────────────────────────────────────────────
class DisasterRealTools(FakeTools):
    """read.disaster 만 실 API 결과를 쓰고 나머지는 FakeTools 그대로."""

    def __init__(self, base_values: dict[str, Any], real_disaster: dict[str, Any]) -> None:
        super().__init__(base_values)
        self._real_disaster = real_disaster

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name == "read.disaster":
            # FakeTools 의 권한·중복·예산 검사는 그대로 통과시키되 값만 바꾼다
            from app.core.contracts import ToolNotAllowed
            from app.tools.read_tools import ToolBudgetExceeded, ToolLoopExceeded
            if name not in allowed_tools:
                raise ToolNotAllowed(name)
            sig = name + ":" + repr(sorted(arguments.items()))
            if sig in seen:
                raise ToolLoopExceeded(name)
            if budget is not None and len(seen) >= budget:
                raise ToolBudgetExceeded(f"budget {budget} exhausted before {name}")
            seen.add(sig)
            self.calls.append((name, dict(arguments)))
            return self._real_disaster
        return super().call(name, context, arguments, allowed_tools, seen, budget)


# ── 공통 헬퍼 ──────────────────────────────────────────────────
def _task(capability: str = "activity.check_feasible") -> Any:
    context = pack("activity", scope=["activity"])
    return task("activity", capability, context, ALLOWED)


def _base_values(starts_at: datetime = DEFAULT_STARTS_AT) -> dict[str, Any]:
    """재난문자 외 나머지 도구 응답 — 항상 고정."""
    place = {"place_id": "p1", "name": "경복궁", "weather_sensitive": False,
             "latitude": 37.5796, "longitude": 126.9770}
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": starts_at, "party_size": 2, "capacity": 4},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": None,
    }


def _has_critical(result: dict[str, Any]) -> bool:
    return any(m.get("EMRG_STEP_NM") == "위급재난"
               for m in (result.get("messages") or [])
               if isinstance(m, dict))


def _show(label: str, team_result) -> None:
    """pytest -s 로 실행해야 보인다."""
    msgs = team_result.decisions[0].get("disaster", {}).get("messages", [])
    print(f"\n--- {label} ---")
    print("outcome  :", team_result.outcome)
    print("feasible :", team_result.decisions[0].get("feasible"))
    print("disaster :", f"{len(msgs)}건")
    print("answer   :", team_result.answer[:120])
    print("warnings :", team_result.warnings)


# ── 테스트 ─────────────────────────────────────────────────────
@pytest.mark.live
@pytest.mark.asyncio
async def test_activity_result_structure_with_real_disaster(disaster_api_result):
    """실 API 결과로 ActivityTeam 이 항상 완료 구조를 돌려주는지 확인한다.

    ★재난 상황과 무관한 **구조 불변량**을 검증한다:
      - outcome=completed
      - decisions 에 feasible·disaster 키 존재
      - evidence 에 read.disaster 근거 포함
      - answer 비어 있지 않음
    """
    tools = DisasterRealTools(_base_values(), disaster_api_result)
    result = await ActivityTeam(tools).execute(_task())
    _show("구조 불변량", result)

    assert result.outcome == "completed"
    assert "feasible" in result.decisions[0]
    assert "disaster" in result.decisions[0], "disaster 키가 없다 — 실 API 결과가 처리되지 않았다"
    assert result.answer


@pytest.mark.live
@pytest.mark.asyncio
async def test_activity_feasible_matches_critical_grade(disaster_api_result):
    """위급재난 유무에 따라 feasible 이 올바르게 설정되는지 확인한다.

    ★실 데이터 기준으로 조건부 검증한다 — 현재 재난 상황에 따라
      둘 중 하나가 검증된다.
    """
    tools = DisasterRealTools(_base_values(), disaster_api_result)
    result = await ActivityTeam(tools).execute(_task())
    _show("등급 대조", result)

    critical = _has_critical(disaster_api_result)
    disaster_dec = result.decisions[0].get("disaster", {})

    if critical:
        assert result.decisions[0]["feasible"] is False, "위급재난 있는데 feasible=True"
        assert disaster_dec.get("blocks") is True
        assert "위급재난" in result.answer
        # ★관련성 미확인 캐비앗은 위급재난 때만 붙는다
        assert "지역·주제가 이 활동과" in result.answer
        assert any("지역·주제 관련성" in w for w in result.warnings)
    else:
        assert result.decisions[0]["feasible"] is True, "위급재난 없는데 feasible=False"
        assert disaster_dec.get("blocks") is False
        # 위급재난이 아닌 메시지나 빈 목록 — 관련성 캐비앗 없음
        assert not any("지역·주제 관련성" in w for w in result.warnings)


@pytest.mark.live
@pytest.mark.asyncio
async def test_activity_answer_mentions_disaster_correctly(disaster_api_result):
    """answer 에 재난문자 안내 문구가 데이터에 맞게 포함되는지 확인한다."""
    tools = DisasterRealTools(_base_values(), disaster_api_result)
    result = await ActivityTeam(tools).execute(_task())
    _show("answer 문구", result)

    messages = disaster_api_result.get("messages") or []
    critical = _has_critical(disaster_api_result)

    if not messages:
        assert "확인 범위 내 재난문자는 없습니다" in result.answer
    elif critical:
        assert "위급재난" in result.answer
    else:
        # 메시지는 있지만 위급재난 없음
        assert f"재난문자 {len(messages)}건" in result.answer
        assert "판정에 영향을 주는 등급은 아닙니다" in result.answer


@pytest.mark.live
@pytest.mark.asyncio
async def test_activity_evidence_carries_disaster_source(disaster_api_result):
    """실 API 결과가 근거(Evidence)로 기록되는지 확인한다."""
    tools = DisasterRealTools(_base_values(), disaster_api_result)
    result = await ActivityTeam(tools).execute(_task())

    evidence_ids = [e.evidence_id for e in result.evidence]
    assert any("read.disaster" in eid for eid in evidence_ids), (
        f"read.disaster 근거 없음 — evidence: {evidence_ids}")


@pytest.mark.live
@pytest.mark.asyncio
async def test_activity_disaster_decision_fields_present(disaster_api_result):
    """decisions.disaster 에 필수 필드가 존재하는지 확인한다."""
    tools = DisasterRealTools(_base_values(), disaster_api_result)
    result = await ActivityTeam(tools).execute(_task())

    dis = result.decisions[0].get("disaster", {})
    for field in ("messages", "blocks", "confirmed_at", "source"):
        assert field in dis, f"decisions.disaster.{field} 없음"