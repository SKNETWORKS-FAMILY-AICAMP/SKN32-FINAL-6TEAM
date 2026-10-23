# -*- coding: utf-8 -*-
"""원장에 없는 가게도 구글로 그 시각 영업을 확인한다. `[2026-10-21]`

☆`find_place` 가 인허가 · 카카오로 찾은 가게는 원장 번호(`place_uid`)가 없다. 영업 도구는 모두 원장 번호를 받아
  (`live_open_check` 도 원장 표에서 이름 · 좌표를 꺼냈다) 그런 가게는 구글을 부를 길이 없었고 영업 줄이 늘 「확인 필요」였다
  (사람 정답 평가 33번 — `wiki/records/reports/2026-10-21_요식판정_사람정답평가_v1.md`).
★찾은 결과의 이름 · 좌표는 **도구 결과에서** 꺼낸다(`find_call_id`) — 모델이 이름 · 좌표를 적어 넘기지 않는다.
"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from app.domains.travel_ops.instances.dining.agent import validate_check
from app.domains.travel_ops.instances.dining.agent_tools import SPECS, DiningTools
from app.domains.travel_ops.instances.dining.judge import outside_ledger

START, END = "2026-10-25T12:00", "2026-10-25T13:00"


class FakeGoogle:
    def __init__(self, verdict=("open", "구글: 그 시각에 영업한다"), found=("g-1", 40.0)):
        self.verdict, self.found, self.asked = verdict, found, []

    def find_place_id(self, *, name, latitude, longitude):
        self.asked.append((name, latitude, longitude))
        return self.found

    def open_verdict(self, place_id, *, start, end):
        return self.verdict


@contextmanager
def _no_db():
    raise AssertionError("원장 밖 가게 확인은 DB 를 열지 않는다")
    yield  # pragma: no cover


def _tools(google=None) -> DiningTools:
    return DiningTools(_no_db, google=google)


def _found(tools: DiningTools, *, source="map", place_uid=None, name="골목떡볶이", lat=37.57, lng=126.98) -> str:
    """`find_place` 결과를 호출 기록에 그대로 넣는다(찾기 자체는 DB · 카카오가 필요하다 — 통합 시험 몫)."""
    call_id = f"c{len(tools.calls) + 1}"
    tools.calls.append({"id": call_id, "tool": "find_place", "args": {"name": name},
                        "result": {"verdict": "unknown", "found": True, "source": source, "place_uid": place_uid,
                                   "name": name, "address": "서울특별시 종로구 시험로 1", "lat": lat, "lng": lng,
                                   "match": source, "needs_review": True}})
    return call_id


def test_a_shop_found_on_the_map_is_checked_on_google_with_the_found_name_and_place():
    google = FakeGoogle()
    tools = _tools(google)
    found = _found(tools)
    got = tools.call("live_open_check", {"find_call_id": found, "start": START, "end": END})
    assert got["verdict"] == "open" and got["google_place_id"] == "g-1"
    assert google.asked == [("골목떡볶이", 37.57, 126.98)]                  # 도구 결과의 이름 · 좌표 그대로
    assert got["place_source"] == "map"


def test_a_shop_found_only_in_the_license_record_is_checked_too():
    google = FakeGoogle(verdict=("closed", "구글: 그 시각에 닫혀 있다"))
    tools = _tools(google)
    found = _found(tools, source="license", name="장수분식")
    got = tools.call("live_open_check", {"find_call_id": found, "start": START})
    assert got["verdict"] == "closed" and got["place_source"] == "license"


def test_google_not_finding_the_same_shop_stays_unknown():
    tools = _tools(FakeGoogle(found="unmatched"))
    got = tools.call("live_open_check", {"find_call_id": _found(tools), "start": START})
    assert got["verdict"] == "unknown"


def test_without_google_it_stays_unknown():
    tools = _tools(None)
    assert tools.call("live_open_check", {"find_call_id": _found(tools), "start": START})["verdict"] == "unknown"


def test_find_call_id_must_point_at_a_found_shop_outside_the_ledger():
    tools = _tools(FakeGoogle())
    ledger = _found(tools, source="ledger", place_uid="00000000-0000-0000-0000-000000000001")
    assert "refused" in tools.call("live_open_check", {"find_call_id": ledger, "start": START})      # 원장 가게는 place_uid 로
    assert "refused" in tools.call("live_open_check", {"find_call_id": "c99", "start": START})       # 없는 호출
    assert "refused" in tools.call("live_open_check", {"start": START})                              # 가게를 안 줌
    assert "find_call_id" in SPECS["live_open_check"].parameters["properties"]


def _check(verdict, call_id):
    return {"check": "open_at", "verdict": verdict, "evidence": [{"call_id": call_id, "path": "verdict", "value": "open"}]}


def _live(i, find_call_id, verdict="open"):
    return {"id": f"c{i}", "tool": "live_open_check", "args": {"find_call_id": find_call_id, "start": START, "end": END},
            "result": {"verdict": verdict}}


def test_an_open_backed_by_google_on_the_same_found_shop_passes():
    tools = SimpleNamespace(calls=[_live(2, "c1")])
    assert validate_check(_check("ok", "c2"), tools, find_call_id="c1", start=START, end=END) is None


def test_google_on_another_found_shop_is_not_evidence():
    tools = SimpleNamespace(calls=[_live(3, "c2")])
    assert validate_check(_check("ok", "c3"), tools, find_call_id="c1", start=START, end=END) == "evidence_other_place"
    assert validate_check(_check("ok", "c3"), tools, start=START, end=END) == "evidence_other_place"   # 가게를 모르면 받지 않는다
    assert validate_check(_check("ok", "c3"), tools, place_uid="p1", start=START, end=END) == "evidence_other_place"


def test_an_uncited_google_closed_on_the_same_found_shop_blocks_an_open():
    detail = {"id": "c3", "tool": "place_detail", "args": {"place_uid": None}, "result": {"hours_text": ["매일 11:00-21:00"]}}
    tools = SimpleNamespace(calls=[_live(2, "c1", "closed"), detail])
    claim = {"check": "open_at", "verdict": "ok", "evidence": [{"call_id": "c3", "path": "hours_text", "value": ["매일 11:00-21:00"]}]}
    assert validate_check(claim, tools, find_call_id="c1", start=START, end=END) == "contradicts_rule_tool"


def test_the_judge_run_records_candidates_from_the_tool_results(monkeypatch):
    """☆에이전트 결과의 `tool_calls` 는 도구 결과를 싣지 않는다 — 그것으로 세면 후보가 늘 빈 목록이었다(첫 판 결함). 도구 기록에서 센다."""
    from app.domains.travel_ops.instances.dining import judge

    written = []

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params):
            written.append(params)

    class Conn:
        def cursor(self):
            return Cur()

        def transaction(self):
            return Cur()

    @contextmanager
    def connect():
        yield Conn()

    def fake_judge_day(plan, *, tools, chat, deadline_s):
        _found(tools, source="license", name="장수분식")
        return SimpleNamespace(items=[], tool_calls=[{"id": c["id"], "tool": c["tool"], "args": c["args"]} for c in tools.calls],
                               failure="final_not_json", stats={}, requests=[], missing=[])

    monkeypatch.setattr(judge, "judge_day", fake_judge_day)
    review = {"items": [{"id": "0-1", "kind": "dining", "date": "2026-10-25", "starts_at": "12:00",
                         "place": {"name": "장수분식", "latitude": 37.57, "longitude": 126.98}, "rows": []}]}
    judge.run(connect, tenant_id="t", intake_id="i", revision=1, review=review, notes="", chat=None, model="m",
              tools_factory=lambda _connect: _tools())
    import json as _json
    runs = [_json.loads(p[10]) for p in written if p[5] == "_run" and "outside_ledger" in _json.loads(p[10])]
    assert runs and runs[0]["outside_ledger"][0]["query"] == "장수분식"


def test_outside_ledger_lists_license_values_but_only_the_query_for_map_hits():
    """원장 추가 후보 — 인허가(공공) 값은 남기고, 카카오 결과는 저장하지 않는다(약관 · `agent_tools` 머리말)."""
    tools = _tools()
    _found(tools, source="license", name="장수분식")
    _found(tools, source="map", name="골목떡볶이")
    _found(tools, source="ledger", place_uid="00000000-0000-0000-0000-000000000001", name="광화문미진")
    got = outside_ledger(tools.calls)
    assert [g["query"] for g in got] == ["장수분식", "골목떡볶이"]
    license_row, map_row = got
    assert license_row["source"] == "license" and license_row["address"] == "서울특별시 종로구 시험로 1"
    assert map_row == {"query": "골목떡볶이", "source": "map"}
