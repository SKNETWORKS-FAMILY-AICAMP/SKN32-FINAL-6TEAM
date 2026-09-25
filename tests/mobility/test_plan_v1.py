# tests/mobility/test_plan_v1.py — 32번 방 · 값 내놓기(plan) 시험
# 실행: 저장소 루트에서
#   $env:PYTHONPATH = "final_project_cs"
#   python tests/mobility/test_plan_v1.py          # 단위 + (시간표가 있으면) 예시 골든 대조
#   python -m pytest tests/mobility/test_plan_v1.py
# 실패하면 종료코드 1.
#
# 축
#   U  단위 — 운행일(45 계약)·시각 표기·uses 표기(9/24)·party 매핑. 데이터 없이 돈다
#   G  골든 — 예시 입력 → 예시 출력(basis 제외)이 바이트 단위로 같다. 시간표가 바뀌면 여기서 걸린다(의도)
#   K  계약 — 코어로 나가는 키가 기존 칸뿐(새 키 0) · 금지 키 0 · ends−starts = 계획 수단 eta_min
#   T  시각 — ends + @ ≤ 다음 항목 시작 · starts 에서 다시 판정하면 성립(역산 시각이 참인지)
#   C  코어 판정 — 팀 itinerary_checks.check_itinerary 가 위반 0 (등록에서 안 걸린다)
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "final_project_cs"))

from app.modules.travel_ops.mobility_engine.plan import (  # noqa: E402
    iso_of, label_of, line_name, party_of, plan, service_day, station_name, uses_of)

KST = timezone(timedelta(hours=9))
IN = HERE / "plan_example_in_v1.json"
GOLD = HERE / "plan_example_out_v1.json"
MODES = ["subway", "walk"]           # 골든은 지하철·도보로 뽑았다(노트북 버스 데이터가 옛 판 · 41 뒤 재추출)

ITEM_KEYS = {"seq", "kind", "title", "place", "starts_at", "ends_at", "route", "detail"}   # trip_api.ItemIn
ROUTE_KEYS = {"from", "to", "planned", "options"}                                        # 스펙 v1.3
OPTION_KEYS = {"id", "label", "eta_min", "uses"}                                         # 스펙 v1.3
FORBIDDEN = {"last_feasible_depart", "last_feasible_depart_min", "grade", "verdict", "code", "reason",
             "relief", "slack_min", "margin_min", "buffer_min", "p90_eta_min", "p95_eta_min",
             "average_eta_min", "recommend_depart_at", "basis", "modes", "legs"}


# ── U 단위 ────────────────────────────────────────────────────────────────
def test_service_day():
    d, m = service_day(datetime(2026, 9, 30, 0, 30, tzinfo=KST))
    assert (d, m) == (date(2026, 9, 29), 1470), "04:00 전은 전날 운행일의 24:xx (45 계약)"
    d, m = service_day(datetime(2026, 9, 30, 4, 0, tzinfo=KST))
    assert (d, m) == (date(2026, 9, 30), 240), "04:00 은 그날 운행일"
    d, m = service_day(datetime(2026, 9, 30, 3, 59, tzinfo=KST))
    assert (d, m) == (date(2026, 9, 29), 1679)


def test_iso_of():
    assert iso_of(date(2026, 9, 29), 1470) == "2026-09-30T00:30:00+09:00", "24:30 은 다음 날 벽시계"
    assert iso_of(date(2026, 9, 29), 558) == "2026-09-29T09:18:00+09:00"
    for m in (240, 700, 1439, 1440, 1500, 1679):
        dt = datetime.fromisoformat(iso_of(date(2026, 9, 29), m))
        assert service_day(dt) == (date(2026, 9, 29), m), f"왕복 {m}"


def test_names():
    assert line_name("02호선") == "2호선"
    assert line_name("09호선") == "9호선"
    assert line_name("경의선") == "경의중앙선"
    assert line_name("공항철도") == "공항철도"
    assert line_name("인천2호선") == "인천2호선", "숫자 두 자리 + 호선 만 줄인다"
    assert station_name("잠실역") == "잠실"
    assert station_name("경복궁(정부서울청사)") == "경복궁"
    assert station_name("서울역") == "서울역"
    assert station_name("역삼") == "역삼", "「역」으로 끝나지 않으면 그대로"


def test_uses():
    legs = [{"line": "03호선", "from": "경복궁", "to": "을지로3가"},
            {"line": "02호선", "from": "을지로3가", "to": "성수"}]
    assert uses_of(legs) == ["3호선:경복궁", "3호선:을지로3가", "2호선:을지로3가", "2호선:성수"], \
        "탄·갈아탄·내린 역만 · 환승역은 두 노선 각각"
    assert uses_of([{"mode": "bus", "route": "2224", "from": "a", "to": "b"}]) == ["버스:2224"]
    assert uses_of([{"mode": "bike", "from": "a", "to": "b"}]) == []
    assert label_of(legs) == "3호선 경복궁→을지로3가 → 2호선 을지로3가→성수"


def test_party():
    assert party_of(2, {}) == {"size": 2}
    assert party_of(None, {"mobility_ease": "needs_rest"}) == {"fatigue_high": True}
    assert party_of(1, {"mobility_ease": "ok"}) == {"size": 1}


# ── 데이터가 필요한 축 ──────────────────────────────────────────────────────
_RT = None


def _runtime():
    global _RT
    if _RT is None:
        from app.modules.travel_ops.mobility_engine.runtime import build_verifier
        try:
            _RT = build_verifier(quiet=True)
        except RuntimeError as e:          # 시간표가 없는 기기 — 데이터 축은 SKIP
            _RT = e
    return None if isinstance(_RT, Exception) else _RT


def _skip_if_no_data():
    if _runtime() is None:
        try:
            import pytest
            pytest.skip("시간표 없음(DATA_DIR) — 데이터 축 SKIP")
        except ImportError:
            raise _Skip()


class _Skip(Exception):
    pass


def _run(trace=None):
    doc = json.loads(IN.read_text(encoding="utf-8"))
    return doc, plan(doc["places"], doc["items"], doc.get("party_size"), doc.get("constraints"),
                     runtime=_runtime(), modes=MODES, trace=trace)


def _walk_keys(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k, path
            yield from _walk_keys(v, f"{path}.{k}")
    elif isinstance(x, list):
        for v in x:
            yield from _walk_keys(v, path)


def test_golden():
    _skip_if_no_data()
    _, got = _run()
    got.pop("basis")
    want = json.loads(GOLD.read_text(encoding="utf-8"))
    assert got == want, "예시 출력이 골든과 다르다 — 시간표·규칙이 바뀌었으면 골든을 다시 뽑고 이유를 적는다"


def test_contract_keys():
    _skip_if_no_data()
    _, got = _run()
    for it in got["items"]:
        assert set(it) <= ITEM_KEYS, f"ItemIn 에 없는 키: {set(it) - ITEM_KEYS}"
    for key, r in got["routes"].items():
        assert set(r) == ROUTE_KEYS, f"{key}: {set(r) ^ ROUTE_KEYS}"
        assert r["planned"] in {o["id"] for o in r["options"]}
        for o in r["options"]:
            assert set(o) == OPTION_KEYS, f"{key}/{o.get('id')}: {set(o) ^ OPTION_KEYS}"
            assert isinstance(o["eta_min"], int) and o["eta_min"] > 0
    bad = [(k, p) for k, p in _walk_keys({"items": got["items"], "routes": got["routes"]}) if k in FORBIDDEN]
    assert not bad, f"코어로 나가면 안 되는 키: {bad}"
    mob = [it for it in got["items"] if it["kind"] == "mobility"]
    for it in mob:
        assert it["route"] in got["routes"]
        for k in ("starts_at", "ends_at"):
            assert it[k].endswith(":00+09:00"), f"시각 표기 {it[k]}"
        r = got["routes"][it["route"]]
        eta = next(o["eta_min"] for o in r["options"] if o["id"] == r["planned"])
        s, e = datetime.fromisoformat(it["starts_at"]), datetime.fromisoformat(it["ends_at"])
        assert (e - s) == timedelta(minutes=eta), "ends − starts = 계획 수단 eta_min"
    assert [it["seq"] for it in got["items"]] == list(range(1, len(got["items"]) + 1))


def test_times_hold():
    _skip_if_no_data()
    tr = []
    doc, got = _run(trace=tr)
    items = got["items"]
    for i, it in enumerate(items):
        if it["kind"] != "mobility":
            continue
        nxt = datetime.fromisoformat(items[i + 1]["starts_at"])
        t = next(x for x in tr if x["route"] == it["route"])
        p = next(o for o in t["options"] if o["id"] == t["planned"])
        assert p["slack_min"] >= 0, "slack 음수 = 늦는다"
        e = datetime.fromisoformat(it["ends_at"])
        assert e + timedelta(minutes=p["margin_min"] + p["slack_min"]) == nxt, \
            "starts = 목표 − (eta + @) − slack  (slack ≥ 0)"
        assert s_ok(it, items[i - 1]), "앞 항목이 끝나기 전에 떠나라는 값이면 예시가 틀렸다(예시에서는 없어야 한다)"


def s_ok(mob, prev):
    s = datetime.fromisoformat(mob["starts_at"])
    pe = datetime.fromisoformat(prev.get("ends_at") or prev["starts_at"])
    return s >= pe


def test_core_itinerary_checks():
    _skip_if_no_data()
    from app.modules.travel_ops.itinerary_checks import Part, check_itinerary
    doc, got = _run()
    places = {p["key"]: p for p in doc["places"]}
    parts = [Part(seq=it["seq"], kind=it["kind"], title=it["title"],
                  starts_at=datetime.fromisoformat(it["starts_at"]),
                  ends_at=datetime.fromisoformat(it["ends_at"]) if it.get("ends_at") else None,
                  place=places.get(it.get("place")), route=got["routes"].get(it.get("route")))
             for it in got["items"]]
    v = check_itinerary(parts, constraints=doc.get("constraints"), party_size=doc.get("party_size"))
    assert not v, f"코어 등록 판정 위반: {[x.as_dict() for x in v]}"


def test_skip_no_station():
    _skip_if_no_data()
    places = [{"key": "g", "name": "경복궁", "kind": "activity", "lat": 37.5796, "lon": 126.977},
              {"key": "j", "name": "제주", "kind": "activity", "lat": 33.5, "lon": 126.5}]
    items = [{"seq": 1, "kind": "activity", "title": "A", "place": "g",
              "starts_at": "2026-09-29T10:00:00+09:00", "ends_at": "2026-09-29T11:00:00+09:00"},
             {"seq": 2, "kind": "activity", "title": "B", "place": "j", "starts_at": "2026-09-29T15:00:00+09:00"}]
    got = plan(places, items, 1, {}, runtime=_runtime(), modes=MODES)
    assert [it["kind"] for it in got["items"]] == ["activity", "activity"], "모르면 이동 항목을 안 만든다"
    assert got["routes"] == {}
    assert got["skipped"] and got["skipped"][0]["code"] == "no_data"


def test_night_service_day():
    """자정 넘는 도착 목표 — 운행일 9/29 의 24:30. 이동 항목 시각은 벽시계(+1일)로 나간다."""
    _skip_if_no_data()
    places = [{"key": "g", "name": "경복궁", "kind": "activity", "lat": 37.5796, "lon": 126.977},
              {"key": "s", "name": "성수", "kind": "activity", "lat": 37.5445, "lon": 127.056}]
    items = [{"seq": 1, "kind": "activity", "title": "A", "place": "g",
              "starts_at": "2026-09-29T22:30:00+09:00", "ends_at": "2026-09-29T23:30:00+09:00"},
             {"seq": 2, "kind": "activity", "title": "B", "place": "s", "starts_at": "2026-09-30T00:30:00+09:00"}]
    tr = []
    got = plan(places, items, 1, {}, runtime=_runtime(), modes=MODES, trace=tr)
    assert tr and tr[0]["date"] == "2026-09-29" and tr[0]["arrive_by_min"] == 1470, "case.date = 운행일"
    mob = [it for it in got["items"] if it["kind"] == "mobility"]
    assert len(mob) == 1
    s, e = datetime.fromisoformat(mob[0]["starts_at"]), datetime.fromisoformat(mob[0]["ends_at"])
    assert s < e <= datetime(2026, 9, 30, 0, 30, tzinfo=KST)


_GS = [{"key": "g", "name": "경복궁", "kind": "activity", "lat": 37.5796, "lon": 126.977},
       {"key": "s", "name": "성수", "kind": "activity", "lat": 37.5445, "lon": 127.056}]


def _two(t0, t1, t2):
    return [{"seq": 1, "kind": "activity", "title": "A", "place": "g", "starts_at": t0, "ends_at": t1},
            {"seq": 2, "kind": "activity", "title": "B", "place": "s", "starts_at": t2}]


def test_0400_boundary():
    """자체 대조 #1 — 도착 목표 04:00 에서 역 도보를 빼면 전 운행일(27:5x)이다. 정수 분을 그대로 넘기면
    판정기가 240 미만을 +24h 로 읽어 그날 밤 막차(20시간 뒤)를 내던 결함. 이제는 목표보다 늦은 출발이 나오면 안 된다."""
    _skip_if_no_data()
    got = plan(_GS, _two("2026-09-28T22:00:00+09:00", "2026-09-28T23:00:00+09:00", "2026-09-29T04:00:00+09:00"),
               1, {}, runtime=_runtime(), modes=MODES)
    mob = [it for it in got["items"] if it["kind"] == "mobility"]
    assert len(mob) == 1, got["skipped"]
    s, e = datetime.fromisoformat(mob[0]["starts_at"]), datetime.fromisoformat(mob[0]["ends_at"])
    assert datetime(2026, 9, 28, 23, 0, tzinfo=KST) <= s < e <= datetime(2026, 9, 29, 4, 0, tzinfo=KST), \
        f"전 운행일 막차(24:xx)로 가야 한다 — 받은 값 {mob[0]}"
    assert any(it["kind"] == "mobility" for it in got["items"]) or got["skipped"]


def test_not_before_prev_end():
    """자체 대조 #2 — 앞 항목이 끝나기 전에 떠나라는 값은 코어 등록이 overlap 으로 거절한다 → 싣지 않고 skipped."""
    _skip_if_no_data()
    got = plan(_GS, _two("2026-09-29T10:00:00+09:00", "2026-09-29T11:00:00+09:00", "2026-09-29T11:10:00+09:00"),
               1, {}, runtime=_runtime(), modes=MODES)
    assert not any(it["kind"] == "mobility" for it in got["items"])
    assert got["skipped"] and got["skipped"][0]["code"] == "arrive_late"


def test_keep_input_move_when_skipped():
    """자체 대조 #6 — 우리가 못 만든 구간의 입력 이동 항목은 그대로 남는다. 만든 구간의 것은 우리 값으로 바뀐다."""
    _skip_if_no_data()
    tight = _two("2026-09-29T10:00:00+09:00", "2026-09-29T11:00:00+09:00", "2026-09-29T11:10:00+09:00")
    tight.append({"seq": 3, "kind": "mobility", "title": "택시", "route": "taxi_g_s",
                  "starts_at": "2026-09-29T11:00:00+09:00", "ends_at": "2026-09-29T11:10:00+09:00"})
    got = plan(_GS, tight, 1, {}, runtime=_runtime(), modes=MODES)
    assert [it.get("route") for it in got["items"] if it["kind"] == "mobility"] == ["taxi_g_s"]
    loose = _two("2026-09-29T10:00:00+09:00", "2026-09-29T11:00:00+09:00", "2026-09-29T13:00:00+09:00")
    loose.append(dict(tight[-1]))
    got = plan(_GS, loose, 1, {}, runtime=_runtime(), modes=MODES)
    assert [it.get("route") for it in got["items"] if it["kind"] == "mobility"] == ["g_to_s"]


if __name__ == "__main__":
    fails, skips, n = 0, 0, 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            n += 1
            try:
                fn()
                print(f"  ok   {name}")
            except _Skip:
                skips += 1
                print(f"  SKIP {name}")
            except AssertionError as e:
                fails += 1
                print(f"  FAIL {name}: {e}")
    print(f"[plan] {n - fails - skips}/{n} 통과 · SKIP {skips} · 실패 {fails}")
    sys.exit(1 if fails else 0)
