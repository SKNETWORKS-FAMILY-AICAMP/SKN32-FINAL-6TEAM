"""성립 판정이 판정 계층을 거친다(4단계, D-CS-008).

★가장 중요한 약속 — **섀도 모드에서는 고객 결과가 규칙 모드와 한 글자도 다르지 않다.** LLM 이 일부러
  반대로 답하게 해 놓고 결과(답변 · decisions · 근거 · 경고 · 실패 코드)를 통째로 비교한다.
★LLM 모드에서는 LLM 판정이 결과에 들어가되, 모르면 모른다고 말하고 코드가 확정한 불가는 뒤집지 못한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.travel_ops.instances.activity.team_a import ActivityTeam
from app.domains.travel_ops.instances.activity import failure_codes as fc
from app.domains.travel_ops.instances.activity.judge import SHADOW_LOGGER_NAME

from ..test_activity_check_feasible import FakeTools, _operating, _task, _values
from ._judge_fakes import out

NOTICE = "https://www.example.go.kr/notice?id=1"


class ScriptedJudgeLLM:
    """판정 종류별로 정해 둔 답을 낸다. 기본은 **규칙과 반대**로 답한다."""

    def __init__(self, **overrides):
        self.overrides = overrides
        self.calls = []

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None,
                    instructions=None, run_id=None):
        from types import SimpleNamespace

        kind = payload["kind"]
        self.calls.append(kind)
        answer = self.overrides.get(kind) or _contrary(kind, payload)
        if isinstance(answer, Exception):
            raise answer
        output, sources = answer
        return SimpleNamespace(output=output, sources=sources, search_calls=len(sources), latency_ms=3,
                               input_tokens=1, output_tokens=1, reasoning_tokens=0, model="fake")


def _contrary(kind, payload):
    if kind == "closure":
        return out("closed", quotes=[payload["restdate_text"]]), []
    if kind == "operating_hours":
        return out("outside", quotes=[payload["usetime_text"]]), []
    if kind == "weather_sensitive":
        return out("indoor"), []
    if kind == "disaster_effect":
        steps = {m["step"] for m in payload["messages"]}
        return out("no_effect" if "위급재난" in steps else "blocks", quotes=[payload["messages"][0]["text"]]), []
    return out("closed", citations=[{"url": NOTICE, "quote": "임시 휴관", "published_at": "2026-10-01"}]), [NOTICE]


class Inline:
    """받은 일을 **다른 스레드에서** 끝까지 돌리고 기다린다 — 실제 실행기(스레드 풀)와 같은 조건이다.
    ★Team 은 이벤트 루프 안에서 돌기 때문에, 같은 스레드에서 돌리면 `asyncio.run` 이 거부된다."""

    def submit(self, work):
        import threading

        thread = threading.Thread(target=work)
        thread.start()
        thread.join(10)
        return True


def _team(values, *, llm=None, mode=None):
    team = ActivityTeam(FakeTools(values))
    if llm is not None:
        team.judge_llm = llm
        team.judge_mode = mode
        team.judge_runner = Inline()
    return team


def _run(team, task):
    return asyncio.run(team.execute(task))


def _comparable(result):
    data = result.model_dump(mode="json")
    for item in data["evidence"]:
        item.pop("observed_at", None)
    return data


#: ★시각은 한 번만 정한다 — 두 실행(규칙 · 섀도)의 입력이 마이크로초까지 같아야 결과를 통째로 비교할 수 있다.
NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


def _scenario(name):
    now = NOW
    tuesday = now + timedelta(days=(1 - now.weekday()) % 7 + 7)          # 다음다음 화요일 언저리 — 72시간 밖
    disaster_red = {"for_region": [{"step": "위급재난", "kind": "호우", "text": "부산 해운대 침수, 접근 금지",
                                    "regions": ["부산광역시"], "created_at": now.isoformat()}],
                    "confirmed_at": now.isoformat(), "source": "disaster_api"}
    disaster_info = {"for_region": [{"step": "안전안내", "kind": "호우", "text": "종로구 사직로 통제",
                                     "regions": ["서울특별시 종로구"], "created_at": now.isoformat()}],
                     "confirmed_at": now.isoformat(), "source": "disaster_api"}
    scenarios = {
        "closed_weekday": _values(operating=_operating(), starts_at=tuesday.replace(hour=5)),
        "open_with_text": _values(operating=_operating()),
        "red_disaster": _values(operating=_operating(), disaster=disaster_red),
        "info_disaster": _values(operating=_operating(), disaster=disaster_info),
        "near_outdoor": _values(operating=_operating(restdate_text="연중무휴"), starts_at=now + timedelta(hours=30)),
    }
    values = scenarios[name]
    if name == "near_outdoor":
        values["read.place"].update({"weather_sensitive": None, "name": "올림픽공원"})
        values["read.weather"] = {"matched_hour": "15:00", "precipitation_probability": 10,
                                  "wind_speed_kmh": 5, "source": "open_meteo"}
    return values


@pytest.mark.parametrize("name", ["closed_weekday", "open_with_text", "red_disaster", "info_disaster", "near_outdoor"])
def test_shadow_result_is_identical_to_rule(name, caplog):
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)
    task = _task()
    rule = _run(_team(_scenario(name)), task)
    llm = ScriptedJudgeLLM()
    shadow = _run(_team(_scenario(name), llm=llm, mode="shadow"), task)
    assert _comparable(shadow) == _comparable(rule)
    # 판정 LLM 은 실제로 불렸고, 차이는 로그로만 남았다
    assert llm.calls
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == SHADOW_LOGGER_NAME]
    assert {line["kind"] for line in lines} == set(llm.calls)


def test_rule_mode_never_calls_the_llm():
    llm = ScriptedJudgeLLM()
    _run(_team(_scenario("near_outdoor"), llm=llm, mode="rule"), _task())
    assert llm.calls == []


def test_live_status_only_for_outdoor_or_soon():
    """실내이고 72시간 밖이면 웹 판정을 부르지 않는다(비용)."""
    llm = ScriptedJudgeLLM()
    _run(_team(_scenario("open_with_text"), llm=llm, mode="shadow"), _task())
    assert "live_status" not in llm.calls
    llm = ScriptedJudgeLLM()
    _run(_team(_scenario("near_outdoor"), llm=llm, mode="shadow"), _task())
    assert "live_status" in llm.calls


# ── LLM 모드 ──────────────────────────────────────────────────

def _llm(name, **overrides):
    return _run(_team(_scenario(name), llm=ScriptedJudgeLLM(**overrides), mode="llm"), _task())


def test_llm_closure_reads_what_the_rule_cannot():
    """「매월 둘째 주 X요일」처럼 규칙이 못 읽는 원문을 LLM 이 휴무로 판정하면 불가가 된다."""
    result = _llm("open_with_text", operating_hours=(out("within", quotes=["09:00~18:00"]), []))
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["failure_code"] == fc.CLOSED_WEEKDAY
    assert decision["operating"]["closure_judged_by"] == "llm"
    assert "원문 해석: «매주 화요일 휴무. 단 공휴일과 겹치면 개방»" in result.answer
    assert any(e["source_id"] == "activity.judge.closure" for e in result.model_dump()["evidence"])


def test_llm_hours_outside_is_a_place_problem():
    result = _llm("open_with_text", closure=(out("not_closed", quotes=["매주 화요일 휴무"]), []))
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["failure_code"] == fc.OUTSIDE_HOURS
    assert decision["operating"]["hours_verdict"] == "outside"
    assert "운영시간 밖입니다" in result.answer and "자동 해석하지 않았습니다" not in result.answer


def test_llm_cannot_override_a_critical_disaster():
    """★`[결정 2026-10-08]` 위급재난은 유형 · 내용과 관계없이 막는다 — LLM 에 묻지도 않는다.
    예전에는 LLM 이 「무관」으로 판정하면 성립으로 뒤집었다."""
    llm = ScriptedJudgeLLM(closure=(out("not_closed", quotes=["매주 화요일 휴무"]), []),
                           operating_hours=(out("within", quotes=["09:00~18:00"]), []))
    result = _run(_team(_scenario("red_disaster"), llm=llm, mode="llm"), _task())
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["disaster"]["blocks"] is True
    assert decision["failure_code"] == fc.DISASTER_BLOCKS and decision["disaster"]["critical"] == 1
    assert "disaster_effect" not in llm.calls
    assert "위급재난 문자(호우)가 발령 중이라" in result.answer
    assert any("유형·내용과 관계없이 막는다" in w for w in result.warnings)


def test_llm_unknown_on_a_non_critical_disaster_does_not_block():
    """★위급재난이 아닌 문자에서 LLM 이 근거를 못 대면(모름) 규칙대로 막지 않고, 모른다고 알린다."""
    result = _llm("info_disaster", disaster_effect=(out("blocks", quotes=["지어낸 구절"]), []),
                  closure=(out("not_closed", quotes=["매주 화요일 휴무"]), []),
                  operating_hours=(out("within", quotes=["09:00~18:00"]), []))
    decision = result.decisions[0]
    assert decision["disaster"]["blocks"] is False
    assert "관련 있는지는 확인하지 못했습니다" in result.answer
    assert any("위급재난이 아니라 막지 않았다" in w for w in result.warnings)


def test_llm_can_block_a_related_non_critical_disaster():
    """긴급재난 · 안전안내는 LLM 이 「이 활동을 막는다」고 근거와 함께 답하면 불가다."""
    result = _llm("info_disaster", closure=(out("not_closed", quotes=["매주 화요일 휴무"]), []),
                  operating_hours=(out("within", quotes=["09:00~18:00"]), []))
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["disaster"]["blocks"] is True
    assert decision["disaster"]["judged_by"] == "llm"
    assert "문자 해석: «종로구 사직로 통제»" in result.answer


def test_llm_live_closed_blocks_with_source():
    result = _llm("near_outdoor", weather_sensitive=(out("outdoor"), []),
                  closure=(out("not_closed", quotes=["연중무휴"]), []),
                  operating_hours=(out("within", quotes=["09:00~18:00"]), []))
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["failure_code"] == fc.LIVE_CLOSED
    assert decision["live_status"]["citations"] == [NOTICE]
    assert NOTICE in result.answer


def test_llm_call_failure_falls_back_to_rule_everywhere():
    """호출이 전부 실패하면 결과는 규칙 모드와 같다(실패 코드는 판정 계층 안에만 남는다)."""
    boom = TimeoutError()
    task = _task()
    rule = _run(_team(_scenario("closed_weekday")), task)
    llm = _run(_team(_scenario("closed_weekday"), llm=ScriptedJudgeLLM(
        closure=boom, operating_hours=boom, weather_sensitive=boom, disaster_effect=boom, live_status=boom),
        mode="llm"), task)
    assert _comparable(llm) == _comparable(rule)


def test_live_status_address_comes_from_csv():
    """주소는 CSV 장소 목록의 addr1·addr2 에서 온다(`read.place` 에는 주소가 없다)."""
    from app.domains.travel_ops.instances.activity.feasibility import _csv_lookup

    content_id = next(iter(_csv_lookup._by_content_id))
    row = _csv_lookup.find_by_content_id(content_id)
    values = _scenario("near_outdoor")
    values["read.place"]["source_content_id"] = content_id
    seen = {}

    class Capture(ScriptedJudgeLLM):
        async def judge(self, prompt_key, payload, **kwargs):
            if payload["kind"] == "live_status":
                seen.update(payload)
            return await super().judge(prompt_key, payload, **kwargs)
    _run(_team(values, llm=Capture(weather_sensitive=(out("outdoor"), [])), mode="shadow"), _task())
    expected = " ".join(p for p in ((row.get("addr1") or "").strip(), (row.get("addr2") or "").strip()) if p)
    assert seen["address"] == expected and expected
