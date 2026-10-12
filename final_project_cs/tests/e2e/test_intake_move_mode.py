# -*- coding: utf-8 -*-
"""이동수단 고르기 — 구간별 수단 후보(읽기) · 고른 수단 반영(쓰기) · 앞뒤 일정이 바뀌면 유지/복귀. `[2026-10-07 사용자 결정 — 이동 세션 착수]`

계약: `wiki/records/plans/2026-10-05_이동수단_선택_서버계약안.md`.

재현:

    python -m pytest tests/e2e/test_intake_move_mode.py -v

★이 시험이 쓰는 관광공사 · 카카오 · **이동 계산기는 모두 시험용 모방**이다(실제 서버가 아니다) — 화면 반응과 계약 모양을 본다. 실제 시간표 판정은 이동 단위 시험과 실서버 확인이 본다.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.domains.travel_ops.components.intake import autofix as autofix_module
from app.domains.travel_ops.components.intake import review as review_module

from .test_intake_review import ROOMY, _client, _edit, _field, _item, _key, _send, rv  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — rv 가 쓰는 픽스처


class FakeCalc:
    """이동 계산기 모방 — 수단마다 정해진 소요(분). 앞 일정 끝(`not_before`) 뒤 떠나서 못 닿으면 후보가 없다(진짜 계산기와 같다)."""

    DUR = {"subway": 16, "bus": 38, "taxi": 12, "walk": 70}
    OPT = {"subway": ("subway_1", ["2호선:경복궁", "2호선:을지로입구"], 1550), "bus": ("bus_3315", ["버스:3315"], 1500),
           "taxi": ("taxi", [], 7000), "walk": ("walk", [], 0)}

    def __init__(self):
        self.calls: list[str] = []

    def factory(self, party=None, modes=None):
        mode = (modes or ["subway"])[0]

        def run(a, b, arrive, not_before=None):
            self.calls.append(mode)
            eta = self.DUR[mode]
            start = arrive - timedelta(minutes=eta + 10)
            if not_before is not None and start < not_before:
                return None, {"code": "arrive_late", "reason": "늦음"}
            oid, uses, fare = self.OPT[mode]
            option = {"id": oid, "label": oid, "eta_min": eta, "uses": uses, "fare_krw": fare}
            if mode == "walk":
                option["walk_m"] = 4200
            return {"route": {"options": [option], "planned": oid}, "starts_at": start,
                    "ends_at": start + timedelta(minutes=eta), "eta_min": eta, "left_out": []}, None
        return run


@pytest.fixture()
def calc(rv, monkeypatch):  # noqa: F811
    fake = FakeCalc()
    monkeypatch.setattr(review_module, "default_engine", fake.factory)
    monkeypatch.setattr(autofix_module, "default_engine", fake.factory)
    return fake


def _setup(calc):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    return client, headers, view


def _gap(view, a_title, b_title):
    a, b = _item(view, a_title), _item(view, b_title)
    h = lambda t: int(t[:2]) * 60 + int(t[3:])  # noqa: E731
    return h(b["starts_at"]) - h(a["ends_at"])


def _opts(client, headers, view, pair="0-1~0-2", status=200):
    r = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/moves/{pair}/options", headers=headers)
    assert r.status_code == status, r.text
    return r.json()


def _pick(client, headers, view, mode, pair="0-1~0-2", status=200, revision=None):
    r = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/moves/{pair}/mode", headers=headers,
                    json={"revision": view["revision"] if revision is None else revision, "mode": mode})
    assert r.status_code == status, r.text
    return r.json()


def _move(review, pair="0-1~0-2"):
    a, b = pair.split("~")
    return next(m for m in review["moves"] if m["from"] == a and m["to"] == b)


def test_options_lists_the_four_modes_in_a_fixed_order_with_fits_and_a_sentence_for_what_does_not_fit(calc):
    client, headers, view = _setup(calc)
    gap = _gap(view, "올리브영", "광장시장 빈대떡")
    assert gap == 60, gap
    got = _opts(client, headers, view)
    assert got["revision"] == view["revision"] and got["from"] == "0-1" and got["to"] == "0-2"
    assert got["current_mode"] == "subway" and got["recommended_mode"] == "subway"
    rows = {r["mode"]: r for r in got["options"]}
    assert [r["mode"] for r in got["options"]] == ["subway", "bus", "taxi", "walk"]
    assert rows["subway"]["fits"] is True and rows["subway"]["label"].startswith("지하철") and rows["subway"]["grade"] == "확정"
    assert rows["subway"]["basis"] == "timetable" and rows["subway"]["fare_krw"] == 1550 and rows["subway"]["fare_is_floor"] is False
    assert rows["bus"]["fits"] is True and rows["bus"]["minutes"] == 38
    assert rows["taxi"]["fits"] is True and rows["taxi"]["fare_is_floor"] is False and rows["taxi"]["grade"] == "추정" and rows["taxi"]["basis"] == "estimate"
    assert rows["taxi"]["fare_is_estimate"] is True
    assert rows["walk"]["fits"] is False and rows["walk"]["fare_krw"] == 0
    assert "걸음으로는 10분 늦어요" in rows["walk"]["why_not"] and "시작해요" in rows["walk"]["why_not"]
    assert "why_not" not in rows["subway"]


def test_a_mode_the_calculator_cannot_make_has_no_row_and_a_slow_one_is_unknown_not_invented(calc, monkeypatch):
    client, headers, view = _setup(calc)
    plain = calc.factory

    def factory(party=None, modes=None):
        mode = (modes or ["subway"])[0]
        if mode == "bus":
            return lambda a, b, arrive, nb=None: (None, {"code": "no_data", "reason": "노선이 없다"})
        if mode == "taxi":
            def boom(a, b, arrive, nb=None):
                raise RuntimeError("계산기 오류")
            return boom
        return plain(party, modes)
    monkeypatch.setattr(review_module, "default_engine", factory)
    got = _opts(client, headers, view)
    modes = [r["mode"] for r in got["options"]]
    assert "bus" not in modes, "못 만든 수단은 줄이 없다"
    taxi = next(r for r in got["options"] if r["mode"] == "taxi")
    assert taxi["fits"] is None and "오래 걸려" in taxi["why_not"] and "minutes" not in taxi, "계산 못 끝낸 수단은 고를 수 없고 값을 지어내지 않는다"


def test_picking_a_mode_that_fits_makes_a_new_revision_with_the_move_recomputed_and_the_choice_marked(calc):
    client, headers, view = _setup(calc)
    done = _pick(client, headers, view, "taxi")
    assert done["revision"] == view["revision"] + 1
    move = _move(done["review"])
    assert move["mode"] == "taxi" and move["minutes"] == 12 and move["mode_choice"] == {"mode": "taxi", "state": "kept"}
    assert move["recommended_mode"] == "subway", "고객이 바꿔도 「추천」 꼬리표는 안 변한다"
    assert move["fare_krw"] == 7000 and "uses" not in move and "sig" not in move
    # 다른 구간은 그대로
    assert "mode_choice" in _move(done["review"], "0-0~0-1") and _move(done["review"], "0-0~0-1")["mode_choice"] is None
    again = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()
    assert again["revision"] == done["revision"] and _move(again["review"])["mode"] == "taxi"


def test_the_server_rechecks_and_refuses_a_mode_that_does_not_fit_or_does_not_exist(calc):
    client, headers, view = _setup(calc)
    body = _pick(client, headers, view, "walk", status=422)
    assert body["error"]["code"] == "mode_not_fit" and "걸음으로는 10분 늦어요" in body["error"]["why"]
    _pick(client, headers, view, "rocket", status=422)
    # 거절은 아무것도 저장하지 않는다
    now = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()
    assert now["revision"] == view["revision"] and _move(now["review"])["mode"] == "subway"


def test_a_stale_revision_is_409_and_a_missing_pair_or_someone_elses_intake_is_404(calc):
    client, headers, view = _setup(calc)
    _pick(client, headers, view, "taxi")
    stale = _pick(client, headers, view, "bus", status=409)
    assert stale["error"]["code"] == "stale_revision"
    got = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/moves/0-0~9-9/options", headers=headers)
    assert got.status_code == 404 and got.json()["error"]["code"] == "not_available"
    other = _key(client)
    assert client.get(f"/v1/web/trip-intakes/{view['intake_id']}/moves/0-1~0-2/options", headers=other).status_code == 404
    assert client.post(f"/v1/web/trip-intakes/{view['intake_id']}/moves/0-1~0-2/mode", headers=other,
                       json={"revision": 1, "mode": "taxi"}).status_code == 404


def test_going_back_to_recommended_clears_the_choice(calc):
    client, headers, view = _setup(calc)
    chosen = _pick(client, headers, view, "bus")
    assert _move(chosen["review"])["mode"] == "bus"
    back = _pick(client, headers, {**view, "revision": chosen["revision"]}, "recommended")
    move = _move(back["review"])
    assert move["mode"] == "subway" and move["mode_choice"] is None and back["revision"] == chosen["revision"] + 1


def test_when_the_neighbour_changes_a_chosen_mode_that_still_fits_is_kept_and_one_that_no_longer_fits_falls_back_with_a_reason(calc):
    client, headers, view = _setup(calc)
    chosen = _pick(client, headers, view, "bus")                 # 간격 60분 — 버스 38분 닿는다
    assert _move(chosen["review"])["mode_choice"]["state"] == "kept"
    cur = {**view, "revision": chosen["revision"]}
    market = _item(client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json(), "광장시장 빈대떡")
    # 다음 일정을 당겨 간격을 30분으로 — 버스 38분은 안 닿고 추천(지하철 16분)은 닿는다
    edited = _edit(client, headers, cur, _field(market, "starts_at", "13:00"), _field(market, "ends_at", "14:00"))
    move = _move(edited["review"])
    assert move["mode"] == "subway" and move["recommended_mode"] == "subway"
    assert move["mode_choice"]["state"] == "dropped" and move["mode_choice"]["mode"] == "bus"
    assert "버스로는" in move["mode_choice"]["why"] and "늦어요" in move["mode_choice"]["why"]
    # 간격이 다시 넉넉해지면 같은 고름을 다시 시도해 되살린다
    market2 = _item(edited, "광장시장 빈대떡")
    again = _edit(client, headers, {**cur, "revision": edited["revision"]}, _field(market2, "starts_at", "13:30"), _field(market2, "ends_at", "14:30"))
    assert _move(again["review"])["mode_choice"] == {"mode": "bus", "state": "kept"} and _move(again["review"])["mode"] == "bus"


def test_the_review_map_draws_the_chosen_mode_as_a_taxi_not_the_recommended_subway_line(calc):
    client, headers, view = _setup(calc)
    before = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/route-shapes", headers=headers).json()
    done = _pick(client, headers, view, "taxi")
    got = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/route-shapes", headers=headers).json()
    pair = ("0-1", "0-2")
    shape = next(s for s in got["shapes"] if (s["from_item_id"], s["to_item_id"]) == pair)
    old = next(s for s in before["shapes"] if (s["from_item_id"], s["to_item_id"]) == pair)
    assert got["revision"] == done["revision"] and shape != old, "고른 수단이 경로선에 반영된다"
    assert "taxi" in str(shape).lower() or "car" in str(shape).lower() or "택시" in str(shape) or "직선" in str(shape.get("note") or ""), shape


def test_auto_fix_all_fits_times_with_the_chosen_mode_where_one_is_kept(calc):
    """계약 ⓒ — 전체 자동 추천이 고른 수단을 유지한다: 고른(`kept`) 구간은 그 수단의 계산기로 시각을 맞춘다."""
    client, headers, view = _setup(calc)
    chosen = _pick(client, headers, view, "bus")
    calc.calls.clear()
    r = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers,
                    json={"revision": chosen["revision"], "dry_run": True})
    assert r.status_code == 200, r.text
    assert "bus" in calc.calls, "고른 구간(올리브영→광장시장)을 고른 수단(버스)으로 맞춰 봐야 한다 — 추천 수단으로만 맞추면 적용 뒤 고른 수단이 안 닿아 되돌아간다"
