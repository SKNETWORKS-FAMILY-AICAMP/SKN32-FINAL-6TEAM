# -*- coding: utf-8 -*-
"""알림 센터가 그대로 보이는 서버 값 · 문장 `[2026-10-23 사용자 지시 — ST4F-723]`.

웹 알림 센터 개편(ST4F-723) 때 서버 쪽 결함으로 남은 것들 — 계약 `wiki/external/rest-endpoints/web-access.md`
「알림 목록의 `changed`」 · `trips.md` 「보류 제안」:

 ①알림 목록(`GET …/notices`)이 알림 payload 의 「바뀌기 전 → 뒤」(`changed`)를 내보내지 않았다 → `changed[]`
 ②고르면 그 일정이 새 id 가 되는데 어디에도 안 적혀 닫힌 제안과 지금 일정을 못 이었다 → 고른 제안 알림의 `changed` 에 두 id
 ③제안 안의 경고가 해라체(「…없다」)였다 → 해요체(경고를 가리는 앞머리 「가격을 몰라」는 그대로)
 ④자동 변경 문장의 조사가 「는 · 으로」 고정 ⑤늘 「오늘」 → 받침 · 그 일정의 날짜로
 ⑥고객 문장에 마크다운 별표(`**…**`) ⑦안 고르기 거절 문장이 해라체

재현:

    python -m pytest tests/unit/travel/test_notice_center_server_text.py -v
"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning import pending
from app.domains.travel_ops.components.planning.pending import Decision, PendingStore, ProposalRefused, proposal_notice
from app.domains.travel_ops.components.planning.replan import activity_candidates, change_notice, ledger_warnings
from app.domains.travel_ops.components.watch.trip_watch_batch import Outcome, digest
from app.domains.travel_ops.components.watch.watch_relaxed import relaxed_text
from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.entry.trip_api import _notice_changed

KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")
START = datetime(2026, 10, 25, 10, 0, tzinfo=KST)          # 일요일 오전
AIR = [{"category": "air_quality"}]


def _place(name, *, building=None, floor=None, lat=37.5, **attributes):
    attrs = {**attributes, **({"building": building} if building else {}), **({"floor": floor} if floor else {})}
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": lat, "longitude": 127.0,
            "weather_sensitive": False, "attributes": attrs}


def _item(title, place, start=START, **detail):
    return Item(item_id=uuid4(), seq=1, kind="activity", title=title, place_id=place["place_id"],
                starts_at=start, ends_at=start + timedelta(hours=1), detail=dict(detail), place=place)


# ── ① 알림 목록의 `changed` ─────────────────────────────────────

def test_a_single_change_is_exported_with_the_time_in_seoul_and_no_invented_ids():
    payload = {"type": "change_notice", "changed": {"from": "경복궁", "to": "국립고궁박물관", "at": "2026-10-25T01:00:00+00:00"}}
    assert _notice_changed(payload) == [{"item_id": None, "new_item_id": None, "from": "경복궁", "to": "국립고궁박물관",
                                         "at": "2026-10-25T10:00:00+09:00"}]


def test_a_chosen_proposal_carries_both_item_ids():
    payload = {"type": "change_notice", "proposal_id": "p1",
               "changed": {"from": "학고재", "to": "이솝 삼청", "at": "2026-10-25T10:45:00+09:00", "item_id": "old", "new_item_id": "new"}}
    [row] = _notice_changed(payload)
    assert (row["item_id"], row["new_item_id"], row["from"], row["to"]) == ("old", "new", "학고재", "이솝 삼청")


def test_a_watch_batch_exports_one_row_per_changed_item_with_its_item_id():
    payload = {"type": "change_notice", "batch": True, "changed": None,
               "changes": [{"item_id": "a", "text": "…", "changed": {"from": "잠실 전망대", "to": "아쿠아리움", "at": "2026-10-25T10:00:00+09:00"}},
                           {"item_id": "b", "text": "…", "changed": {"from": "지하철", "to": "버스"}},          # 이동 수단 — 시각 없음
                           {"item_id": "c", "text": "…", "changed": None}]}
    assert _notice_changed(payload) == [
        {"item_id": "a", "new_item_id": None, "from": "잠실 전망대", "to": "아쿠아리움", "at": "2026-10-25T10:00:00+09:00"},
        {"item_id": "b", "new_item_id": None, "from": "지하철", "to": "버스", "at": None}]


@pytest.mark.parametrize("payload", [
    {"type": "guidance", "text": "좋은 아침이에요!"},                                  # 안내 — changed 없음
    {"type": "change_notice", "changed": None},                                        # 등록
    {"changed": {"rollback_to": 1, "restored": ["경복궁"]}},                            # 되돌리기
    {"changed": {"progress": "advance_trip"}},                                          # 진행 「끝났어요」
    {"changed": {"requested_place": "스타벅스"}},                                       # 이름만 받은 목적지
    {"changed": {"edit": {"changed": 1, "added": 0, "removed": 0}}},                    # 일정 수정 「완료」
    {"type": "change_notice", "changed": None, "changes": []},                          # 묶음인데 바꾼 것이 없다
])
def test_notices_without_a_from_to_pair_export_null(payload):
    assert _notice_changed(payload) is None


def test_an_unreadable_time_is_passed_as_written():
    [row] = _notice_changed({"changed": {"from": "가", "to": "나", "at": "곧"}})
    assert row["at"] == "곧"


# ── ② 고른 제안의 바뀐 뒤 일정 id ────────────────────────────────

def test_choosing_writes_the_old_and_new_item_ids_into_the_change_notice(monkeypatch):
    origin, other = _place("학고재"), _place("이솝 삼청", lat=37.501)
    current = _item("학고재 관람", origin)
    proposal_id = uuid4()
    options = [{"key": other["place_id"], "rank": 1, "name": other["name"], "place_id": other["place_id"],
                "starts_at": START.isoformat(), "ends_at": (START + timedelta(hours=1)).isoformat()}]
    proposal = {"proposal_id": proposal_id, "item_id": current.item_id, "base_version": 1, "reason": "ask_first",
                "status": "open", "expires_at": START + timedelta(hours=1), "options_json": options, "protected_by": None}
    closed, notices, written = [], [], []

    class Store:
        tenant_id = "unit"

        def latest(self, conn, trip_id):
            return {"version": 1, "constraints": {}}, [current]

        def append_version(self, conn, **kw):
            written.append(kw["items"])
            return 2

        def enqueue_notice(self, conn, **kw):
            notices.append(kw["payload"])

    monkeypatch.setattr(PendingStore, "get", lambda self, conn, trip_id, pid, lock=False: dict(proposal))
    monkeypatch.setattr(PendingStore, "close", lambda self, conn, pid, **kw: closed.append(kw) or True)
    result = pending.choose(conn=None, store=Store(), pending=PendingStore("unit"), trip_id=uuid4(), proposal_id=proposal_id,
                            key=other["place_id"], by="web:unit", places_by_id={other["place_id"]: other}, check=None,
                            now=START - timedelta(hours=2))

    assert result["status"] == "chosen" and closed[-1]["status"] == "chosen"
    [new] = [i for i in written[0] if i.replaces_item_id == current.item_id]
    [payload] = notices
    assert payload["proposal_id"] == str(proposal_id)
    assert payload["changed"]["item_id"] == str(current.item_id) and payload["changed"]["new_item_id"] == str(new.item_id)
    assert (payload["changed"]["from"], payload["changed"]["to"]) == ("학고재", "이솝 삼청")
    [row] = _notice_changed(payload)                                              # 목록이 그대로 내보낸다
    assert row["new_item_id"] == str(new.item_id) and row["item_id"] == str(current.item_id)


# ── ③ 제안 안의 경고 해요체 ──────────────────────────────────────

def test_proposal_warnings_are_polite_but_the_rejection_reason_keeps_its_wording():
    origin = _place("원래 전망대", price_krw=10000)
    unknown = _place("값 모르는 전시관", lat=37.501)                                 # 가격 · 영업시간 모름
    [asked] = activity_candidates(original=origin, places=[origin, unknown], start=START, end=START + timedelta(hours=1),
                                  causes=AIR, proposal=True)
    assert asked.warnings == ["가격을 몰라 추가 비용을 계산할 수 없어요", "그 시각 영업을 확인할 수 없어요"] and asked.rejected == []
    [auto] = activity_candidates(original=origin, places=[origin, unknown], start=START, end=START + timedelta(hours=1),
                                 causes=AIR, proposal=False)
    assert auto.warnings == ["가격을 몰라 추가 비용을 계산할 수 없어요"]
    assert auto.rejected == ["그 시각 영업을 확인할 수 없다"]                        # 탈락 사유(진단 기록)는 그대로


def test_ledger_warnings_are_polite():
    assert ledger_warnings({"linked": True, "needs_holiday_check": True, "needs_check": True}) == [
        "명절이나 공휴일이라 영업시간이 다를 수 있어요", "영업 종료가 임박해 마지막 주문을 확인해야 해요"]


def test_the_proposal_frame_is_unchanged_and_carries_the_option_warnings_word_for_word():
    origin = _place("학고재")
    item = _item("학고재 관람", origin)
    options = [{"key": "a", "rank": 1, "name": "이솝 삼청"},
               {"key": "b", "rank": 2, "name": "아트스페이스3", "warnings": ["가격을 몰라 추가 비용을 계산할 수 없어요",
                                                                             "그 시각 영업을 확인할 수 없어요"]}]
    notice = proposal_notice(item=item, decision=Decision("ask", "ask_first", None, False),
                             causes=[{"category": "forecast"}], options=options, proposal_id=uuid4())
    assert notice["text"] == ("학고재 관람 — 날씨 예보에 문제가 있어요. 어떻게 할까요? 1) 이솝 삼청 · 2) 아트스페이스3 "
                              "아트스페이스3: 가격을 몰라 추가 비용을 계산할 수 없어요 아트스페이스3: 그 시각 영업을 확인할 수 없어요 "
                              "답이 없으면 원래 일정을 그대로 둡니다.")
    assert notice["options"][1]["warnings"] == options[1]["warnings"]


# ── ④ · ⑤ 자동 변경 문장 — 조사 · 날짜 ─────────────────────────────

def _change_text(original, replacement, *, now, start=START):
    return change_notice(original=original, replacement=replacement, start=start, causes=AIR,
                         alternates=[], replay=False, now=now)["text"]


def test_the_scenario_sentence_is_unchanged_on_the_same_day():
    original = _place("잠실 스카이타워", building="롯데", area="야외 전망 데크", view_dependent=True)
    replacement = _place("아쿠아리움", building="롯데", floor="지하 1층")
    assert _change_text(original, replacement, now=START - timedelta(hours=2)) == (
        "오늘 오전 잠실 스카이타워 야외 전망 데크는 시야 확보가 어려울 것으로 예상되어, 같은 건물 지하 1층 아쿠아리움으로 변경됩니다.")


@pytest.mark.parametrize("before, after, expected", [
    ("경복궁", "롯데월드몰", "경복궁은 미세먼지 기준을 넘어 야외 활동이 어려울 것으로 예상되어, 롯데월드몰로 변경됩니다."),      # ㅇ 받침 · ㄹ 받침은 「로」
    ("서울숲", "N서울타워", "서울숲은 미세먼지 기준을 넘어 야외 활동이 어려울 것으로 예상되어, N서울타워로 변경됩니다."),        # 받침 없음 → 「로」
    ("남산타워", "국립중앙박물관", "남산타워는 미세먼지 기준을 넘어 야외 활동이 어려울 것으로 예상되어, 국립중앙박물관으로 변경됩니다."),
])
def test_particles_follow_the_final_syllable(before, after, expected):
    assert _change_text(_place(before), _place(after), now=START - timedelta(hours=1)) == "오늘 오전 " + expected


@pytest.mark.parametrize("now, day", [
    (START - timedelta(hours=1), "오늘"),
    (START - timedelta(days=1), "내일"),
    (START - timedelta(days=3), "10월 25일(일)"),
    # 서울 날짜로 견준다 — 세계 표준시로는 10월 24일 · 25일(「내일」)이지만 서울로는 둘 다 25일
    (datetime(2026, 10, 24, 16, 0, tzinfo=UTC), "오늘"),
])
def test_the_day_word_is_the_stops_seoul_date_against_when_the_notice_is_made(now, day):
    start = datetime(2026, 10, 25, 1, 0, tzinfo=UTC)                                 # 서울 10:00
    text = _change_text(_place("경복궁"), _place("국립고궁박물관"), now=now, start=start)
    assert text.startswith(f"{day} 오전 경복궁은 ")


# ── ⑥ 마크다운 별표 없음 ─────────────────────────────────────────

@pytest.mark.parametrize("kind", ["unhandled", "recheck_failed", "no_alternate"])
def test_the_watch_sentences_carry_no_markdown(kind):
    item = _item("경복궁 관람", _place("경복궁"))
    text = digest([Outcome(item, kind, causes=[{"category": "traffic_control", "kind": "road_closed"}], reasons=["x"])],
                  kind="guidance")["text"]
    assert "**" not in text and "일정은 그대로 두었어요." in text


def test_the_relaxed_offer_carries_no_markdown():
    item = _item("경복궁 관람", _place("경복궁"))
    text = relaxed_text(item=item, causes=[{"category": "traffic_control", "kind": "road_closed"}],
                        options=[{"rank": 1, "name": "창덕궁", "note": "11:00으로 늦추면"}], recheck_failed=False)
    assert "**" not in text and "그래서 일정은 그대로 두었어요. " in text


# ── ⑦ 안 고르기 거절 문장 ────────────────────────────────────────

def test_the_choose_refusal_is_polite_and_keeps_its_code_and_status(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.domains.travel_ops.modules.web_account import web_cookie, web_guard

    owner, trip_id = uuid4(), uuid4()
    now = datetime.now(KST)

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def transaction(self): return nullcontext()

    store = SimpleNamespace(tenant_id="unit", latest=lambda *a: ({"customer_id": owner, "version": 1}, []),
                            places=lambda *a: [])
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    monkeypatch.setattr(trip_api, "get_connection", Connection)
    monkeypatch.setattr(trip_api, "TripStore", lambda tenant: store)
    monkeypatch.setattr(web_cookie, "get_connection", Connection)
    monkeypatch.setattr(web_cookie, "cookie_name", lambda: "test_session")
    monkeypatch.setattr(web_cookie, "csrf_token", lambda *a: "valid-csrf")
    monkeypatch.setattr(web_cookie, "_admin_access", lambda *a: None)
    monkeypatch.setattr(web_cookie, "_consent_gate", lambda *a: None)
    monkeypatch.setattr(web_cookie, "resolve_key", lambda *a, **k: None)
    monkeypatch.setattr(web_cookie, "lookup", lambda *a, **k: web_cookie.Session(
        owner, "synthetic", "member", now + timedelta(days=1), now + timedelta(days=1)))

    def refuse(**kwargs):
        raise ProposalRefused("unknown_choice", {"choices": ["a"]})

    monkeypatch.setattr(pending, "choose", refuse)
    app = FastAPI()
    app.include_router(trip_api.build_trip_router(check_factory=lambda: None))
    client = TestClient(app)
    client.cookies.set("test_session", "synthetic")
    response = client.post(f"/v1/web/trips/{trip_id}/proposals/{uuid4()}/choose", json={"key": None},
                           headers={"sec-fetch-site": "same-origin", "x-csrf-token": "valid-csrf"})
    assert response.status_code == 422
    error = response.json()["detail"]["error"]
    assert error["code"] == "unknown_choice" and error["detail"] == {"choices": ["a"]}
    assert error["message"] == "안을 고르지 못했어요 — 아무것도 바뀌지 않았어요."
