# -*- coding: utf-8 -*-
"""감시가 대안을 못 찾아도 **조건을 풀어 비슷한 안**을 고객에게 묻는다. `[2026-10-03 사용자 지적 — multi-agent flow 세션 전달]`

사용자 말: 「변경안 못 찾으면 탈락이고 그렇게 고객에게 알리지만, 그래도 최대한 유사한 대안 찾아서 고객에게 제공하는 걸로 논의되어 있지 않았어?」

☆왜: 조건을 풀어 되는 안을 찾는 계산(`itinerary_changes.relaxed_options` — 시각 늦추기 · 다음 일정 근처 · 반경 넓히기)은 **고객이 「다른 곳으로」를 요청한 길**에서만 불렀다.
감시 길(식사 · 활동 · 묶음)은 부르지 않아서 같은 조건으로 대안이 0곳이면 곧바로 「일정은 그대로 두었어요 + 원인」 알림으로 끝났다.

★지키려는 것
 ①감시가 바꿀 곳을 못 찾았을 때(`itinerary_unresolved`) · 찾은 안이 일정 전체 재판정에 다 걸렸을 때(`recheck_failed`) **옛 알림 대신 조건을 푼 안을 묻는다**(보류 제안, 이유 `relaxed`)
 ②**자동 적용하지 않는다** — 일정은 그대로(판 번호 그대로), 고르면 그때 바뀐다. 답이 없으면 그대로
 ③묻는 안은 **같은 원인을 다시 점검해 통과한 곳만**(활동 · 식사 모두) · 날씨 원인이면 활동은 실내만 · 고르면 그대로 적용될 안만(`plan_swap` 시뮬레이션 → 구조 위반 · 밀도 악화 없음)
 ④한 곳도 없으면 지금처럼 「일정은 그대로 두었어요」 · 같은 항목 · 같은 판에는 제안 하나(알림도 한 번) · 스위치(`travel.watch.relaxed_enabled`)를 끄면 전과 같다
 ⑤묶음 Case 의 못 푼 항목도 같다 — 묻는 항목은 「그대로 두었어요」 알림에서 빠지고 못 찾은 항목만 남는다

재현:

    python -m pytest tests/e2e/test_watch_relaxed.py -v
"""
from __future__ import annotations

import json
from uuid import UUID

import pytest

from app.core import settings as settings_module
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.watch import watch_relaxed
from app.domains.travel_ops.components.planning.replan import WEATHER_LIKE
from app.domains.travel_ops.components.watch.trip_watch_cases import Issue, TripWatchCaseOpener

from .test_ask_first import _proposals
from .test_trip_api import _at, _create, api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_watch_failures import DISRUPTED, SAFETY, _escalating, _notices, _opener, _tick, guardrails  # noqa: F401 — `guardrails`: 묶음을 꺼 둔 같은 환경

WEEK = {d: {"open": "09:00", "close": "21:00", "last_entry": "20:30"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
PALACE = "경복궁"                       # 시나리오의 15:30 활동 — 이 곳만 「도로 통제」에 걸린다고 본다


def _only(names, report=DISRUPTED):
    """이름이 `names` 인 곳만 깨졌다고 보는 점검기 — 그 밖의 곳은 `clear`(후보가 통과하는 길)."""
    def check(*, place, starts_at):
        return report if place.get("name") in names else {"verdict": "clear", "disruptions": []}
    return check


def _catalog(api, content_id, title, lat, lon, ctype="12", indoor=False):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO place_catalog (tenant_id, source, content_id, content_type_id, title, address, latitude, longitude) "
                    "VALUES (%s,'tour_api',%s,%s,%s,'서울특별시 종로구 사직로 1',%s,%s) ON CONFLICT DO NOTHING",
                    (api["tenant"], content_id, ctype, title, lat, lon))
        cur.execute("INSERT INTO catalog_hours (tenant_id, source, content_id, content_type_id, hours_week, hours_read, read_at) "
                    "VALUES (%s,'tour_api',%s,%s,%s,%s, now()) ON CONFLICT DO NOTHING",
                    (api["tenant"], content_id, ctype, json.dumps(WEEK), json.dumps({"source": "tour_api", "method": "test"})))


@pytest.fixture()
def world(api):  # noqa: F811
    """시나리오 여행 + 경복궁 둘레에 열려 있는 관광공사 활동 둘(창덕궁 · 덕수궁). 끝나면 시험이 넣은 목록 줄을 지운다."""
    trip_id = _create(api)["trip_id"]
    _catalog(api, "930001", "창덕궁", 37.5794, 126.9910)
    _catalog(api, "930002", "덕수궁", 37.5658, 126.9751)
    yield {**api, "trip_id": UUID(trip_id)}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for table in ("catalog_hours", "place_catalog"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (api["tenant"],))


@pytest.fixture()
def lenient(monkeypatch):
    """일정 전체 재판정(`introduced_violations`)을 통과시킨다 — 시나리오 일정은 이동 항목이 고정 소요(30분)로 박혀 있어 **어떤 대체든** 새 이동에서 「소요가 안 맞는다」가 나온다.
    이 시험들은 감시 → 제안의 **연결**을 본다. 재판정이 안을 거르는 것은 아래 `test_options_that_break_...` 가 진짜 판정으로 따로 본다."""
    monkeypatch.setattr(watch_relaxed, "introduced_violations", lambda trip, current, new_items: [])


def _unresolved_tick(world, check):
    opener = _opener(world, check, _escalating("itinerary_unresolved"), hhmm="15:00")
    return opener, _tick(opener)


def _kinds(world, key):
    return [n for n in _notices(world) if n.get("kind") == key]


def _palace(world):
    with get_connection() as conn:
        _, items = world["store"].latest(conn, world["trip_id"])
    return next(i for i in items if i.place and i.place["name"] == PALACE)


# invariant: INV-CS-ACT-012
def test_when_the_watch_finds_no_alternative_it_asks_about_similar_ones_instead_of_only_saying_nothing_was_found(world, lenient):
    version_before = _version(world)
    opener, first = _unresolved_tick(world, _only({PALACE}))
    mine = [r for r in first.relaxed if r["item"] == _palace(world).title]
    assert len(mine) == 1 and mine[0]["options"] and not mine[0]["already"]                          # ★제안으로 물었다
    # 옛 알림(「대신 갈 수 있는 곳을 찾지 못해」)은 이 항목에는 안 나갔다
    assert all(_palace(world).title not in n["text"] for n in _kinds(world, "no_alternate"))
    [proposal] = [p for p in _proposals(world, world["trip_id"]) if p["item_id"] == _palace(world).item_id]
    assert proposal["reason"] == "relaxed" and proposal["status"] == "open"
    names = {o["name"] for o in proposal["options_json"]}
    assert names and PALACE not in names                                                           # 같은 원인을 통과한 곳 — 원래 곳은 없다
    assert all(o.get("note") for o in proposal["options_json"]) and [o["rank"] for o in proposal["options_json"]] == list(range(1, len(names) + 1))
    # 묻는 알림 — 「그대로 두었어요」 + 「고르시면 바꿀게요」 + 답 없으면 그대로
    [message] = [m for m in _messages(world) if m.get("proposal_id") == str(proposal["proposal_id"])]
    assert message["type"] == "proposal_request" and message["reason"] == "relaxed"
    assert "일정은 그대로 두었어요" in message["text"] and "고르시면 바꿀게요" in message["text"] and "답이 없으면" in message["text"]
    assert "도로가 통제돼요" in message["text"] and "road_closed" not in message["text"]                  # 원인 코드 이름이 고객 문장에 새지 않는다
    assert any(name in message["text"] for name in names)
    assert _version(world) == version_before                                                       # ★자동 적용하지 않았다


def test_choosing_an_asked_option_changes_the_item_and_declining_leaves_it(world, lenient):
    _unresolved_tick(world, _only({PALACE}))
    [proposal] = [p for p in _proposals(world, world["trip_id"]) if p["item_id"] == _palace(world).item_id]
    option = proposal["options_json"][0]
    version = _version(world)
    chosen = world["client"].post(f"/v1/trips/{world['trip_id']}/proposals/{proposal['proposal_id']}/choose",
                                  json={"key": option["key"]}, headers=world["auth"]("trip:write"))
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["status"] == "chosen" and _version(world) == version + 1
    with get_connection() as conn:
        _, items = world["store"].latest(conn, world["trip_id"])
    assert any(i.place and i.place["name"] == option["name"] for i in items) and not any(i.place and i.place["name"] == PALACE for i in items)


def test_options_that_fail_the_same_check_are_not_offered_and_the_old_notice_goes_out(world):
    version_before = _version(world)
    _, first = _unresolved_tick(world, _only({PALACE, "창덕궁", "덕수궁"}))                          # 후보도 같은 원인에 걸렸다
    assert first.relaxed == []
    assert any(_palace(world).title in n["text"] for n in _kinds(world, "no_alternate"))              # 지금처럼 「일정은 그대로 두었어요」
    assert [p for p in _proposals(world, world["trip_id"]) if p["reason"] == "relaxed"] == []
    assert _version(world) == version_before


def test_options_that_break_the_whole_itinerary_are_not_offered_with_the_real_judge(world):
    """진짜 재판정으로 — 시나리오 일정에서는 대체가 새 이동 소요와 안 맞아(「30분으로 잡혔는데 60분 걸린다」) 안이 걸러지고, 한 곳도 안 남으면 옛 알림이 나간다(고르게 두지 않는다)."""
    version_before = _version(world)
    _, first = _unresolved_tick(world, _only({PALACE}))
    assert first.relaxed == [] and any(_palace(world).title in n["text"] for n in _kinds(world, "no_alternate"))
    assert [p for p in _proposals(world, world["trip_id"]) if p["reason"] == "relaxed"] == [] and _version(world) == version_before


def test_an_option_that_makes_the_day_denser_than_wanted_is_dropped_but_the_others_stay(world, lenient, monkeypatch):
    seen: list[str] = []
    real = watch_relaxed.density_regressions

    def regress_first(constraints, before, after):
        seen.append("call")
        return ["worse"] if len(seen) == 1 else real(constraints, before, after)       # 첫 안만 하루가 빡빡해진다고 본다

    monkeypatch.setattr(watch_relaxed, "density_regressions", regress_first)
    opener, first = _unresolved_tick(world, _only({PALACE}))
    offered = [r for r in first.relaxed if r["item"] == _palace(world).title]
    assert len(seen) >= 2 and offered                                                  # 안마다 밀도를 봤고 하나가 빠져도 나머지는 물었다
    [proposal] = [p for p in _proposals(world, world["trip_id"]) if p["item_id"] == _palace(world).item_id]
    assert [o["rank"] for o in proposal["options_json"]] == list(range(1, len(proposal["options_json"]) + 1))      # 순위가 다시 매겨진다
    assert all(o["name"] != "창덕궁" for o in proposal["options_json"])                 # 첫 안(시각 늦추기 창덕궁)이 빠졌다


def test_a_safety_event_is_still_a_safety_alert_when_it_asks(world, lenient):
    _unresolved_tick(world, _only({PALACE}, report=SAFETY))
    messages = [m for m in _messages(world) if m.get("reason") == "relaxed"]
    assert messages and all(m["type"] == "safety_alert" and m["text"].startswith("⚠️ 안전 알림") for m in messages)


def test_weather_keeps_activities_indoors_so_no_outdoor_option_is_offered(world, lenient):
    rain = {"verdict": "disrupted", "disruptions": [{"category": sorted(WEATHER_LIKE)[0], "kind": "rain"}]}
    _, first = _unresolved_tick(world, _only({PALACE}, report=rain))
    # 시험이 넣은 후보(창덕궁 · 덕수궁)에는 「실내」 표시가 없다 — 비를 피하려고 고른 곳이 또 야외일 수 있어 안 올린다(`activity_candidates` 와 같은 규칙)
    offered = {name for r in first.relaxed if r["item"] == _palace(world).title for name in r["options"]}
    assert not offered & {"창덕궁", "덕수궁"}


def test_the_same_event_and_version_ask_once_and_a_repeat_makes_no_second_message(world, lenient):
    opener, first = _unresolved_tick(world, _only({PALACE}))
    count = len([m for m in _messages(world) if m.get("reason") == "relaxed"])
    assert count == len(first.relaxed) >= 1
    second = _tick(opener)                                                                         # 같은 사건이 그대로 — 같은 Case 로 모인다
    assert second.relaxed == [] and len([m for m in _messages(world) if m.get("reason") == "relaxed"]) == count
    # 직접 다시 불러도 제안은 하나 — 이미 있다고 답한다
    again = watch_relaxed.try_offer(get_connection, store=world["store"], trip_id=world["trip_id"], item_id=_palace(world).item_id,
                                    causes=DISRUPTED["disruptions"], check=_only({PALACE}))
    assert again is not None and again["already"] is True and len([m for m in _messages(world) if m.get("reason") == "relaxed"]) == count


def test_the_switch_turns_it_off_and_nothing_else_changes(world, guardrails):
    guardrails["travel.watch.relaxed_enabled"] = False
    _, first = _unresolved_tick(world, _only({PALACE}))
    assert first.relaxed == [] and any(_palace(world).title in n["text"] for n in _kinds(world, "no_alternate"))


def test_a_recheck_failure_asks_too_and_says_the_found_one_did_not_fit(world, lenient):
    """찾은 안이 일정 전체와 안 맞아 끝난 Case(`itinerary_recheck_failed`)도 같다 — 문장이 「찾았지만 일정 전체와 맞지 않았어요」로 갈린다."""
    _, first = _unresolved_tick_with(world, _only({PALACE}), "itinerary_recheck_failed")
    assert first.relaxed
    [message] = [m for m in _messages(world) if m.get("reason") == "relaxed" and _palace(world).title in m["text"]]
    assert "찾았지만 일정 전체와 맞지 않았어요" in message["text"] and "일정은 그대로 두었어요" in message["text"]


def test_in_a_batch_the_asked_items_leave_the_unchanged_notice_and_only_the_unsolved_remain(world, lenient):
    """묶음 Case 가 아무것도 못 바꾸고 끝났다 — 못 푼 두 항목 가운데 비슷한 안이 있는 항목은 묻고, 없는 항목만 「그대로 두었어요」로 남는다."""
    palace = _palace(world)
    with get_connection() as conn:
        _, items = world["store"].latest(conn, world["trip_id"])
    other = next(i for i in items if i.kind == "activity" and i.place and i.place["name"] == "롯데마트 서울역점")
    check = _only({PALACE, "롯데마트 서울역점", "창덕궁"})                      # 롯데마트 쪽은 후보(덕수궁은 가깝지만 이 시각 · 거리 밖이거나 통과)를 못 쓴다고 보지는 않는다 — 결과는 아래서 가른다
    opener = TripWatchCaseOpener(store=world["store"], check=check, connection_factory=get_connection, clock=lambda: _at("15:00"),
                                 repository=None, run_case=None, route_events=None)
    issues = [Issue(world["trip_id"], palace, DISRUPTED["disruptions"], "activity_other", "place"),
              Issue(world["trip_id"], other, DISRUPTED["disruptions"], "activity_other", "place")]
    observed = " ".join(f"outcome:{i.item.item_id}:no_alternate" for i in issues)
    opener._escalation = lambda case_id: ("itinerary_unresolved", observed)           # 묶음 Team 이 항목별 표지를 남기고 끝난 것
    from app.domains.travel_ops.components.watch.trip_watch_cases import CaseTickResult

    result = CaseTickResult()
    opener._after_batch(UUID(int=1), {"trip_id": world["trip_id"], "batch": issues}, result)
    asked_titles = {r["item"] for r in result.relaxed}
    unchanged = [n for n in _notices(world) if n.get("batch") and n.get("kind") in ("no_alternate", "recheck_failed", "mixed")]
    told = {t for n in unchanged for t in n["text"].split("\n") if "그대로 두었어요" in t}
    assert palace.title in asked_titles                                              # 경복궁은 비슷한 안이 있어 물었다
    assert all(palace.title not in line for line in told)                            # 그래서 「그대로 두었어요」 줄에서 빠졌다
    for title in {i.item.title for i in issues} - asked_titles:                      # 묻지 못한 항목은 지금처럼 남는다
        assert any(title in line for line in told)


# ── 도우미 ──────────────────────────────────────────────────────────
def _unresolved_tick_with(world, check, guardrail):
    opener = _opener(world, check, _escalating(guardrail), hhmm="15:00")
    return opener, _tick(opener)


def _version(world) -> int:
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])[0]["version"]


def _messages(world):
    """이 여행의 알림(통지 · 제안 알림) 전부 — 한 주제(`trip.notice`)로 나간다."""
    return _notices(world)
