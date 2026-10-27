# -*- coding: utf-8 -*-
"""먼저 채우기의 전체 자동 추천을 **빈칸 일정만** 계산한다 — `[2026-10-28 서빙 속도]` (`autofix.plan(item_ids=…)` · `prefill.autofix_owner(targets=…)`).

☆왜. 먼저 채우기(`prefill.run`)는 확인 화면 공개(`stage=review`) **전**에 돈다(고객은 그동안 「읽는 중」). 식당 팀 · 활동 팀 빈칸을 채우려고
  `autofix.plan` 을 부르는데, 전에는 이 계산이 확인이 필요한 **모든** 일정(운영시간 모름 · 지점 모호 · 늦게 닿는 구간)마다 후보를 모으고
  시간표 이동 계산기로 맞춰 봤다. 먼저 채우기는 빈칸 일정의 장소 바꿈만 쓰고 나머지는 버린다 — 버릴 계산이 기다림과 요청 한도(25초)를 썼다.
★지키는 것: 고객이 누르는 「전체 자동 추천」(`item_ids` 없음)은 그대로 · 빈칸 일정의 결과는 실제로 저장되는 앞 일정을 기준으로 맞춘다 ·
  묻는 빈칸의 일정이 계산 모음에 없으면 더해서 다시 계산한다(빠뜨려서 「바꿀 안 없음」이 되지 않게).

재현:

    python -m pytest tests/unit/travel/test_intake_prefill_plan_scope.py -q
"""
from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.intake import autofix, pipeline, prefill
from app.domains.travel_ops.components.intake.gaps import Gap

BAD_PLACE = {"row": "place", "result": "bad", "text": "x"}
WARN_HOURS = {"row": "hours", "result": "warn", "text": "운영시간 모름"}


def _item(n: int, title: str, start: str, end: str, *, status: str = "review", place: dict | None = None,
          state: str = "found", kind: str = "activity", rows=None) -> dict:
    return {"id": f"0-{n}", "source_id": "s", "index": n, "title": title, "kind": kind, "date": "2030-01-05",
            "starts_at": start, "ends_at": end, "locked": False, "status": status, "place_state": state,
            "place": place, "rows": list(rows if rows is not None else [BAD_PLACE])}


def _place(name: str, lat: float = 37.57, lon: float = 126.98) -> dict:
    return {"name": name, "latitude": lat, "longitude": lon, "source": "tour_api"}


@pytest.fixture()
def tracing(monkeypatch):
    """후보 · 시각 맞추기 모방 — 어느 일정을 맞춰 봤는지(와 그때의 앞 일정)를 적는다. 이동 계산기는 만들지 않는다."""
    seen: dict = {"alternatives": [], "fit": [], "prev": {}}

    def fake_alternatives(conn, **kwargs):
        seen["alternatives"].append(kwargs["item"]["id"])
        return {"candidates": [{"place": _place(f"{kwargs['item']['title']} 대안"), "status": "ok"}]}

    def fake_fit(conn, tenant_id, item, place, prev, nxt, start, duration, engine, *, require_known=False, **_kw):
        seen["fit"].append(item["id"])
        seen["prev"][item["id"]] = None if prev is None else {k: prev.get(k) for k in ("starts_at", "ends_at")} | {
            "place": (prev.get("place") or {}).get("name")}
        later = start.replace(hour=start.hour + 1) if item["id"] == "0-0" else start      # 첫 일정은 시각까지 옮긴다(버려질 바꿈)
        return later, later + duration, True

    monkeypatch.setattr(autofix.cand_module, "alternatives", fake_alternatives)
    monkeypatch.setattr(autofix, "_fit_window", fake_fit)
    monkeypatch.setattr(autofix, "default_engine", lambda party=None, modes=None: None)
    return seen


def _review():
    return {"items": [_item(0, "올리브영", "10:00", "11:00", place=_place("올리브영 명동"), state="picked_nearest"),
                      _item(1, "성수 식당", "12:00", "13:00", place=None, state="needs_choice", kind="dining"),
                      _item(2, "N서울타워", "15:00", "16:00", place=_place("N서울타워"), rows=[WARN_HOURS])],
            "moves": []}


def test_item_ids_fit_only_those_items(tracing):
    got = autofix.plan(None, tenant_id="t", review=_review(), item_ids={"0-1"})
    assert tracing["alternatives"] == ["0-1"] and set(tracing["fit"]) == {"0-1"}, tracing
    assert {c["id"] for c in got["changes"]} <= {"0-1"} and [c["id"] for c in got["changes"]] == ["0-1"]


def test_without_item_ids_the_customer_full_autofix_is_unchanged(tracing):
    got = autofix.plan(None, tenant_id="t", review=_review())
    assert tracing["alternatives"] == ["0-0", "0-1", "0-2"], tracing
    assert {c["id"] for c in got["changes"]} == {"0-0", "0-1"} and [k["id"] for k in got["kept"]] == ["0-2"]


def test_empty_item_ids_compute_nothing_and_build_no_engine(tracing, monkeypatch):
    monkeypatch.setattr(autofix, "default_engine", lambda *a, **k: pytest.fail("계산기를 만들면 안 된다"))
    assert autofix.plan(None, tenant_id="t", review=_review(), item_ids=()) == {"changes": [], "kept": []}
    assert tracing["alternatives"] == [] and tracing["fit"] == []


def test_item_id_and_item_ids_together_are_refused(tracing):
    with pytest.raises(TypeError):
        autofix.plan(None, tenant_id="t", review=_review(), item_id="0-1", item_ids={"0-1"})


def test_the_gap_is_fitted_against_the_saved_previous_stop_not_a_discarded_change(tracing):
    """전체 계산에서는 앞 일정(올리브영 — 지점 모호)을 한 시간 뒤로 옮긴 값을 기준으로 빈칸을 맞췄다 — 그 바꿈은 먼저 채우기가 버린다(저장되지 않는 기준).
    빈칸 일정만 계산하면 실제로 남는 앞 일정(지금 시각)을 기준으로 맞춘다."""
    # 아래 첫 단언은 고객이 누르는 전체 자동 추천(`item_ids` 없음)의 **지금 동작을 기록**한다 — 그 길을 고치면 이 줄만 바꾼다
    autofix.plan(None, tenant_id="t", review=_review())
    assert tracing["prev"]["0-1"] == {"starts_at": "11:00", "ends_at": "12:00", "place": "올리브영 명동"}       # 전: 버려질 시각이 기준
    tracing["prev"].clear()
    autofix.plan(None, tenant_id="t", review=_review(), item_ids={"0-1"})
    assert tracing["prev"]["0-1"] == {"starts_at": "10:00", "ends_at": "11:00", "place": "올리브영 명동"}       # 후: 저장되는 값이 기준


# ── autofix_owner(targets) ───────────────────────────────────────
def _gap(item: str | None, kind: str = "meal_place") -> Gap:
    return Gap(kind, {"item": item} if item is not None else {"pair": ["0-0", "0-1"]}, "빈칸")


def _recording_plan(calls: list):
    def plan(**kwargs):
        calls.append(kwargs)
        ids = kwargs.get("item_ids")
        return {"changes": [{"id": i, "edits": [{"field": "place", "value": {"name": f"{i} 채움"}}], "to": {"place": {"name": f"{i} 채움"}}}
                            for i in sorted(ids or [])], "kept": []}
    return plan


def test_owner_plans_once_per_revision_for_the_round_targets():
    calls: list = []
    targets = {"0-1", "0-3"}
    owner = prefill.autofix_owner(_recording_plan(calls), targets=lambda: targets)
    first = owner(_gap("0-1"), {"revision": 2})
    second = owner(_gap("0-3"), {"revision": 2})
    assert calls == [{"item_ids": frozenset({"0-1", "0-3"})}]
    assert first.candidates and second.candidates


def test_owner_adds_a_gap_missing_from_the_targets_and_recomputes():
    calls: list = []
    owner = prefill.autofix_owner(_recording_plan(calls), targets=lambda: {"0-1"})
    owner(_gap("0-1"), {"revision": 2})
    got = owner(_gap("0-5"), {"revision": 2})                    # 다시 묻는 빈칸(회차 모음 밖) — 빠뜨리지 않는다
    assert calls == [{"item_ids": frozenset({"0-1"})}, {"item_ids": frozenset({"0-1", "0-5"})}]
    assert got.candidates and got.candidates[0]["title"] == "0-5 채움"


def test_owner_recomputes_for_a_new_revision_with_the_new_targets():
    calls: list = []
    targets = {"0-1"}
    owner = prefill.autofix_owner(_recording_plan(calls), targets=lambda: targets)
    owner(_gap("0-1"), {"revision": 2})
    targets = {"0-4"}
    owner(_gap("0-4"), {"revision": 3})
    assert calls == [{"item_ids": frozenset({"0-1"})}, {"item_ids": frozenset({"0-4"})}]


def test_owner_with_a_missing_revision_does_not_reuse_or_crash():
    calls: list = []
    owner = prefill.autofix_owner(_recording_plan(calls), targets=lambda: {"0-1"})
    assert owner(_gap("0-1"), {}).candidates                      # 판 번호가 없어도(KeyError 없이) 계산한다
    assert calls == [{"item_ids": frozenset({"0-1"})}]


def test_owner_without_targets_keeps_the_old_whole_plan_call():
    calls: list = []

    def plan(**kwargs):
        calls.append(kwargs)
        return {"changes": [], "kept": []}
    owner = prefill.autofix_owner(plan)
    owner(_gap("0-1"), {"revision": 2})
    owner(_gap(None), {"revision": 2})
    assert calls == [{}]


def test_team_items_are_the_team_routed_gaps_that_point_at_an_item():
    gaps = [_gap("0-1"), _gap("0-2", "activity_place"), _gap("0-3", "place_not_found"), _gap(None, "move_mode"),
            Gap("free_slot", {"source_id": "s", "day": 1}, "빈 시간")]
    assert prefill._team_items(gaps) == {"0-1", "0-2"}


# ── prefill.run 전체(가짜 DB 경계) ─────────────────────────────────
def test_prefill_run_plans_only_the_gap_item_and_logs_timing_without_names(monkeypatch, caplog):
    review1 = _review()
    filled = _review()
    filled["items"][1] = {**filled["items"][1], "place": _place("성수가든"), "place_state": "customer", "status": "adjusted", "rows": []}
    reviews = {1: review1, 2: filled}
    monkeypatch.setattr(pipeline, "current_review", lambda conn, *, revision, **kw: (None, reviews[revision]))
    monkeypatch.setattr(pipeline, "_claims", lambda conn, tenant_id, intake_id, revision: [])
    monkeypatch.setattr(pipeline, "_trip_fields", lambda claims: {})
    edits: list = []
    monkeypatch.setattr(pipeline, "edit", lambda conn, **kw: edits.append(kw["edits"]) or kw["revision"] + 1)
    stored: dict = {}
    monkeypatch.setattr(prefill, "_store", lambda conn, **kw: stored.update(kw))
    planned: list = []

    def fake_plan(conn, *, tenant_id, review, kakao=None, item_ids=None, **kw):
        planned.append(item_ids)
        assert kw == {"keep_times": True}, kw                   # 장소만 저장하는 쪽 — 이웃 빈칸 기준(`test_intake_prefill_adjacent_blanks.py`)
        return {"changes": [{"id": "0-1", "source_id": "s", "index": 1, "title": "성수 식당", "from": {}, "hours_known": True,
                             "to": {"place": {"name": "성수가든"}}, "edits": [{"field": "place", "value": _place("성수가든")}]}],
                "kept": []}
    monkeypatch.setattr(autofix, "plan", fake_plan)
    caplog.set_level(logging.INFO, logger=prefill.log.name)
    intake = uuid4()
    got = prefill.run(None, tenant_id="t", customer_id=uuid4(), intake_id=intake, revision=1)
    assert planned == [frozenset({"0-1"})]                                           # 빈칸 일정만
    assert got["revision"] == 2 and [f["item"] for f in got["filled"]] == ["0-1"]
    assert edits == [[{"source_id": "s", "field": "items[1].place", "value": _place("성수가든")}]]   # 저장은 전처럼 빈칸 장소만
    [line] = [r.getMessage() for r in caplog.records if "intake prefill timing" in r.getMessage()]
    for field in ("seconds=", "plan_seconds=", "plan_runs=1", "planned_items=1", "gaps_seen=1", "rounds=1", str(intake)):
        assert field in line, line
    assert not any(name in line for name in ("성수", "올리브영", "N서울타워"))


def test_a_second_round_plans_only_the_new_blank(monkeypatch):
    """채운 뒤 다시 검사가 **새** 빈칸(0-4)을 내면 다음 회차는 그 일정만 계산한다 — 이미 물은 빈칸(0-1)을 다시 계산하지 않는다."""
    review1 = _review()
    review1["items"].append(_item(4, "오후 구경", "17:00", "18:00", place=None, state="needs_choice"))
    review1["items"][-1]["place_state"] = "found"                   # 1판: 0-4 는 아직 빈칸이 아니다
    review1["items"][-1]["place"] = _place("광장")
    review2 = _review()
    review2["items"][1] = {**review2["items"][1], "place": _place("성수가든"), "place_state": "customer", "status": "adjusted", "rows": []}
    review2["items"].append(_item(4, "오후 구경", "17:00", "18:00", place=None, state="needs_choice"))   # 2판: 새 빈칸
    review3 = {**review2, "items": [*review2["items"][:-1], {**review2["items"][-1], "place": _place("구경터"), "place_state": "customer"}]}
    reviews = {1: review1, 2: review2, 3: review3}
    monkeypatch.setattr(pipeline, "current_review", lambda conn, *, revision, **kw: (None, reviews[revision]))
    monkeypatch.setattr(pipeline, "_claims", lambda conn, tenant_id, intake_id, revision: [])
    monkeypatch.setattr(pipeline, "_trip_fields", lambda claims: {})
    monkeypatch.setattr(pipeline, "edit", lambda conn, **kw: kw["revision"] + 1)
    monkeypatch.setattr(prefill, "_store", lambda conn, **kw: None)
    planned: list = []

    def fake_plan(conn, *, tenant_id, review, kakao=None, item_ids=None, **kw):
        planned.append(item_ids)
        return {"changes": [{"id": i, "source_id": "s", "index": int(i[2:]), "title": i, "from": {}, "hours_known": True,
                             "to": {"place": {"name": i}}, "edits": [{"field": "place", "value": _place(f"{i} 채움")}]}
                            for i in sorted(item_ids)], "kept": []}
    monkeypatch.setattr(autofix, "plan", fake_plan)
    got = prefill.run(None, tenant_id="t", customer_id=uuid4(), intake_id=uuid4(), revision=1)
    assert planned == [frozenset({"0-1"}), frozenset({"0-4"})], planned
    assert got["revision"] == 3 and sorted(f["item"] for f in got["filled"]) == ["0-1", "0-4"]
