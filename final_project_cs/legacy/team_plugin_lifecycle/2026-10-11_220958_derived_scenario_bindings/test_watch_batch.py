# -*- coding: utf-8 -*-
"""같은 여행의 문제는 **Case 하나 · 판 하나 · 알림 하나**로 — v11 §6-C-1. `[2026-10-03 사용자 지시]`

☆전에는 한 회차에 한 여행의 항목 둘이 깨지면 Case 둘이 열려 **판 둘 · 알림 둘**이 나갔다(앞 판이 낡은 알림을 먼저 보내고 곧 또 보낸다). 이제 같은 여행의 새 문제가 둘 이상이면 묶음 Case 하나를 열고
활동 Team 이 조정자가 되어 한 초안 위에서 차례로 고친다 — 적용은 코어가 Case 완료와 한 트랜잭션으로(`itinerary.apply` 제안 하나).

★지키려는 것
 ①새 문제가 둘 이상이면 Case 1 · 새 판 1 · 알림 1(「두 가지가 겹쳐 …」). 설정(`travel.watch.batch_enabled`)을 끄면 전처럼 항목마다(Case 2 · 판 2 · 알림 2)
 ②뒤 항목은 **앞에서 고친 초안 기준**이다(같은 곳을 또 고르지 않는다)
 ③「변경 안 할 일정」은 **바꾸지 않고 묻는다** — 나머지는 진행하고, 질문은 **새 판 기준**으로 연다(같은 판이면 곧 낡아 고르지 못한다). 묻는 알림은 제안마다 따로
 ④못 푼 항목만 있으면 판 없이 「그대로 두었어요」 알림 하나 — 그리고 **다음 회차에 같은 알림이 또 나가지 않는다**(항목의 정체로 덮은 Case 를 센다)
 ⑤안전 사건 줄이 알림의 맨 앞이고 머리가 「안전 알림」이다

재현:

    python -m pytest tests/scenario/test_watch_batch.py -v
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.core import settings as settings_module
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.scenarios.case_engine import CaseEngine
from app.domains.travel_ops.components.planning.pending import PendingStore

from .test_case_version_day import _classifier, _extractor, case_world  # noqa: F401 — 픽스처를 그대로 쓴다

ROAD = {"verdict": "disrupted", "disruptions": [{"category": "traffic_control", "kind": "road_closed"}]}
FIRE = {"verdict": "disrupted", "disruptions": [{"category": "disaster_msg", "kind": "fire"}]}
CLEAR = {"verdict": "clear", "disruptions": []}
FATAL = {"verdict": "fatal", "disruptions": []}
ALL_DAY = timedelta(hours=14)


@pytest.fixture()
def guardrails(monkeypatch):
    real = settings_module.get_guardrails()
    override: dict[str, object] = {}

    class Guard:
        def get(self, key, *args):
            return override[key] if key in override else real.get(key, *args)

    monkeypatch.setattr(settings_module, "get_guardrails", lambda: Guard())
    return override


def _engine(world, reports: dict[str, dict]):
    """`reports` — 장소 이름 → 그 장소의 점검 결과. 적힌 곳만 깨지고(일정의 원래 장소) 나머지(대체 후보)는 `clear`."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, place_id FROM places WHERE tenant_id=%s", (world["tenant"],))
        by_id = {str(place_id): reports[name] for name, place_id in cur.fetchall() if name in reports}

    def check(*, place, starts_at, **_):
        # ★읽기 도구는 장소의 **이름 없이** id · 좌표만 넘긴다 — id 로 가른다. 값이 호출 가능하면 부를 때마다 다음 결과(점검 소스가 잠깐 실패했다 돌아오는 시험)
        report = by_id.get(str(place.get("place_id")), CLEAR)
        return report() if callable(report) else report

    return CaseEngine(tenant_id=world["tenant"], check=check, route_events=world["engine"].opener.route_events,
                      classifier=_classifier, report_extractor=_extractor, clock=world["clock"])


def _tick(engine):
    return engine.opener.tick(lookahead=ALL_DAY)


def _versions(world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT version, reason, case_id FROM itinerary_versions WHERE tenant_id=%s AND trip_id=%s ORDER BY version",
                    (world["tenant"], world["trip_id"]))
        return cur.fetchall()


def _outbox(world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice' ORDER BY dedupe_key",
                    (world["tenant"],))
        return cur.fetchall()


def _latest(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def _status(world, case_id):
    with get_connection() as conn:
        return str(repository.get_case(conn, tenant_id=world["tenant"], case_id=case_id)["status"])


# 일정의 원래 장소 — 활동 하나(잠실 스카이타워) · 식사 하나(성수 점심 식당)
SKY, LUNCH = "잠실 스카이타워", "성수 점심 식당"


# ── ① Case 1 · 판 1 · 알림 1 ─────────────────────────────────────

# invariant: INV-CS-ACT-006
def test_two_broken_items_of_one_trip_become_one_case_one_version_and_one_notice(case_world):
    world = case_world
    result = _tick(_engine(world, {SKY: ROAD, LUNCH: ROAD}))

    [opened] = result.opened                                            # ★Case 가 하나다(전에는 둘)
    assert opened["issue_code"] == "batch" and len(opened["items"]) == 2
    assert [v[0] for v in _versions(world)] == [1, 2]                   # 판 하나만 더 생겼다(전에는 v3 까지)
    assert str(_versions(world)[1][2]) == opened["case_id"]             # 그 판은 이 묶음 Case 가 썼다
    assert _status(world, __import__("uuid").UUID(opened["case_id"])) == "resolved"

    notices = _outbox(world)
    assert len(notices) == 1                                            # 알림 하나
    payload = notices[0][1]
    assert payload["text"].startswith("일정에 문제가 두 가지 겹쳐서 이렇게 처리했어요.") and payload["batch"] is True
    assert len(payload["changes"]) == 2 and payload["version"] == 2 and payload["rollback"]                 # 되돌리기 제안이 붙는다(자동 변경)
    assert payload["text"].count("다른 안") == payload["text"].count("다른 안:")                           # 식당 문장에 이미 있는 「다른 안」을 또 붙이지 않는다
    assert all(payload["text"].count(f"다른 안: {name}") <= 1 for name in ("롯데월드 어드벤처", "성수 국수 식당(시나리오)"))
    _, items = _latest(world)
    names = {i.place["name"] for i in items if i.place}
    assert SKY not in names and LUNCH not in names                      # 둘 다 바뀌었다


def test_with_batching_off_each_item_keeps_its_own_case_version_and_notice(case_world, guardrails):
    """같은 입력을 묶음 없이 — 전의 동작이다(Case 2 · 판 3 까지 · 알림 2). 위 시험이 이 숫자와 달라야 의미가 있다."""
    guardrails["travel.watch.batch_enabled"] = False
    world = case_world
    result = _tick(_engine(world, {SKY: ROAD, LUNCH: ROAD}))

    assert len(result.opened) == 2
    assert [v[0] for v in _versions(world)] == [1, 2, 3]
    assert len(_outbox(world)) == 2


# ── ② 하나를 못 풀어도 나머지는 진행 ─────────────────────────────────

def test_one_that_cannot_be_solved_does_not_block_the_rest_and_is_told_in_the_same_notice(case_world):
    """스카이타워는 대체(아쿠아리움)가 있고, 성수 팝업 · 경복궁은 600m 안에 대체가 없다 — 전자는 적용하고 후자는 **그대로 두었다고** 같은 알림에 적는다."""
    world = case_world
    result = _tick(_engine(world, {SKY: ROAD, "성수동 팝업·향수 쇼룸 거리": ROAD, "경복궁": ROAD}))

    [opened] = result.opened
    assert len(opened["items"]) == 3 and [v[0] for v in _versions(world)] == [1, 2]
    _, items = _latest(world)
    names = {i.place["name"] for i in items if i.place}
    assert "아쿠아리움" in names and SKY not in names                                  # 풀리는 것은 풀렸다
    assert {"성수동 팝업·향수 쇼룸 거리", "경복궁"} <= names                             # 못 푼 것은 그대로다
    [(_, payload)] = _outbox(world)
    text = payload["text"]
    assert text.startswith("일정에 문제가 세 가지 겹쳐서 이렇게 처리했어요.")
    assert text.count("일정은 그대로 두었어요") == 2 and "가시기 전에 한 번 확인해 주세요." in text
    assert "사람" not in text and "담당자" not in text


# ── ③ 하나를 못 풀어도 나머지는 진행 · 묻는 것은 새 판 기준 ──────────

def test_a_pinned_item_is_asked_while_the_rest_is_applied_and_the_question_is_against_the_new_version(case_world):
    world = case_world
    with get_connection() as conn, conn.transaction():
        trip, items = world["store"].latest(conn, world["trip_id"])
        pinned = [i.replaced_by(place=i.place, title=i.title, detail={**i.detail, "customer_pinned": True})
                  if i.place and i.place["name"] == LUNCH else i for i in items]
        world["store"].append_version(conn, trip_id=world["trip_id"], base_version=trip["version"], items=pinned,
                                      reason="customer_request", causes=[])
    before = [v[0] for v in _versions(world)]
    result = _tick(_engine(world, {SKY: ROAD, LUNCH: ROAD}))

    [opened] = result.opened
    after = [v[0] for v in _versions(world)]
    assert after == [*before, before[-1] + 1]                            # 판은 활동 하나만 — 식당은 안 바뀌었다
    _, items = _latest(world)
    assert LUNCH in {i.place["name"] for i in items if i.place} and SKY not in {i.place["name"] for i in items if i.place}
    with get_connection() as conn:
        [proposal] = PendingStore(world["tenant"]).list(conn, world["trip_id"], only_open=True)
    assert proposal["reason"] == "protected" and proposal["base_version"] == after[-1]       # ★새 판이 기준이다
    keys = [key for key, _ in _outbox(world)]
    assert sum(1 for k in keys if ":proposal:" in k) == 1 and any(k.endswith(f":v{after[-1]}") for k in keys)
    notice = next(p for k, p in _outbox(world) if k.endswith(f":v{after[-1]}"))
    assert "변경하지 않기로 한 일정이라 바꾸지 않고" in notice["text"]       # 한 이야기로 읽히게 묻는 항목도 한 줄


def test_when_every_item_is_protected_no_version_is_written_and_each_question_is_against_the_current_version(case_world):
    """둘 다 「변경 안 할 일정」 — 판은 안 바뀌고(바꿀 것이 없다) 질문만 항목마다 따로 간다. 질문의 기준은 **지금 판**이다."""
    world = case_world
    with get_connection() as conn, conn.transaction():
        trip, items = world["store"].latest(conn, world["trip_id"])
        pinned = [i.replaced_by(place=i.place, title=i.title, detail={**i.detail, "customer_pinned": True})
                  if i.place and i.place["name"] in (SKY, LUNCH) else i for i in items]
        base = world["store"].append_version(conn, trip_id=world["trip_id"], base_version=trip["version"], items=pinned,
                                             reason="customer_request", causes=[])
    versions_before = [v[0] for v in _versions(world)]
    result = _tick(_engine(world, {SKY: ROAD, LUNCH: ROAD}))

    [opened] = result.opened
    assert [v[0] for v in _versions(world)] == versions_before                    # 판이 안 늘었다
    assert _status(world, __import__("uuid").UUID(opened["case_id"])) == "resolved"
    with get_connection() as conn:
        proposals = PendingStore(world["tenant"]).list(conn, world["trip_id"], only_open=True)
    assert len(proposals) == 2 and {p["base_version"] for p in proposals} == {base} and {p["reason"] for p in proposals} == {"protected"}
    assert sum(1 for key, _ in _outbox(world) if ":proposal:" in key) == 2         # 묻는 알림은 제안마다 따로(D-020 — 묶어서 묻지 않는다)
    again = _tick(_engine(world, {SKY: ROAD, LUNCH: ROAD}))                         # 다음 회차 — 같은 사건이라 새로 열지도 다시 묻지도 않는다
    assert again.opened == [] and len(_outbox(world)) == 2


# ── ④ 못 푼 것만 있으면 판 없이 알림 하나 — 다음 회차에 되풀이하지 않는다 ───

def test_when_nothing_can_be_changed_the_customer_hears_it_once_and_never_again_for_the_same_set(case_world):
    world = case_world
    everything = {SKY: ROAD, LUNCH: ROAD, "아쿠아리움": ROAD, "롯데월드 어드벤처": ROAD,
                  "성수 브런치 식당(시나리오)": ROAD, "성수 국수 식당(시나리오)": ROAD}      # 원래 곳도 대체 후보도 다 막혔다
    engine = _engine(world, everything)
    first = _tick(engine)

    [opened] = first.opened
    assert [v[0] for v in _versions(world)] == [1]                       # 판이 안 바뀌었다
    assert _status(world, __import__("uuid").UUID(opened["case_id"])) == "escalated"
    [(key, payload)] = _outbox(world)                                    # 항목마다가 아니라 **한 통**
    assert payload["type"] == "guidance" and payload["batch"] is True and payload["kind"] in ("no_alternate", "mixed")
    assert "잠실 스카이타워" in payload["text"] and "성수 점심 식사" in payload["text"] and "일정은 그대로 두었어요" in payload["text"]
    assert "사람" not in payload["text"] and "담당자" not in payload["text"]

    second, third = _tick(engine), _tick(engine)                          # ★같은 사건 — 다시 열지도 알리지도 않는다
    assert second.opened == [] and third.opened == [] and len(_outbox(world)) == 1
    assert len(second.existing) >= 2


# ── ⑤ 안전 사건이 맨 앞 ───────────────────────────────────────────

def test_the_safety_line_comes_first_and_the_notice_is_a_safety_alert(case_world):
    world = case_world
    # 활동(스카이타워)은 일반 사건, 식사(점심)는 안전 사건 — 시간 순서로는 활동이 앞이지만 알림은 안전 줄이 앞이다
    _tick(_engine(world, {SKY: ROAD, LUNCH: FIRE}))
    [(_, payload)] = _outbox(world)
    assert payload["type"] == "safety_alert" and payload["text"].startswith("⚠️ 안전 알림 — ")
    lines = [line for line in payload["text"].splitlines() if line.startswith("· ")]
    assert len(lines) == 2
    assert "성수 점심 식당" in lines[0] and "fire" in lines[0]                              # 첫 줄이 안전 사건(점심)이다
    assert "잠실 스카이타워" in lines[1] and "fire" not in lines[1]                         # 일반 사건(스카이타워)은 그 뒤다


# ── ⑥ 한 항목이 한 번만 — 단일 Case 가 덮은 항목은 묶음에 다시 안 들어간다 ──

def test_an_item_already_covered_by_a_single_case_is_not_pulled_into_a_later_batch(case_world, guardrails):
    world = case_world
    guardrails["travel.watch.batch_enabled"] = False
    dead_end = {SKY: ROAD, "아쿠아리움": ROAD, "롯데월드 어드벤처": ROAD}                    # 스카이타워는 깨졌고 대체도 없다 — 못 풀고 그대로 남는다
    first = _tick(_engine(world, dead_end))
    [single] = first.opened                                                                 # 단일 Case 하나가 스카이타워의 정체를 덮었다
    assert single["issue_code"] != "batch"

    guardrails["travel.watch.batch_enabled"] = True
    second = _tick(_engine(world, {**dead_end, "성수동 팝업·향수 쇼룸 거리": ROAD, "경복궁": ROAD}))
    [opened] = second.opened                                                                # 스카이타워도 아직 깨져 있지만 덮여 있다 — 묶음은 **새 문제 둘**만 담는다
    assert opened["issue_code"] == "batch" and len(opened["items"]) == 2
    assert not any("스카이타워" in title for title in opened["items"])
    assert any("스카이타워" in str(entry["item"]) for entry in second.existing)             # 덮여서 열지 않은 것으로 센다


# ── ⑦ 적대 검토(2026-10-03) — 묶음이 끝났어도 못 푼 항목은 다시 열린다 ──────

def test_a_source_failure_inside_a_completed_batch_is_reopened_alone_on_the_next_tick(case_world, guardrails):
    """★전에는 묶음 Case 가 `resolved` 로 닫히면 그 안의 점검 소스 실패 항목도 「끝났다」로 덮여 **영원히 다시 안 열렸다**(재난문자 소스가 잠깐 죽은 항목이 고쳐지지 않았다). 항목마다 다시 열 항목으로 남긴다."""
    guardrails.update({"travel.watch.retry_cooldown_seconds": 0, "travel.watch.retry_max": 3})
    world = case_world
    flaky = iter([ROAD, FATAL, ROAD, ROAD, ROAD])        # 감시가 보고(깨짐) → 묶음 Team 이 다시 점검(소스 실패) → 다음 회차(깨짐) → Team(깨짐)
    engine = _engine(world, {SKY: ROAD, LUNCH: lambda: next(flaky)})
    first = _tick(engine)

    [opened] = first.opened
    assert opened["issue_code"] == "batch" and _status(world, __import__("uuid").UUID(opened["case_id"])) == "resolved"
    assert [v[0] for v in _versions(world)] == [1, 2]                                       # 스카이타워만 바뀌었다
    names = {i.place["name"] for i in _latest(world)[1] if i.place}
    assert LUNCH in names and SKY not in names
    assert not [p for _, p in _outbox(world) if "점심" in p["text"] and "그대로 두었어요" in p["text"]]     # 소스 실패는 고객에게 알리지 않는다

    second = _tick(engine)
    [again] = second.opened                                                                # ★그 항목만 단일 Case 로 다시 열렸다
    assert again["issue_code"] != "batch" and "성수 점심" in again["item"]
    assert [r["attempt"] for r in second.retried] == [1]
    assert [v[0] for v in _versions(world)] == [1, 2, 3]
    assert LUNCH not in {i.place["name"] for i in _latest(world)[1] if i.place}             # 점심도 바뀌었다
