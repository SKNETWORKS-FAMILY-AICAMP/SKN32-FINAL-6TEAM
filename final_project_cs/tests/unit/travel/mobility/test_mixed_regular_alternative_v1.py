"""추가운임 없는 혼합 대안도 실제 그래프 탐색과 기존 상한을 따른다."""
import copy
import json
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine.candidates import CandidateGraph, MixedCandidate, MixedGenerator
from app.domains.travel_ops.instances.mobility.engine.paths import RULES_DIR


def build(*, ratio=1.5, avoid=()):
    rules = json.loads((RULES_DIR / "rules_v0.3.json").read_text(encoding="utf-8"))
    rules["fare"]["subway"]["special_lines"] = {"Premium": {}}
    rules["candidates"]["허용_소요_배수"]["value"] = ratio
    lines = {
        "Premium": {"stations": [{"station_nm": x} for x in ("A", "B")],
                    "edges": [{"a": "A", "b": "B", "travel_min": 1}]},
        "Normal": {"stations": [{"station_nm": x} for x in ("A", "C")],
                   "edges": [{"a": "A", "b": "C", "travel_min": 3}]},
        "Shared": {"stations": [{"station_nm": x} for x in ("B", "C", "D")],
                   "edges": [{"a": "B", "b": "D", "travel_min": 1},
                             {"a": "C", "b": "D", "travel_min": 3}]},
    }
    cg = CandidateGraph(SimpleNamespace(doc={"lines": lines}), None, rules, False)
    g = MixedGenerator(cg, None, None, None, radius_m=500, near_m=500, cuts=3, tlim=2,
                       avoid_lines=avoid)
    fast = cg.search("A", "D", "최단", 1, origin_lines=["Premium", "Normal"], dest_lines=["Shared"])
    c = MixedCandidate("B", [{"mode": "bus", "route": "R", "from": "D앞", "to": "목적지"}],
                       fast.est_min + 10, 1, 0, 0, 0, "R", "D", None, 0, "추정")
    c._rank, c._sub_lines, c._tg = fast.est_min, ["Shared"], [("A", {"Premium", "Normal"}, 0)]
    assert g.materialize(c)
    return g, c


def test_regular_alternative_preserves_fastest_and_same_bus():
    g, fastest = build()
    before = copy.deepcopy(fastest.legs)
    regular = g.regular_alternative(fastest)
    assert regular is not None
    assert fastest.legs == before
    assert [x.get("line") for x in fastest.legs[:-1]] == ["Premium", "Shared"]
    assert [x.get("line") for x in regular.legs[:-1]] == ["Normal", "Shared"]
    assert regular.legs[-1] == fastest.legs[-1]
    assert regular.transfers == fastest.transfers == 2
    assert fastest.est_min < regular.est_min <= fastest.est_min * 1.5
    assert g.regular_alternative(regular) is None


def test_regular_alternative_respects_time_ratio():
    g, fastest = build(ratio=1.01)
    assert g.regular_alternative(fastest) is None


def test_regular_alternative_preserves_disruption_avoidance():
    g, fastest = build(avoid={"Normal"})
    assert g.regular_alternative(fastest) is None


def test_regular_alternative_only_when_existing_policy_has_extra_fare():
    g, fastest = build()
    g.cg.R["fare"]["subway"]["special_lines"] = {}
    assert g.regular_alternative(fastest) is None


def test_regular_alternative_respects_transfer_cap():
    g, fastest = build()
    g.tlim = 1
    assert g.regular_alternative(fastest) is None


def test_planner_inserts_regular_once_and_keeps_verification_cap():
    from app.domains.travel_ops.instances.mobility.engine import plan as P
    g, fastest = build()
    candidates = [copy.copy(fastest) for _ in range(6)]
    g.bus_to_subway = lambda *a, **k: []
    g.subway_to_bus = lambda *a, **k: candidates
    g.bus_to_bus = lambda *a, **k: []
    pl = P.Planner.__new__(P.Planner)
    pl.modes = {"bus", "subway"}
    pl.v = SimpleNamespace(R=g.cg.R)
    pl.speed, pl.detour = 1.04, 1.4
    pl._mix_gen = lambda *a, **k: g
    pl._phys_set = lambda _: set()
    pl._in_service = lambda *a: True
    verified = []
    def verify(mc, i, *a, **k):
        verified.append(mc)
        return {"eta_min": mc.est_min, "_legs": mc.legs}, None
    pl._mixed_one = verify
    got = pl._mixed({"lat": 0, "lon": 0}, {"lat": 0, "lon": 0}, [("A", 0, None)], [],
                    None, None, 600, {}, False, "public-mix", 1200, [], [])
    assert len(got) == len(verified) == P.MIX_VERIFY_MAX
    assert verified[0].legs == fastest.legs
    assert sum(bool(getattr(c, "_regular_variant", False)) for c in verified) == 1
    assert verified[1].legs[0]["line"] == "Normal"


def test_regular_alternative_updates_bus_board_window_hint_only_for_rail_first():
    g, fastest = build()
    fastest.bus_board_offsets = [fastest._materialized_rank + 5]
    before = list(fastest.bus_board_offsets)
    regular = g.regular_alternative(fastest)
    assert regular.bus_board_offsets == [regular._materialized_rank + 5]
    assert fastest.bus_board_offsets == before
    assert regular.bus_board_offsets[0] > before[0]
