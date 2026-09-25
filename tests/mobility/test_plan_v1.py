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


def _recheck(got, tr, doc_items, party_size=None, constraints=None, stage="planning"):
    """출력 기준으로 다시 본다(GPT 2차 #2) — 출력 options 와 trace 후보 ID 집합이 같고, 출력 eta_min 이 판정기를
    **따로** 불러 낸 소요(+장소·정류장 도보)와 같고, 도착 목표는 원본 다음 일정 starts_at 에서 가져온다.
    재판정에는 원래 party·first_visit·stage 를 그대로 넘긴다."""
    v = _runtime()._v
    constraints = dict(constraints or {})
    party = party_of(party_size, constraints)
    fv = constraints.get("first_visit", True)
    stays = sorted((x for x in doc_items if x.get("kind") != "mobility"),
                   key=lambda x: datetime.fromisoformat(x["starts_at"]))
    n = 0
    items = got["items"]
    for i, it in enumerate(items):
        if it["kind"] != "mobility":
            continue
        t = next(x for x in tr if x["route"] == it["route"])
        out_opts = {o["id"]: o for o in got["routes"][it["route"]]["options"]}
        assert set(out_opts) == {o["id"] for o in t["options"]}, "출력 options 와 판정한 후보가 다르다"
        nxt = next(x for x in stays if x["title"] == items[i + 1]["title"])   # 원본 다음 일정
        sdate = date.fromisoformat(t["date"])
        d, m = service_day(datetime.fromisoformat(nxt["starts_at"]))
        arrive_by = m + (d - sdate).days * 1440
        d, m = service_day(datetime.fromisoformat(it["starts_at"]))
        start_min = m + (d - sdate).days * 1440
        for o in t["options"]:
            eta_out = out_opts[o["id"]]["eta_min"]
            ck = o.get("check")
            if ck is None:                          # 도보 — 출발 + 소요 + 버퍼 ≤ 목표
                assert eta_out == o["eta_min"]
                assert start_min + eta_out + v.rv("buffer", "by_stage", stage) <= arrive_by
                continue
            dep = start_min + ck["walk_place_in"] - ck["off"] + ck["walk_stop_in"]
            by_station = arrive_by - ck["walk_place_out"] - ck["off"]
            r = v.verify_case({"id": f"recheck/{it['route']}/{o['id']}", "date": ck["date"], "legs": ck["legs"],
                               "depart_at": dep, "arrive_by": by_station - ck["walk_stop_out"],
                               "stage": stage, "party": party, "first_visit": fv, "no_alternatives": True})
            assert r.out["verdict"] == "feasible" and r.out.get("slack_min", -1) >= 0, \
                f"{it['route']}/{o['id']} 가 출력 출발 시각에서 성립하지 않는다: {r.out}"
            eta_indep = (ck["walk_place_in"] + ck["walk_stop_in"] + r.out["eta_min"]
                         + ck["walk_stop_out"] + ck["walk_place_out"])
            assert eta_out == eta_indep, f"{it['route']}/{o['id']}: 출력 eta {eta_out} ≠ 따로 잰 {eta_indep}"
            n += 1
    return n


def test_independent_recheck():
    """GPT #5 — 출력된 starts_at 에서 판정기를 **따로** 불러 성립을 본다(trace 등식에 기대지 않는다).
    GPT #1 — options 에 남은 후보 전부가 그 한 출발 시각에서 성립해야 한다. 자정 가까운 경복궁→성수는
    후보마다 마지막 성립 출발이 다르다(23:42 · 23:32) — 더 일찍 떠나야 하는 후보는 options 에 남으면 안 된다."""
    _skip_if_no_data()
    tr = []
    doc, got = _run(trace=tr)
    n = _recheck(got, tr, doc["items"], doc.get("party_size"), doc.get("constraints"))
    tr = []
    night = _two("2026-09-29T22:30:00+09:00", "2026-09-29T23:30:00+09:00", "2026-09-30T00:30:00+09:00")
    got = plan(_GS, night, 1, {}, runtime=_runtime(), modes=MODES, trace=tr)
    n += _recheck(got, tr, night, 1, {})
    assert n >= 4


def test_route_key_reserved():
    """GPT #2 — 남겨 둔 입력 이동 항목·호출 쪽 routes 의 키를 새 경로가 덮지 않는다."""
    _skip_if_no_data()
    items = _two("2026-09-29T10:00:00+09:00", "2026-09-29T11:00:00+09:00", "2026-09-29T13:00:00+09:00")
    items.append({"seq": 9, "kind": "activity", "title": "C", "place": "s",
                  "starts_at": "2026-09-29T15:00:00+09:00"})
    items.append({"seq": 10, "kind": "mobility", "title": "옛 이동", "route": "g_to_s",
                  "starts_at": "2026-09-29T14:00:00+09:00", "ends_at": "2026-09-29T14:10:00+09:00"})
    got = plan(_GS, items, 1, {}, runtime=_runtime(), modes=MODES, routes={"g_to_s_2": {}})
    assert "g_to_s" not in got["routes"] and "g_to_s_2" not in got["routes"], list(got["routes"])
    keys = [it.get("route") for it in got["items"] if it["kind"] == "mobility"]
    assert "g_to_s" in keys, "같은 장소 사이의 입력 이동 항목은 남는다"


def test_recheck_catches_tampering():
    """_recheck 자신의 실패 장면 — 출력 eta 를 바꾸거나 후보를 끼워 넣으면 잡아야 한다(GPT 2차 #2 재현)."""
    _skip_if_no_data()
    import copy
    tr = []
    doc, got = _run(trace=tr)
    key = next(it["route"] for it in got["items"] if it["kind"] == "mobility" and it["route"] != "dinner_to_lotte_mart")
    for tamper in ("eta", "extra"):
        g = copy.deepcopy(got)
        opts = g["routes"][key]["options"]
        if tamper == "eta":
            opts[0]["eta_min"] = 999
        else:
            opts.append({"id": "fake", "label": "가짜", "eta_min": 1, "uses": []})
        try:
            _recheck(g, tr, doc["items"], doc.get("party_size"), doc.get("constraints"))
        except AssertionError:
            continue
        raise AssertionError(f"_recheck 가 {tamper} 변조를 못 잡았다")


def test_cli_passes_routes():
    """GPT 2차 #1 — CLI(plan_doc)도 입력의 기존 routes 키를 새 키로 안 쓴다 · 함수 호출과 결과가 같다."""
    _skip_if_no_data()
    from app.modules.travel_ops.mobility_engine.plan import plan_doc
    doc = {"places": _GS, "items": _two("2026-09-29T10:00:00+09:00", "2026-09-29T11:00:00+09:00",
                                        "2026-09-29T13:00:00+09:00"),
           "party_size": 1, "constraints": {}, "routes": {"g_to_s": {"from": "옛", "to": "옛", "planned": "x",
                                                                      "options": []}}}
    by_cli = plan_doc(doc, runtime=_runtime(), modes=MODES)
    by_fn = plan(doc["places"], doc["items"], 1, {}, runtime=_runtime(), modes=MODES, routes=doc["routes"])
    assert "g_to_s" not in by_cli["routes"] and list(by_cli["routes"]) == ["g_to_s_2"], list(by_cli["routes"])
    for r in (by_cli, by_fn):
        r.pop("basis")
    assert by_cli == by_fn


def test_not_before_seconds():
    """GPT #3 — 앞 항목이 09:47:30 에 끝나면 09:47 출발은 겹친다. 하한은 분 올림."""
    _skip_if_no_data()
    got = plan(_GS, _two("2026-09-29T09:00:00+09:00", "2026-09-29T10:00:00+09:00", "2026-09-29T11:00:00+09:00"),
               1, {}, runtime=_runtime(), modes=MODES)
    mob = [it for it in got["items"] if it["kind"] == "mobility"]
    assert mob, got["skipped"]
    s = datetime.fromisoformat(mob[0]["starts_at"])
    end_sec = (s + timedelta(seconds=30)).isoformat()          # 이동 출발 30초 뒤에 앞 항목이 끝나게
    got = plan(_GS, _two("2026-09-29T09:00:00+09:00", end_sec, "2026-09-29T11:00:00+09:00"),
               1, {}, runtime=_runtime(), modes=MODES)
    for it in got["items"]:
        if it["kind"] == "mobility":
            assert datetime.fromisoformat(it["starts_at"]) >= datetime.fromisoformat(end_sec), it


def test_leading_and_only_moves_kept():
    """GPT #4 — 첫 비이동 항목보다 앞선 입력 이동 · 이동 항목만 있는 입력은 사라지지 않는다."""
    _skip_if_no_data()
    mv = {"seq": 1, "kind": "mobility", "title": "공항 → 호텔", "route": "airport",
          "starts_at": "2026-09-29T08:00:00+09:00", "ends_at": "2026-09-29T08:50:00+09:00"}
    act = {"seq": 2, "kind": "activity", "title": "A", "place": "g", "starts_at": "2026-09-29T09:00:00+09:00"}
    got = plan(_GS, [mv, act], 1, {}, runtime=_runtime(), modes=MODES)
    assert [it["title"] for it in got["items"]] == ["공항 → 호텔", "A"]
    got = plan(_GS, [mv], 1, {}, runtime=_runtime(), modes=MODES)
    assert [it["title"] for it in got["items"]] == ["공항 → 호텔"]


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
