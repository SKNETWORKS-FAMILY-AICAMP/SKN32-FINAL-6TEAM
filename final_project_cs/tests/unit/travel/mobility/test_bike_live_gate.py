# -*- coding: utf-8 -*-
"""따릉이 실시간 조회(`BikeLive`)의 호출 한도 문 — `TravelSource` 를 거치지 않는 직접 호출도 env 하루 한도·DB 예산을 지킨다(2026-10-05).

한도가 차면 **부르지 않고** 모름(`None`)으로 돌린다 — 거치 대수는 근거없음이고 서비스는 계속된다. 문을 못 만들면 실시간을 끈다."""
from __future__ import annotations

import io
import json
import urllib.request

import pytest

from app.infrastructure.travel.source_budget import BudgetExhausted, BudgetUnavailable
from app.modules.travel_ops.mobility import wiring
from app.modules.travel_ops.mobility.engine.bike import BikeLive


class Gate:
    def __init__(self, raises=None):
        self.names, self.raises = [], raises

    def acquire(self, name):
        self.names.append(name)
        if self.raises:
            raise self.raises


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _urlopen_spy(monkeypatch):
    calls = []

    def fake(url, timeout=None):
        calls.append(url)
        body = {"rentBikeStatus": {"row": [{"parkingBikeTotCnt": "7", "stationId": "ST-1"}]}}
        return _Resp(json.dumps(body).encode("utf-8"))
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


@pytest.mark.parametrize("exc", [BudgetExhausted("seoul_bike", 3600.0), BudgetUnavailable("seoul_bike", 10.0)])
def test_a_spent_budget_means_the_call_is_never_made(monkeypatch, exc):
    calls = _urlopen_spy(monkeypatch)
    live = BikeLive(key="SECRET-KEY-123", gate=Gate(exc))
    assert live.get("ST-1") is None
    assert calls == [] and live.calls == 0, "★한도가 찼으면 바깥으로 나가지 않는다"
    assert live.last_error == {"kind": "budget", "reason": exc.reason}
    assert "SECRET-KEY-123" not in json.dumps(live.last_error), "기록에 키가 새지 않는다"


def test_an_open_gate_lets_the_call_through_once_and_names_the_meter(monkeypatch):
    calls = _urlopen_spy(monkeypatch)
    gate = Gate()
    live = BikeLive(key="k", gate=gate)
    got = live.get("ST-1")
    assert gate.names == ["seoul_bike"] and live.calls == 1 and len(calls) == 1
    assert got is not None and got["available"] == 7


def test_a_gate_bug_is_not_swallowed_as_a_budget_miss(monkeypatch):
    _urlopen_spy(monkeypatch)
    with pytest.raises(RuntimeError):
        BikeLive(key="k", gate=Gate(RuntimeError("코드 결함"))).get("ST-1")


def test_no_gate_keeps_the_old_behaviour(monkeypatch):
    calls = _urlopen_spy(monkeypatch)
    assert BikeLive(key="k").get("ST-1")["available"] == 7 and len(calls) == 1


def test_fixture_mode_never_touches_the_gate():
    gate = Gate(BudgetExhausted("seoul_bike", 1.0))
    live = BikeLive(fixture={"checked_at": "t", "counts": {"ST-1": 4}}, gate=gate)
    assert live.get("ST-1")["available"] == 4 and gate.names == []


def _fake_settings(key):
    class Settings:
        seoul_openapi_key = key
        mobility_data_dir = ""
        mobility_gh_url = ""
        guardrails_path = "config/guardrails.yaml"
    return Settings()


def test_wiring_turns_live_off_without_a_gate(monkeypatch):
    """문이 없으면(조립이 못 만들었거나 안 넘김) 한도를 못 지킨 채 부르지 않는다 — 실시간(seoul_key)을 비워 끈다."""
    seen = {}
    monkeypatch.setattr(wiring, "configure", lambda **kw: seen.update(kw) or {"mode": "disabled"})
    wiring.configure_from_settings(_fake_settings("k"), preload=False)
    assert seen["seoul_key"] == "" and seen["bike_gate"] is None


def test_wiring_passes_the_gate_through_when_given(monkeypatch):
    seen = {}
    monkeypatch.setattr(wiring, "configure", lambda **kw: seen.update(kw) or {"mode": "disabled"})
    sentinel = object()
    wiring.configure_from_settings(_fake_settings("k"), preload=False, bike_gate=sentinel)
    assert seen["seoul_key"] == "k" and seen["bike_gate"] is sentinel


def test_wiring_needs_no_gate_without_a_key(monkeypatch):
    seen = {}
    monkeypatch.setattr(wiring, "configure", lambda **kw: seen.update(kw) or {"mode": "disabled"})
    wiring.configure_from_settings(_fake_settings(""), preload=False)
    assert seen["seoul_key"] == "" and seen["bike_gate"] is None


def test_the_real_gate_for_the_bike_meter_can_be_built():
    """조립이 쓰는 실제 `build_gate` 가 따릉이 이름으로 만들어진다(하루 한도 이름이 settings 와 맞는다)."""
    from app.core.settings import get_settings
    from app.infrastructure.travel.source_budget import build_gate
    assert "seoul_bike" in get_settings().source_rate_limits()
    assert build_gate(get_settings(), ["seoul_bike"]) is not None
