"""공급자 응답 오류가 다음 정상 조회를 막거나 잘못된 재고·경로를 만들지 않습니다."""
import io
import json
import urllib.request

import pytest

from app.domains.travel_ops.instances.mobility.engine.bike import BikeLive, BikeRouter


class Gate:
    def __init__(self):
        self.names = []

    def acquire(self, name):
        self.names.append(name)


def response(count):
    return {"rentBikeStatus": {"RESULT": {"CODE": "INFO-000"}, "row": [
        {"stationId": "ST-1", "parkingBikeTotCnt": count}]}}


@pytest.mark.parametrize("bad", [
    None, [], "broken", {"rentBikeStatus": []},
    {"rentBikeStatus": {"row": {"stationId": "ST-1"}}},
    {"rentBikeStatus": {"row": [None]}},
    {"RESULT": ["INFO-100"]},
    response(-1), response(True), response(1.5), response("-1"), response("1.5"),
    response(None), response(float("inf")),
])
def test_bad_stock_response_is_rejected_and_next_call_recovers(monkeypatch, bad):
    bodies = iter([bad, response("7")])
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k:
                        io.BytesIO(json.dumps(next(bodies)).encode()))
    gate = Gate()
    live = BikeLive(key="test-only-secret", gate=gate)
    assert live.get("ST-1") is None
    assert live.last_error["kind"] == "bad_response"
    assert "test-only-secret" not in json.dumps(live.last_error)
    assert live.get("ST-1")["available"] == 7
    assert live.last_error is None
    assert live.calls == 2 and gate.names == ["seoul_bike", "seoul_bike"]


@pytest.mark.parametrize("count", [0, "0", 7, "7"])
def test_valid_whole_stock_count_is_preserved(monkeypatch, count):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k:
                        io.BytesIO(json.dumps(response(count)).encode()))
    assert BikeLive(key="test-key").get("ST-1")["available"] == int(count)


@pytest.mark.parametrize("field,value", [
    (field, value) for field in ("distance", "time")
    for value in (True, float("nan"), float("inf"), -float("inf"), -1)
])
def test_bad_route_metric_is_rejected_without_storing_path(field, value):
    class Router:
        def route(self, *a, **k):
            path = {"distance": 100, "time": 25000}
            path[field] = value
            return {"paths": [path]}
    record = {}
    bike = BikeRouter(router=Router(), record=record)
    assert bike.route("bike", 37.5, 127.0, 37.51, 127.01) is None
    assert bike.last_error["kind"] == "bad_response"
    assert record == {} and bike.calls == 1


@pytest.mark.parametrize("bad", [[], "broken", {"paths": [None]}, {"paths": {"distance": 2}}])
def test_malformed_route_then_valid_route_recovers(bad):
    class Router:
        def __init__(self):
            self.docs = iter([bad, {"paths": [{"distance": 100.5, "time": 25000}]}])
        def route(self, *a, **k):
            return next(self.docs)
    bike = BikeRouter(router=Router())
    assert bike.route("bike", 37.5, 127.0, 37.51, 127.01) is None
    assert bike.last_error["kind"] == "bad_response"
    got = bike.route("bike", 37.5, 127.0, 37.51, 127.01)
    assert (got["distance_m"], got["time_s"]) == (100.5, 25)
