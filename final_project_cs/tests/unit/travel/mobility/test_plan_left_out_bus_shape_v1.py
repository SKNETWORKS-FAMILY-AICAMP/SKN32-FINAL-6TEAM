"""버스 환승 제외 후보를 직행 수에 합치지 않는 표시 경계."""
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine.plan import Planner


def _entry(label, count, code="before_prev_end"):
    return {"label": label, "code": code, "reason": "개발 표본",
            "_o": {"_legs": [{"mode": "bus"}] * count, "_walk_m": 100, "_n": 0}}


def test_bus_transfer_is_not_folded_into_direct_bus_count():
    planner = object.__new__(Planner)
    planner.v = SimpleNamespace(R={"candidates": {"버스_직행_최대": {"value": 1}}})
    left = [_entry("직행 A", 1), _entry("직행 B", 1), _entry("버스 환승", 2, "mix_dominated")]
    got = planner._fold_left(left)
    assert [entry["label"] for entry in got] == ["직행 A", "버스 환승", "그 밖 버스 직행 1개"]
    assert got[-1]["reason"] == "도보 긴 쪽 — before_prev_end 1"
    assert all("_o" not in entry for entry in got)


def test_only_bus_transfers_remain_individual_entries():
    planner = object.__new__(Planner)
    planner.v = SimpleNamespace(R={"candidates": {"버스_직행_최대": {"value": 1}}})
    got = planner._fold_left([_entry("환승 A", 2), _entry("환승 B", 3)])
    assert [entry["label"] for entry in got] == ["환승 A", "환승 B"]
    assert all(entry["code"] != "bus_more" for entry in got)
