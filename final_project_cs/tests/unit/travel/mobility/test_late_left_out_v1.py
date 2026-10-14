# final_project_cs/tests/unit/travel/mobility/test_late_left_out_v1.py — 시각 때문에 못 맞춘 구간도 뺀 후보 이유를 싣는다
#
# 2026-10-12: 도착점이 건물 안이라 보행 접근을 검증하지 못한 도보 후보(walk_source_unavailable · unverified_walk_access)가
# 다른 후보의 시각 불성립(arrive_late)에 묻혀 결과 어디에도 남지 않았다. 후보가 아예 없을 때처럼 skipped 항목에 left_out 을 싣는다.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
sys.path.insert(0, str(HERE))

import test_plan_v1 as T  # noqa: E402
from app.domains.travel_ops.instances.mobility.engine.plan import plan  # noqa: E402


def test_arrive_late_keeps_unverified_walk_reason():
    T._skip_if_no_data()
    doc = json.loads(T.IN.read_text(encoding="utf-8"))
    places = [p for p in doc["places"] if p["key"] in ("dinner", "lotte_mart")]
    items = [it for it in doc["items"] if it["place"] in ("dinner", "lotte_mart")]
    got = plan(places, items, doc.get("party_size"), doc.get("constraints"), runtime=T._runtime(), modes=T.MODES)
    assert not got["routes"], got["routes"]
    skipped = got["skipped"]
    assert len(skipped) == 1 and skipped[0]["code"] == "arrive_late", skipped
    walk = [x for x in skipped[0].get("left_out", []) if x["label"] == "도보"]
    assert len(walk) == 1, skipped[0]
    assert walk[0]["code"] == "walk_source_unavailable"
    assert walk[0]["walk_basis"] == {"source": "walking_network", "status": "unavailable",
                                     "reason": "unverified_walk_access"}
    assert all("_o" not in x for x in skipped[0]["left_out"]), "내부 참조가 결과로 나갔다"
