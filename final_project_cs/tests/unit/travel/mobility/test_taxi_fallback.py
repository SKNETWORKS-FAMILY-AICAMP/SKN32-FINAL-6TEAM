# -*- coding: utf-8 -*-
"""대중교통이 운행 시간 때문에 하나도 안 맞을 때 택시로 대체 (2026-10-07).

04:30 도착을 요구하면(첫차 05:34 전) 「결과 없음」만 나오던 것을 택시 후보로 대체해 싣는다. 대체한 사실은 라벨과 left_out 에 밝힌다.
역이 멀어서 못 만든 것(걸어갈 역 없음)이나 사용자가 modes 로 택시를 뺀 요청은 대체하지 않는다.
"""
from __future__ import annotations

from tests.unit.travel.mobility import test_plan_v1 as T      # 같은 폴더 시험의 실데이터 런타임을 쓴다 (시간표가 없는 기기는 SKIP)

from app.domains.travel_ops.instances.mobility.engine import plan as P

_PLACES = [{"key": "g", "name": "북촌", "kind": "activity", "lat": 37.5845, "lon": 126.9852},
           {"key": "s", "name": "석관동", "kind": "activity", "lat": 37.6076, "lon": 127.0601}]


def _items(day, start, end, arrive):
    # 두 일정은 같은 운행일(04:00 경계) 안에 둔다 — 운행일이 바뀌면 plan() 이 「숙소 위치를 모른다」로 잇지 않는다
    return [{"seq": 1, "kind": "activity", "title": "A", "place": "g",
             "starts_at": f"{day}T{start}:00+09:00", "ends_at": f"{day}T{end}:00+09:00"},
            {"seq": 2, "kind": "activity", "title": "B", "place": "s", "starts_at": f"{day}T{arrive}:00+09:00"}]


_RT = []


def _runtime_with_car():
    """택시는 택시 서비스(car — 로컬 길 그래프)가 있는 런타임에서만 만들어진다. 없으면 시험을 건너뛴다."""
    T._skip_if_no_data()
    if not _RT:
        import pytest
        from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
        try:
            _RT.append(build_verifier(quiet=True, local_router=True))
        except Exception as e:                       # 길 그래프가 없는 기기
            pytest.skip(f"로컬 길 그래프로 런타임을 못 올렸다 — {str(e)[:80]}")
    rt = _RT[0]
    if getattr(rt, "stats", {}).get("car") is not True:
        import pytest
        pytest.skip("택시 서비스(car)가 없는 런타임 — 데이터 축 SKIP")
    return rt


def _run(arrive, start="04:05", end="04:10", **kw):
    return P.plan(_PLACES, _items("2026-10-07", start, end, arrive), 1, {}, runtime=_runtime_with_car(), **kw)


def _route(out):
    return out["routes"].get("g_to_s") or next(iter(out["routes"].values()), None)


def test_before_first_train_falls_back_to_a_labelled_taxi():
    out = _run("05:00")          # 첫차(05:34) 전
    r = _route(out)
    assert r is not None and r["planned"] == "taxi", out
    taxi = [o for o in r["options"] if o["id"] == "taxi"][0]
    assert "대중교통 운행 시간 밖이라 택시로 대체" in taxi["label"] and taxi["eta_min"] > 0 and taxi.get("fare_krw")
    left = [e for v in out["left_out"].values() for e in v]
    assert any(e["code"] == "transit_hours_taxi" and "첫차" in e["reason"] for e in left), left


def test_daytime_is_untouched():
    r = _route(_run("10:30", "08:00", "08:30"))
    assert r is not None and r["planned"] != "taxi"
    assert not any("택시로 대체" in o["label"] for o in r["options"])


def test_explicit_modes_without_taxi_keep_the_old_no_result():
    out = _run("05:00", modes=["subway", "bus", "walk"])
    assert out["routes"] == {} or _route(out) is None or _route(out)["planned"] != "taxi"


def test_switch_off_restores_the_old_behaviour():
    orig = P.TAXI_FALLBACK_ON_SERVICE_HOURS_PROPOSED
    try:
        P.TAXI_FALLBACK_ON_SERVICE_HOURS_PROPOSED = False
        out = _run("05:00")
        r = _route(out)
        assert r is None or r["planned"] != "taxi"
    finally:
        P.TAXI_FALLBACK_ON_SERVICE_HOURS_PROPOSED = orig


def test_service_hours_classifier():
    pl = P.Planner.__new__(P.Planner)
    assert pl._service_hours_blocked({"code": "before_first"}, [])
    assert pl._service_hours_blocked({"code": "no_data"}, [{"code": "no_last_departure", "reason": "04:00 은 1111 첫차(04:20) 이전이다"}])
    assert not pl._service_hours_blocked({"code": "no_data", "reason": "도보 상한 안에 지하철역이 없다"}, [])
    assert not pl._service_hours_blocked({"code": "no_data"}, [{"code": "no_last_departure", "reason": "행선지를 찾지 못했다"}])
