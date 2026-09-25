# tests/mobility/test_plan_estimate_v1.py — 48번 방 · 계획용 이동 추정(P1) 시험
# 실행: 저장소 루트에서
#   $env:PYTHONPATH = "final_project_cs"
#   python tests/mobility/test_plan_estimate_v1.py      # 단위 + (시간표가 있으면) 데이터 축
#   python -m pytest tests/mobility/test_plan_estimate_v1.py
# 실패하면 종료코드 1.
#
# 축
#   U  단위 — 날짜 유형(우리 달력) · 분위(최근순위) · 시간대 창. 데이터 없이 돈다
#   D  데이터 — 실제 시간표·버스 프로파일·혼잡도로 추정을 돌려 성질을 본다
#      · 범위 순서 p10 ≤ p50 ≤ p90 ≤ worst_max · 여유 키 0
#      · 독립 재판정 — 표본의 경로를 판정기에 **legs 케이스로 따로** 넣어 같은 소요가 나오는가
#      · 공휴일(추석)은 일요일과 같은 판(시간표·혼잡도 요일축) · 일요일엔 출퇴근 주의가 없다
#      · 버스 범위는 구간 프로파일 p10/p90 · 막차(경로 기준 + 뒤를 잇는 경로 · 버스 막차) · 첫차 · 판정기 상태 무변경
#      · 토요일 재차율 ≥100 셀은 출퇴근 주의가 아니다
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "final_project_cs"))

from app.modules.travel_ops.mobility_engine.plan_estimate import (  # noqa: E402
    Estimator, day_info, estimate, pct, slot_window)

HOTEL = {"name": "명동 호텔", "lat": 37.5636, "lon": 126.9826}           # 32 예시와 같은 장소
SEONGSU = {"name": "성수 쇼룸", "lat": 37.5445, "lon": 127.056}
WEEKDAY, SUNDAY, CHUSEOK = "2026-09-29", "2026-09-27", "2026-09-25"
NO_MARGIN = {"margin_min", "slack_min", "buffer_min", "last_feasible_depart_min", "arrive_by_min"}

_RT, _CACHE = None, {}


class _Skip(Exception):
    pass


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


def _est(frm, to, d, slot, **kw):
    key = (str(frm), str(to), d, slot, tuple(sorted((k, str(v)) for k, v in kw.items())))
    if key not in _CACHE:
        sm = []
        r = estimate(frm, to, d, slot, runtime=_runtime(), samples=sm, **kw)
        _CACHE[key] = (r, sm)
    return _CACHE[key]


def _keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from _keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from _keys(v)


# ── U 단위 ────────────────────────────────────────────────────────────────
def test_day_info():
    x = day_info(date(2026, 9, 25))
    assert (x["kind"], x["holiday_name"], x["timetable"], x["congestion"]) == ("공휴일", "추석", "holiday", "sunday")
    x = day_info(date(2026, 9, 26))
    assert (x["weekday"], x["kind"], x["congestion"]) == ("토", "공휴일", "sunday"), "토요일과 겹친 공휴일은 공휴일(혼잡도 sunday)"
    x = day_info(date(2026, 10, 10))
    assert (x["kind"], x["timetable"], x["congestion"]) == ("토요일", "holiday", "saturday")
    x = day_info(date(2026, 9, 29))
    assert (x["kind"], x["timetable"], x["congestion"], x["in_calendar"]) == ("평일", "weekday", "weekday", True)
    assert "holiday_name" not in x
    assert day_info(date(2028, 1, 3))["in_calendar"] is False, "공휴일 표가 덮지 않는 해는 표시한다"


def test_pct():
    xs = list(range(1, 11))
    assert (pct(xs, 0.1), pct(xs, 0.5), pct(xs, 0.9)) == (1, 5, 9), "최근순위 — ceil(q·n) 번째"
    assert pct([], 0.5) is None
    assert pct([7], 0.1) == pct([7], 0.9) == 7
    assert pct([3, None, 1], 0.5) == 1


def test_slot_window():
    assert slot_window("오전") == ("오전", (360, 720))
    assert slot_window("night") == ("밤", (1320, 1680)), "밤은 운행일 끝(28:00)까지"
    try:
        slot_window("새벽")
    except ValueError:
        pass
    else:
        raise AssertionError("모르는 시간대는 멈춘다")


# ── D 데이터 ─────────────────────────────────────────────────────────────
def test_order_and_no_margin():
    _skip_if_no_data()
    for args in [(HOTEL, SEONGSU, WEEKDAY, "오후"), ("서울역", "이태원", WEEKDAY, "오후"), ("사당", "강남", WEEKDAY, "오전")]:
        r, _ = _est(*args)
        e = r["eta"]
        assert r["verdict"] == "feasible"
        assert e["p10_min"] <= e["p50_min"] <= e["p90_min"] <= e["worst_max_min"], f"범위 순서 {args[:2]} {e}"
        assert not (set(_keys(r)) & NO_MARGIN), f"여유 키가 새었다: {set(_keys(r)) & NO_MARGIN}"
        assert r["window"]["n"] == len(range(*slot_window(args[3])[1], 5))


def test_recheck_independent():
    """표본의 경로를 legs 케이스로 판정기에 따로 넣는다 — 같은 출발 시각에서 같은 예정 소요가 나와야 한다."""
    _skip_if_no_data()
    rt = _runtime()
    r, sm = _est(HOTEL, SEONGSU, WEEKDAY, "오후")
    E = Estimator(rt)
    wl = rt._v._walk_limit({})
    wa, wb = E._point(HOTEL, wl)["walk"], E._point(SEONGSU, wl)["walk"]
    got = []
    for x in sm[::7]:
        o = rt._v.verify_case({"id": "re", "date": WEEKDAY, "depart_at": x["t"] + wa, "legs": x["legs"],
                               "no_alternatives": True}).out
        assert o["verdict"] == "feasible", x
        assert wa + o["eta_min"] + wb == x["eta"], f"{x['t']} 재판정 {wa + o['eta_min'] + wb} ≠ 표본 {x['eta']}"
        assert wa + o["eta_worst_min"] + wb == x["worst"]
        got.append(x["eta"])
    assert got, "재판정 표본이 없다"
    assert r["eta"]["p50_min"] == pct([x["eta"] for x in sm if x["choice"]], 0.5)


def test_holiday_is_sunday_board():
    """추석(금)은 시간표·혼잡도 모두 일요일 판 — 같은 경로·같은 창이면 일요일과 값이 같다."""
    _skip_if_no_data()
    a, _ = _est(HOTEL, SEONGSU, CHUSEOK, "저녁")
    b, _ = _est(HOTEL, SEONGSU, SUNDAY, "저녁")
    assert a["day"]["kind"] == "공휴일" and b["day"]["kind"] == "일요일"
    assert a["eta"] == b["eta"] and a["routes"] == b["routes"]


def test_commute_crowding_weekday_only():
    _skip_if_no_data()
    r, _ = _est("사당", "강남", WEEKDAY, "오전")
    cc = [c for c in r["cautions"] if c["code"] == "commute_crowding"]
    assert cc and cc[0]["pct"] >= 80 and cc[0]["station"] == "사당", r["cautions"]
    assert all(x["range"] == "timetable" for x in r["routes"]), "06:00 창 — 첫차 전 버스 표본이 섞이지 않는다"
    s, _ = _est("사당", "강남", SUNDAY, "오전")
    assert not [c for c in s["cautions"] if c["code"] == "commute_crowding"], "일요일엔 출퇴근 주의 없음"


def test_saturday_crowding_not_commute():
    """토요일 남태령 4호선 상행 10:30 재차율 104%(J-CONG-05 셀) — 표본엔 남지만 출퇴근 주의로는 안 올린다."""
    _skip_if_no_data()
    r, sm = _est("남태령", "사당", "2026-10-10", "오전")
    assert r["day"]["kind"] == "토요일" and r["day"]["congestion"] == "saturday"
    top = max((x["crowd"] for x in sm if x.get("crowd")), key=lambda c: c[0])
    assert top[0] >= 100 and top[3] == "남태령", top
    assert not [c for c in r["cautions"] if c["code"] == "commute_crowding"], r["cautions"]


def test_bus_range_profile():
    _skip_if_no_data()
    r, sm = _est("서울역", "이태원", WEEKDAY, "오후", modes=["bus"])
    ok = [x for x in sm if x["choice"]]
    assert ok and all(x["range"] == "bus_profile" for x in ok), {x["range"] for x in ok}
    assert all(x["lo"] <= x["eta"] <= x["hi"] for x in ok)
    assert any(x["lo"] < x["eta"] for x in ok) and any(x["hi"] > x["eta"] for x in ok), "버스 범위가 0 폭이다"
    e = r["eta"]
    assert e["p10_min"] < e["p50_min"] < e["p90_min"], e


def test_night_last_service():
    _skip_if_no_data()
    r, _ = _est(HOTEL, SEONGSU, WEEKDAY, "밤")
    ls = [c for c in r["cautions"] if c["code"] == "last_service"]
    assert ls and ls[0]["route"].startswith("02호선"), r["cautions"]
    assert ls[0]["carried_by"] and all(k.startswith("버스 N") for k in ls[0]["carried_by"]), "지하철 뒤를 심야버스가 잇는다"
    b, _ = _est("서울역", "이태원", WEEKDAY, "밤", modes=["bus"])
    ls = [c for c in b["cautions"] if c["code"] == "last_service"]
    assert ls and ls[0]["route"].startswith("버스 ") and ls[0]["none_from"], \
        "버스 막차 — multi 가 불가 버스 후보를 코드 없이 접어도 경계 재판정으로 잡는다"
    s, _ = _est(HOTEL, SEONGSU, WEEKDAY, "밤", modes=["subway"])
    ls = [c for c in s["cautions"] if c["code"] == "last_service"]
    assert ls and not ls[0]["carried_by"] and ls[0]["none_from"], "지하철만이면 그 뒤는 없다"


def test_first_service_window():
    _skip_if_no_data()
    rt = _runtime()
    sm = []
    r = Estimator(rt, modes=["subway"]).estimate(HOTEL, SEONGSU, WEEKDAY, "오전", window=(240, 360), samples=sm)
    fs = [c for c in r["cautions"] if c["code"] == "first_service"]
    assert fs and fs[0]["first_ok"] and not fs[0]["carried_by"], r["cautions"]
    assert r["window"]["from"] == "04:00"


def test_no_station():
    _skip_if_no_data()
    r, _ = _est({"name": "먼 곳", "lat": 37.20, "lon": 127.60}, SEONGSU, WEEKDAY, "오후")
    assert r["verdict"] == "no_data" and "지하철역" in r["reason"]


def test_verifier_untouched():
    """추정이 판정기 상태를 바꾸지 않는다 — 역산 스위치 복구 · 같은 케이스의 밖 판이 앞뒤로 같다."""
    _skip_if_no_data()
    v = _runtime()._v
    case = {"id": "u", "date": WEEKDAY, "depart_at": "14:00", "arrive_by": "14:40",
            "legs": [{"line": "02호선", "from": "을지로입구", "to": "성수"}]}
    before = v.verify_case(dict(case)).out
    _est(HOTEL, SEONGSU, WEEKDAY, "저녁")
    _CACHE.clear()
    _est(HOTEL, SEONGSU, WEEKDAY, "저녁")
    assert v.lfd_enabled is True
    assert v.verify_case(dict(case)).out == before


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
    print(f"[estimate] {n - fails - skips}/{n} 통과 · SKIP {skips} · 실패 {fails}")
    sys.exit(1 if fails else 0)
