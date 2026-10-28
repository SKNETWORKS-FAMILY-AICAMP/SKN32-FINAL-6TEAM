# -*- coding: utf-8 -*-
"""먼저 채우기 — **이웃한 두 빈칸**의 시각 기준 `[2026-10-28 서빙 속도 독립 검토]`.

☆문제. 먼저 채우기(`prefill.run`)는 빈칸 일정의 **장소만** 저장한다(고객이 쓴 시각은 그대로 — `apply`). 그런데 추천 계산(`autofix.plan`)은
  앞 빈칸을 맞추면서 옮긴 시각(예: 앞 일정에서 40분 걸려 12:00 → 12:40)을 **다음 일정의 기준**으로 썼다. 그 시각은 저장되지 않는다.
  그래서 바로 뒤 빈칸은 실제로 남지 않는 「12:40~13:40 식사」 뒤에 맞춰 보다 자리가 모자라 「맞는 안이 없어 그대로 두었어요」로 남았다
  (저장되는 12:00~13:00 뒤라면 채울 수 있다). 팀 HEAD(전체 계산)와 빈칸만 계산 후보(`06b75e491`)에서 **똑같이** 재현된다 — 새 회귀가 아니다.
★고침: 먼저 채우기는 `autofix.plan(keep_times=True)` 로 부른다 — 바꾼 일정의 **장소만** 다음 일정의 기준에 반영하고 시각은 저장되는 값(그대로)을 쓴다.
  고객이 누르는 「전체 자동 추천」(시각 바꿈도 저장한다)은 그대로 옮긴 시각을 기준으로 쓴다.

재현(가짜 DB 경계 · 실제 `autofix.plan` / `_fit_window` · 시험용 이동 계산기 · 운영시간 모름):

    python -m pytest tests/unit/travel/test_intake_prefill_adjacent_blanks.py -q
"""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.intake import autofix, pipeline, prefill

BAD_PLACE = {"row": "place", "result": "bad", "text": "x"}
DAY = "2030-01-05"
FAR = {"name": "경복궁", "latitude": 37.5796, "longitude": 126.9770, "source": "tour_api"}
TOWER = {"name": "N서울타워", "latitude": 37.5512, "longitude": 126.9882, "source": "tour_api"}


def _item(n, title, start, end, *, place=None, state="needs_choice", kind="activity", status="review", rows=None):
    return {"id": f"0-{n}", "source_id": "s", "index": n, "title": title, "kind": kind, "date": DAY, "starts_at": start,
            "ends_at": end, "locked": False, "status": status, "place_state": state, "place": place,
            "rows": list(rows if rows is not None else ([BAD_PLACE] if place is None else []))}


def _review():
    """경복궁(10:00~12:00, 다음 곳까지 40분) → 빈칸 식당(12:00~13:00) → 빈칸 구경(13:00~14:00) → N서울타워(14:15~)."""
    return {"items": [_item(0, "경복궁", "10:00", "12:00", place=FAR, state="found", status="ok"),
                      _item(1, "성수 식당", "12:00", "13:00", kind="dining"),
                      _item(2, "근처 구경", "13:00", "14:00"),
                      _item(3, "N서울타워", "14:15", "16:00", place=TOWER, state="found", status="ok")],
            "moves": []}


@pytest.fixture()
def world(monkeypatch):
    """후보 · 운영시간 · 이동 계산기 모방. 경복궁에서 떠나면 40분, 그 밖은 10분(시간표로 확인되는 가장 늦은 출발을 준다)."""
    seen: dict = {"prev": {}}

    def alternatives(conn, **kwargs):
        item = kwargs["item"]
        name = {"0-1": "성수가든", "0-2": "서울숲 산책"}.get(item["id"], f"{item['title']} 대안")
        return {"candidates": [{"place": {"name": name, "latitude": 37.544, "longitude": 127.04, "source": "tour_api"},
                                "status": "ok"}]}

    class _Facts:
        known = False
        attributes: dict = {}

    def engine(a, b, arrive, not_before=None):
        eta = 40 if a.get("name") == FAR["name"] else 10
        start = arrive - timedelta(minutes=eta)
        option = {"id": "subway_1", "label": "subway_1", "eta_min": eta, "uses": [], "fare_krw": 1550}
        return {"route": {"options": [option], "planned": "subway_1"}, "starts_at": start, "ends_at": arrive,
                "eta_min": eta, "left_out": []}, None

    real_fit = autofix._fit_window

    def fit(conn, tenant_id, item, place, prev, nxt, *args, **kwargs):
        seen["prev"].setdefault(item["id"], None if prev is None else
                                {"place": (prev.get("place") or {}).get("name"), "starts_at": prev.get("starts_at"),
                                 "ends_at": prev.get("ends_at")})
        return real_fit(conn, tenant_id, item, place, prev, nxt, *args, **kwargs)

    monkeypatch.setattr(autofix.cand_module, "alternatives", alternatives)
    monkeypatch.setattr(autofix, "facts_for", lambda *a, **k: _Facts())
    monkeypatch.setattr(autofix, "default_engine", lambda party=None, modes=None: engine)
    monkeypatch.setattr(autofix, "_fit_window", fit)
    return seen


def _run_prefill(monkeypatch):
    saved = _review()
    reviews = {1: saved}
    edits: list = []

    def edit(conn, **kw):
        edits.append(kw["edits"])
        new = kw["revision"] + 1
        nxt = {**reviews[kw["revision"]], "items": [dict(x) for x in reviews[kw["revision"]]["items"]]}
        for e in kw["edits"]:                              # 저장되는 것만 반영한다(장소 · 시각 필드 그대로)
            index, field = int(e["field"].split("[")[1].split("]")[0]), e["field"].split(".")[-1]
            row = nxt["items"][index]
            row[field] = e["value"]
            if field == "place":
                row.update(place_state="customer", status="adjusted", rows=[])
        reviews[new] = nxt
        return new
    monkeypatch.setattr(pipeline, "current_review", lambda conn, *, revision, **kw: (None, reviews[revision]))
    monkeypatch.setattr(pipeline, "_claims", lambda conn, tenant_id, intake_id, revision: [])
    monkeypatch.setattr(pipeline, "_trip_fields", lambda claims: {})
    monkeypatch.setattr(pipeline, "edit", edit)
    monkeypatch.setattr(prefill, "_store", lambda conn, **kw: None)
    got = prefill.run(None, tenant_id="t", customer_id=uuid4(), intake_id=uuid4(), revision=1)
    return got, edits, reviews[got["revision"]]


def test_the_second_blank_is_fitted_after_the_saved_first_blank_and_gets_filled(world, monkeypatch):
    got, edits, final = _run_prefill(monkeypatch)
    # 뒤 빈칸의 기준 = 저장되는 앞 빈칸(새 장소 · **고객 시각** 12:00~13:00). 전: 저장 안 되는 12:40~13:40
    assert world["prev"]["0-2"] == {"place": "성수가든", "starts_at": "12:00", "ends_at": "13:00"}, world["prev"]
    assert sorted(f["item"] for f in got["filled"]) == ["0-1", "0-2"], got
    assert [x["place"]["name"] if x["place"] else None for x in final["items"]] == ["경복궁", "성수가든", "서울숲 산책", "N서울타워"]


def test_prefill_still_saves_only_places_never_customer_times(world, monkeypatch):
    _, edits, final = _run_prefill(monkeypatch)
    fields = sorted(e["field"] for batch in edits for e in batch)
    assert fields == ["items[1].place", "items[2].place"], fields
    assert [(x["starts_at"], x["ends_at"]) for x in final["items"]] == [("10:00", "12:00"), ("12:00", "13:00"),
                                                                       ("13:00", "14:00"), ("14:15", "16:00")]


def test_customer_full_autofix_still_chains_the_moved_times(world):
    """고객이 누르는 「전체 자동 추천」은 시각 바꿈도 저장하므로 옮긴 시각을 다음 일정의 기준으로 쓴다 — 바뀌지 않는다."""
    got = autofix.plan(None, tenant_id="t", review=_review())
    first = next(c for c in got["changes"] if c["id"] == "0-1")
    assert (first["to"]["starts_at"], first["to"]["ends_at"]) == ("12:40", "13:40")
    assert world["prev"]["0-2"] == {"place": "성수가든", "starts_at": "12:40", "ends_at": "13:40"}
    assert [k["id"] for k in got["kept"]] == ["0-2"]          # 옮긴 시각 뒤로는 30분이 안 남는다(그 길의 지금 동작 기록)


def test_keep_times_changes_only_the_next_basis_not_the_first_proposal(world):
    """`keep_times` 는 앞 빈칸의 제안(장소 · 옮긴 시각 · 운영시간 확인)을 바꾸지 않는다 — 다음 일정이 보는 기준만 저장되는 값으로."""
    chained = autofix.plan(None, tenant_id="t", review=_review(), item_ids={"0-1", "0-2"})
    world["prev"].clear()
    kept = autofix.plan(None, tenant_id="t", review=_review(), item_ids={"0-1", "0-2"}, keep_times=True)
    first = [next(c for c in got["changes"] if c["id"] == "0-1") for got in (chained, kept)]
    assert first[0] == first[1]
    assert [k["id"] for k in chained["kept"]] == ["0-2"] and kept["kept"] == []
    second = next(c for c in kept["changes"] if c["id"] == "0-2")
    assert second["to"]["place"]["name"] == "서울숲 산책" and second["edits"][0]["field"] == "place"
