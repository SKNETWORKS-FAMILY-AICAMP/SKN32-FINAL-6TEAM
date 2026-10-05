# -*- coding: utf-8 -*-
"""시나리오 감시 · 새벽 확인이 쓰는 문(`pending.apply_or_ask`)도 **일정 전체를 다시 판정한다** — D-017, 체크리스트 v2 T5. `[2026-10-03]`

☆왜: Case 버전의 적용기(`itinerary_actions`)는 자동 변경 전에 일정 전체를 다시 판정했지만(`INV-CS-ACT-004`), 기본 일꾼이 도는 시나리오 감시(`trip_watch`)와 새벽 확인(`dawn_check`)은
`apply_or_ask` 에서 판정 없이 바로 새 버전을 썼다 — 항목 하나를 점검해 고른 대체가 앞뒤 항목과 겹치거나 이동이 안 닿아도 그대로 들어갔다.

★지키려는 것: ①바꾼 뒤 **새로** 생긴 위반이 있으면 쓰지 않고 「일정은 그대로 두었어요」를 알린다(조용히 두면 닫힌 곳이 그대로 일정에 남는다) ②같은 사건 · 같은 판은 한 번만 알린다(감시가 몇 분마다 다시 와도)
③맞는 변경은 그대로 쓴다 ④최고 안이 걸리면 담당이 뽑아 둔 다음 순위 안을 쓴다(Case 와 같은 `fit_change`) ⑤두 호출자(`TripWatcher` · `DawnCheck`)가 이 결과를 센다.

재현:

    python -m pytest tests/scenario/test_apply_or_ask_recheck.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange
from app.domains.travel_ops.components.planning.pending import apply_or_ask
from app.domains.travel_ops.components.watch.trip_watch import TripTickResult, TripWatcher

from .test_case_version_day import case_world  # noqa: F401 — 픽스처를 그대로 쓴다

CAUSES = [{"category": "traffic_control", "kind": "road_closed", "summary": "도로 통제"}]


def _trip(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def _activity_followed_by_something(items):
    ordered = sorted(items, key=lambda i: (i.starts_at, i.seq))
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier.kind == "activity" and earlier.place is not None and later.kind != "mobility":
            return earlier, later
    raise AssertionError("시나리오에 활동 바로 뒤에 다른 항목이 오는 곳이 없다")


def _overlapping(item, later):
    """같은 장소 · 같은 시작이지만 다음 항목이 시작한 **뒤까지** 끝나는 대체 — 앞뒤와 겹친다."""
    return item.replaced_by(place=item.place, title=item.title + "(겹침)", ends_at=later.starts_at + timedelta(minutes=30))


def _change(item, replacement, *, to, fallbacks=()):
    return ItineraryChange(reason="auto_adjusted", causes=CAUSES, notice={"text": f"{to} 로 바꿨어요"},
                           replacements={item.item_id: replacement}, summary={"from": item.title, "to": to},
                           fallbacks=list(fallbacks))


def _run(world, item, change):
    with get_connection() as conn, conn.transaction():
        return apply_or_ask(conn, store=world["store"], trip_id=world["trip_id"], item_id=item.item_id, plan=change)


def _recheck_notices(world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice' "
                    "AND dedupe_key LIKE %s", (world["tenant"], "%:recheck:%"))
        return cur.fetchall()


# invariant: INV-CS-ACT-007
def test_a_change_that_breaks_the_whole_itinerary_is_not_written_and_the_customer_is_told(case_world):
    trip, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    change = _change(item, _overlapping(item, later), to=item.title + "(겹침)")

    outcome = _run(case_world, item, change)

    assert outcome["status"] == "rechecked" and outcome["item"] == item.title
    assert outcome["skipped"] and outcome["skipped"][0]["why"] == "schedule" and "겹친다" in outcome["skipped"][0]["reasons"][0]
    assert _trip(case_world)[0]["version"] == trip["version"]                       # ★아무것도 안 바뀌었다
    notices = _recheck_notices(case_world)
    assert len(notices) == 1
    payload = notices[0][1]
    assert payload["kind"] == "recheck_failed" and "일정은 그대로 두었어요" in payload["text"] and payload["item_id"] == str(item.item_id)
    assert payload["plan_url"]                                                       # 링크가 붙는다(상태의 정본 — v11 §6-A)


def test_the_same_event_on_the_same_version_is_told_only_once(case_world):
    """감시는 몇 분마다 다시 온다 — 같은 사건 · 같은 판이면 같은 알림을 또 내지 않는다."""
    _, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    change = _change(item, _overlapping(item, later), to=item.title + "(겹침)")
    for _ in range(3):
        assert _run(case_world, item, change)["status"] == "rechecked"
    assert len(_recheck_notices(case_world)) == 1


def test_a_change_that_fits_the_whole_itinerary_is_still_written(case_world):
    trip, items = _trip(case_world)
    item, _ = _activity_followed_by_something(items)
    harmless = item.replaced_by(place=item.place, title=item.title + "(대체)")
    outcome = _run(case_world, item, _change(item, harmless, to=harmless.title))

    assert outcome["status"] == "adjusted" and outcome["version"] == trip["version"] + 1
    assert outcome["summary"]["to"] == harmless.title and outcome["notice"]["text"] == f"{harmless.title} 로 바꿨어요"
    assert _recheck_notices(case_world) == []
    assert any(i.title == harmless.title for i in _trip(case_world)[1])


def test_when_the_best_option_fails_the_next_ranked_option_is_used_and_the_notice_says_why(case_world):
    trip, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    second = item.replaced_by(place=item.place, title=item.title + "(2순위)")
    change = _change(item, _overlapping(item, later), to=item.title + "(겹침)",
                     fallbacks=[_change(item, second, to=second.title)])

    outcome = _run(case_world, item, change)

    assert outcome["status"] == "adjusted" and outcome["summary"]["fit_rank"] == 2
    text = outcome["notice"]["text"]
    assert "1순위" in text and "2순위로 골랐어요" in text                           # 왜 1순위가 아닌지 알림에 적힌다
    assert any(i.title == second.title for i in _trip(case_world)[1])
    assert not any(i.title.endswith("(겹침)") for i in _trip(case_world)[1])


def test_the_scenario_watcher_counts_a_blocked_change_as_rechecked_not_adjusted(case_world):
    """`TripWatcher._apply` — 기본 일꾼이 부르는 자리. 막힌 변경은 `adjusted` 에 안 세고 `rechecked` 에 센다."""
    _, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    watcher = TripWatcher(store=case_world["store"], check=lambda **_: {}, connection_factory=get_connection,
                          clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")))
    result = TripTickResult()
    watcher._apply(case_world["trip_id"], item, _change(item, _overlapping(item, later), to="겹침"), result)

    assert result.adjusted == [] and result.asked == []
    assert [r["item"] for r in result.rechecked] == [item.title] and result.rechecked[0]["skipped"]
