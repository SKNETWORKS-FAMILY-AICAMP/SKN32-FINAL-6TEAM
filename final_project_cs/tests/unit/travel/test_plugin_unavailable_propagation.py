"""필수 계산 불가가 후보 정렬·확인 화면·수단 목록에서 어림값으로 바뀌지 않는다."""
from datetime import UTC, datetime, timedelta

import pytest

from app.core.team_availability import TeamUnavailable
from app.domains.travel_ops.components.intake import move_options, moves
from app.domains.travel_ops.components.planning.replan import MealRoute


@pytest.mark.parametrize("reason", ["disabled", "not_installed", "engine_unavailable"])
@pytest.mark.parametrize("surface", ["meal", "leg", "options"])
def test_unavailable_reason_survives_every_nested_calculation(reason, surface, monkeypatch):
    error = TeamUnavailable("mobility", reason)

    def unavailable(*args, **kwargs):
        raise error

    now = datetime(2026, 10, 11, 12, tzinfo=UTC)
    a = {"key": "a", "name": "출발", "lat": 37.5, "lon": 127.0}
    b = {"key": "b", "name": "도착", "lat": 37.55, "lon": 127.0}
    with pytest.raises(TeamUnavailable) as caught:
        if surface == "meal":
            route = MealRoute(planned_end=now, leg=unavailable)
            route._eta({"name": a["name"], "latitude": a["lat"], "longitude": a["lon"]},
                       {"name": b["name"], "latitude": b["lat"], "longitude": b["lon"]}, now)
        elif surface == "leg":
            moves.leg_between(unavailable, a, b, now, now + timedelta(hours=1))
        else:
            monkeypatch.setattr(move_options, "_one", unavailable)
            found = {"revision": 1, "moves": [{"from": "a", "to": "b"}],
                     "items": [{"id": "a", "date": "2026-10-11", "ends_at": "12:00",
                                "place": {"name": "출발", "latitude": 37.5, "longitude": 127.0}},
                               {"id": "b", "date": "2026-10-11", "starts_at": "13:00",
                                "place": {"name": "도착", "latitude": 37.55, "longitude": 127.0}}]}
            move_options.options(found, "a", "b", only="subway", engine_for_mode=lambda mode: unavailable)
    assert caught.value is error
