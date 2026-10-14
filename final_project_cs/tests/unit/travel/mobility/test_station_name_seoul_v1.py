"""uses 역명 — 서울역은 어느 노선 자료가 어떻게 적든 `서울역`(계약 trips.md 「지하철」). GTX-A 시간표는 「서울」로 적는다."""
from app.domains.travel_ops.components.itinerary.route_uses import problem
from app.domains.travel_ops.instances.mobility.engine.options import station_name
from app.domains.travel_ops.instances.mobility.engine.plan import uses_of


def test_seoul_station_variants_become_seoul_station():
    for nm in ("서울", "서울역", "서울역(경부선)", "서울 "):
        assert station_name(nm) == "서울역", nm


def test_other_stations_unchanged():
    assert station_name("잠실역") == "잠실"
    assert station_name("경복궁(정부서울청사)") == "경복궁"
    assert station_name("서울대입구") == "서울대입구"
    assert station_name("서울숲") == "서울숲"


def test_gtx_a_uses_pass_contract():
    legs = [{"line": "GTX-A", "from": "서울", "to": "연신내"}]
    uses = uses_of(legs)
    assert uses == ["GTX-A:서울역", "GTX-A:연신내"], uses
    assert all(problem(u) is None for u in uses), [problem(u) for u in uses]
