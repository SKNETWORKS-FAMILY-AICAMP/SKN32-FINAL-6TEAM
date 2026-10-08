# -*- coding: utf-8 -*-
"""일정 위험 점검 보고(`components/watch/risk_report.py`) — 점검 결과를 사람이 읽을 모양으로. `[2026-10-06 사용자 요청 — MCP 읽기 도구]`

★지키려는 것
 ①항목마다 `problem`(원인) · `clear` · `unknown`. **확인 불가를 「문제 없음」으로 말하지 않는다** — 6종 중 하나라도 못 확인했으면 `clear` 가 아니다.
 ②「해당 없음」(실내 장소의 예보)은 확인 불가가 아니다. 문제가 찾아졌으면 못 확인한 종류가 있어도 `problem`(그 종류는 `unknown_categories` 에 따로).
 ③캐시만 읽는 호출(`cached`)에서 못 읽은 종류는 `not_cached` 라고 이유를 밝힌다. 장소(좌표)를 모르면 점검하지 않고 `unknown`. 점검이 죽어도 그 항목만 `unknown`.
 ④점검 대상: 지금부터 N시간 안 + 진행 중 · 이동 항목은 건너뜀 · 최대 개수 · `item_id` 한 항목만(시간 범위 무시) · 없는 항목은 `LookupError`.
 ⑤확인 시각 — `checked_at` 과 종류마다 `confirmed_at`(가장 오래된 것을 `oldest_confirmed_at`).

재현:

    python -m pytest tests/unit/travel/test_risk_report.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch import risk_report

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=KST)
PLACE = {"place_id": str(uuid4()), "name": "시험 궁", "latitude": 37.57, "longitude": 126.98, "weather_sensitive": True}
NAMES = ("forecast", "weather_warning", "disaster_msg", "traffic_control", "air_quality", "earthquake")


def _item(seq=1, start_min=30, kind="activity", place=PLACE, length_min=60, title=None) -> Item:
    start = NOW + timedelta(minutes=start_min)
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title or f"항목 {seq}", place_id=None, starts_at=start,
                ends_at=start + timedelta(minutes=length_min), place=place)


def _check(*, ok=NAMES, na=(), failed=(), not_connected=(), disruptions=()):
    """점검 흉내 — 6종 중 어느 것이 어떤 상태인지 정한다."""
    def check(*, place, starts_at, region="서울"):
        rows = []
        for name in NAMES:
            if name in na:
                rows.append({"category": name, "status": "not_applicable", "reason": "날씨 영향을 받지 않는 장소"})
            elif name in failed:
                rows.append({"category": name, "status": "failed", "reason": "값을 못 냈다"})
            elif name in not_connected:
                rows.append({"category": name, "status": "not_connected", "reason": "키 발급 대기"})
            else:
                rows.append({"category": name, "status": "ok", "source": f"{name}-src", "confirmed_at": f"2026-10-06T09:5{NAMES.index(name)}:00+09:00"})
        return {"verdict": "x", "disruptions": list(disruptions), "advisories": [{"category": "forecast", "field": "wind_speed_kmh", "value": 40}],
                "checks": rows, "checked_at": "2026-10-06T10:00:01+00:00"}
    return check


# ── ① 세 상태 ─────────────────────────────────────────────────────
def test_a_clean_check_is_clear_and_carries_both_times():
    row = risk_report.judge_item(_check(), _item(), mode="cached")
    assert row["status"] == "clear" and row["problems"] == [] and row["unknown_categories"] == []
    assert [c["category"] for c in row["categories"]] == list(NAMES) and all(c["status"] == "ok" for c in row["categories"])
    assert row["checked_at"] == "2026-10-06T10:00:01+00:00" and row["oldest_confirmed_at"] == "2026-10-06T09:50:00+09:00"     # ⑤
    assert row["cautions"] and row["cautions"][0]["field"] == "wind_speed_kmh"


def test_a_problem_names_its_cause():
    cause = {"category": "disaster_msg", "kind": "지진", "step": "긴급재난", "text": "서울 지진 발생", "source": "행안부", "created_at": "2026-10-06T09:58:00+09:00"}
    row = risk_report.judge_item(_check(disruptions=[cause]), _item(), mode="fresh")
    assert row["status"] == "problem" and len(row["problems"]) == 1
    problem = row["problems"][0]
    assert problem["label"] == "재난문자" and problem["kind"] == "지진" and "서울 지진 발생" in problem["summary"] and problem["created_at"] == cause["created_at"]


def test_not_applicable_is_not_unknown_but_a_failed_or_unconnected_source_is():
    assert risk_report.judge_item(_check(na=("forecast", "weather_warning", "air_quality")), _item(), mode="fresh")["status"] == "clear"       # ②
    row = risk_report.judge_item(_check(failed=("traffic_control",), not_connected=("air_quality",)), _item(), mode="fresh")
    assert row["status"] == "unknown"                                                                       # ① 확인 불가를 「문제 없음」으로 말하지 않는다
    assert [(u["category"], u["code"]) for u in row["unknown_categories"]] == [("traffic_control", "source_failed"), ("air_quality", "not_connected")]
    assert row["unknown_categories"][0]["reason"] == risk_report.REASONS["source_failed"]                    # 고정 문장 — 점검기의 reason 이 아니다


def test_a_found_problem_wins_over_unchecked_kinds_and_the_unchecked_ones_are_still_listed():
    cause = {"category": "weather_warning", "kind": "호우", "areas": ["서울"]}
    row = risk_report.judge_item(_check(failed=("traffic_control",), disruptions=[cause]), _item(), mode="fresh")
    assert row["status"] == "problem" and [u["category"] for u in row["unknown_categories"]] == ["traffic_control"]


def test_in_cached_mode_a_miss_says_it_was_not_cached():
    row = risk_report.judge_item(_check(failed=("forecast", "traffic_control")), _item(), mode="cached")
    assert row["status"] == "unknown" and {u["code"] for u in row["unknown_categories"]} == {"not_cached"}
    assert all("fresh" in u["reason"] for u in row["unknown_categories"])                                      # ③ 새로 확인하는 길을 알린다


def test_a_category_missing_from_the_response_is_unknown_so_it_can_never_be_clear():
    """`[코덱스 검토 반영]` 점검 응답에 6종 중 일부가 없거나 `checks` 가 비면 빠진 종류를 확인 불가로 채운다 — 점검기를 갈아 끼우거나 회귀가 나도 `clear` 가 되지 않는다."""
    def partial(*, place, starts_at, region="서울"):
        return {"verdict": "clear", "disruptions": [], "advisories": [],
                "checks": [{"category": "forecast", "status": "ok", "confirmed_at": "2026-10-06T09:50:00+09:00"}], "checked_at": "t"}

    row = risk_report.judge_item(partial, _item(), mode="fresh")
    assert row["status"] == "unknown" and {u["category"] for u in row["unknown_categories"]} == set(NAMES) - {"forecast"}
    assert {u["code"] for u in row["unknown_categories"]} == {"missing"}
    empty = risk_report.judge_item(lambda **kw: {"verdict": "clear", "disruptions": [], "checks": [], "checked_at": "t"}, _item(), mode="fresh")
    assert empty["status"] == "unknown" and len(empty["unknown_categories"]) == 6


def test_the_checkers_own_reason_text_never_reaches_the_report():
    """`[검토 반영]` 소스 미연결 사유에는 환경변수 · 파일 이름이 들어 있다 — 내보내지 않는다."""
    def check(*, place, starts_at, region="서울"):
        rows = [{"category": n, "status": "ok", "source": "s", "confirmed_at": "2026-10-06T09:50:00+09:00"} for n in NAMES[:4]]
        rows += [{"category": "air_quality", "status": "not_connected", "reason": "ACOP_UTIC_API_KEY_1 을 .env.apikeys 에 넣어야 한다 (http://10.0.0.5:8989)"},
                 {"category": "earthquake", "status": "failed", "reason": "내부 오류: C:\\secret\\path"}]
        return {"verdict": "x", "disruptions": [], "checks": rows, "checked_at": "t"}

    row = risk_report.judge_item(check, _item(), mode="fresh")
    text = str(row)
    assert "ACOP_" not in text and ".env" not in text and "10.0.0.5" not in text and "secret" not in text
    assert {u["reason"] for u in row["unknown_categories"]} == {risk_report.REASONS["not_connected"], risk_report.REASONS["source_failed"]}


def test_a_partial_answer_is_unknown_not_clear_and_notes_are_surfaced():
    """`[검토 반영]` 교통은 ITS · UTIC 중 한쪽만 답해도 점검기는 `ok` 로 돌려준다 — 「집회 · 행사」를 놓쳤을 수 있으니 확인 불가다. 구분 못 한 재난문자 · 모델 추정 대기질은 주의로 드러낸다."""
    def check(*, place, starts_at, region="서울"):
        rows = []
        for name in NAMES:
            row = {"category": name, "status": "ok", "source": f"{name}-src", "confirmed_at": "2026-10-06T09:50:00+09:00"}
            if name == "traffic_control":
                row.update(partial_from=["utic"], sources=["its"], note="UTIC 못 답함")
            if name == "disaster_msg":
                row["unclassified"] = [{"text": "구분 모르는 문자"}, {"text": "또 하나"}]
            if name == "air_quality":
                row["mode"] = "model"
            rows.append(row)
        return {"verdict": "clear", "disruptions": [], "checks": rows, "checked_at": "t"}

    row = risk_report.judge_item(check, _item(), mode="fresh")
    assert row["status"] == "unknown" and [(u["category"], u["code"]) for u in row["unknown_categories"]] == [("traffic_control", "partial")]
    traffic = next(c for c in row["categories"] if c["category"] == "traffic_control")
    assert traffic["answered_by"] == ["its"] and traffic["missing_from"] == ["utic"]
    notes = [c["note"] for c in row["cautions"] if "note" in c]
    assert any("2건" in n for n in notes) and any("모델 추정" in n for n in notes)
    assert next(c for c in row["categories"] if c["category"] == "air_quality")["estimated"] is True


def test_an_ongoing_item_is_checked_now_and_a_far_item_cannot_be_clear_for_current_state_kinds():
    seen = []

    def check(*, place, starts_at, region="서울"):
        seen.append(starts_at)
        return _check()(place=place, starts_at=starts_at)

    ongoing = _item(1, start_min=-45, length_min=90)
    row = risk_report.judge_item(check, ongoing, mode="cached", at=NOW)
    assert seen[-1] == NOW and row["checked_for"] == NOW.isoformat() and row["status"] == "clear"            # 시작 시각이 아니라 지금으로 점검한다
    soon = _item(2, start_min=30)
    assert risk_report.judge_item(check, soon, mode="cached", at=NOW)["status"] == "clear" and seen[-1] == soon.starts_at     # 곧 시작하는 항목은 시작 시각 그대로(감시와 같은 캐시 키)
    far = _item(3, start_min=60 * 8)
    far_row = risk_report.judge_item(check, far, mode="cached", at=NOW, snapshot_hours=3)
    assert far_row["status"] == "unknown" and {u["category"] for u in far_row["unknown_categories"]} == set(risk_report.CURRENT_STATE)
    assert {u["code"] for u in far_row["unknown_categories"]} == {"too_early"} and next(c for c in far_row["categories"] if c["category"] == "forecast")["status"] == "ok"
    cause = {"category": "weather_warning", "kind": "호우"}
    problem_row = risk_report.judge_item(_check(disruptions=[cause]), far, mode="cached", at=NOW, snapshot_hours=3)
    assert problem_row["status"] == "problem" and problem_row["problems"][0]["as_of_now"] is True              # 지금 일어난 일이라고 밝힌다


def test_the_oldest_confirmation_is_picked_by_time_not_by_text():
    def check(*, place, starts_at, region="서울"):
        rows = [{"category": n, "status": "ok", "confirmed_at": at} for n, at in zip(NAMES, (
            "2026-10-06T09:50:00+09:00", "2026-10-06T01:10:00+00:00", "2026-10-06T09:40:00+09:00", "2026-10-06T09:55:00+09:00",
            "2026-10-06T09:56:00+09:00", "2026-10-06T09:57:00+09:00"))]
        return {"verdict": "x", "disruptions": [], "checks": rows, "checked_at": "t"}

    # 01:10Z = 10:10 KST 이고 가장 낡은 것은 09:40 KST — 글자 순으로 보면 「2026-10-06T01…」이 가장 앞이다
    assert risk_report.judge_item(check, _item(), mode="fresh")["oldest_confirmed_at"] == "2026-10-06T09:40:00+09:00"


# ── ③ 못 하는 경우 ───────────────────────────────────────────────
def test_an_item_without_a_place_or_coordinates_is_unknown_and_not_checked():
    calls = []
    check = lambda **kw: calls.append(kw)                                                       # noqa: E731
    assert risk_report.judge_item(check, _item(place=None), mode="cached")["code"] == "no_place"
    assert risk_report.judge_item(check, _item(place={"name": "좌표 없음", "latitude": None, "longitude": None}), mode="cached")["status"] == "unknown"
    assert calls == []


def test_a_crashing_check_only_marks_that_item_unknown():
    def check(**_):
        raise RuntimeError("소스가 터졌다")

    row = risk_report.judge_item(check, _item(), mode="fresh")
    assert row["status"] == "unknown" and row["code"] == "check_error" and "터졌다" not in str(row)         # 내부 오류 문구를 내보내지 않는다


# ── ④ 점검 대상 ───────────────────────────────────────────────────
def test_the_window_includes_ongoing_and_soon_items_and_skips_past_far_and_mobility():
    ongoing = _item(1, start_min=-30, length_min=60, title="진행 중")
    soon = _item(2, start_min=90, title="곧")
    far = _item(3, start_min=60 * 20, title="내일")
    past = _item(4, start_min=-300, length_min=30, title="지난")
    moving = _item(5, start_min=45, kind="mobility", place=None, title="이동")
    chosen, skipped = risk_report.pick_items([far, soon, past, moving, ongoing], at=NOW, horizon_hours=12, max_items=6, item_id=None)
    assert [i.title for i in chosen] == ["진행 중", "곧"]                                                       # 시작이 빠른 순
    assert [(s["title"], s["reason"]) for s in skipped] == [("이동", "mobility")]


def test_the_item_cap_skips_the_rest_with_a_reason():
    items = [_item(n, start_min=10 * n) for n in range(1, 6)]
    chosen, skipped = risk_report.pick_items(items, at=NOW, horizon_hours=12, max_items=2, item_id=None)
    assert len(chosen) == 2 and [s["reason"] for s in skipped] == ["over_limit"] * 3


def test_one_item_ignores_the_window_and_a_missing_item_is_a_lookup_error():
    far = _item(1, start_min=60 * 30)
    chosen, skipped = risk_report.pick_items([far], at=NOW, horizon_hours=1, max_items=6, item_id=far.item_id)
    assert chosen == [far] and skipped == []
    with pytest.raises(LookupError):
        risk_report.pick_items([far], at=NOW, horizon_hours=1, max_items=6, item_id=uuid4())


# ── 보고 전체 ─────────────────────────────────────────────────────
def test_the_report_counts_each_state_and_says_what_cached_mode_means():
    problem_cause = {"category": "traffic_control", "kind": "집회"}
    plan = {1: _check(), 2: _check(disruptions=[problem_cause]), 3: _check(failed=("earthquake",))}
    items = [_item(n, start_min=20 * n) for n in (1, 2, 3)]

    def check(*, place, starts_at, region="서울"):
        index = int((starts_at - NOW).total_seconds() // 60 // 20)
        return plan[index](place=place, starts_at=starts_at)

    report = risk_report.build_report(trip_id=UUID(int=1), version=3, items=items, check=check, at=NOW, horizon_hours=12, max_items=6, item_id=None, mode="cached")
    assert report["summary"] == {"problem": 1, "clear": 1, "unknown": 1, "checked": 3} and report["mode"] == "cached" and report["scope"] == "upcoming"
    assert [r["status"] for r in report["items"]] == ["clear", "problem", "unknown"] and report["version"] == 3
    assert any("바깥에 새로 묻지 않아요" in note for note in report["notes"])
    assert [c["category"] for c in report["categories"]] == list(NAMES)


def test_an_empty_window_is_said_out_loud():
    report = risk_report.build_report(trip_id=UUID(int=1), version=1, items=[_item(1, start_min=60 * 30)], check=_check(), at=NOW, horizon_hours=12,
                                      max_items=6, item_id=None, mode="fresh")
    assert report["items"] == [] and report["summary"]["checked"] == 0 and any("12시간 안" in note for note in report["notes"])
