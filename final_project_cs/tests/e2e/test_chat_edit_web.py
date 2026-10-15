# -*- coding: utf-8 -*-
"""채팅으로 일정 고치기 — 웹 「일정 수정」과 같은 길(`chat_edit`)로 **실제로 새 판을 쓰는지** 본다. `[2026-10-15 사용자 지시]`

☆10-14 x600 실서버 재시험: 시각 옮기기 51건 중 40 · 넣기 8/8 · 빼기 10/11 이 「아직 채팅에서 하지 못해요」로 막혔고, 「경복궁 대신 창덕궁 가자」는
  「바로 바꾸는 기능은 아직 없어요」였다. 사용자: 「이미 있는 기능 그냥 써서 처리해서 답 주면 되는 건데 왜 안 하고 있었어?」

해석 모델은 **자동 시험용 고정 답**(`_answer`)이다 — 서버가 그 해석을 받아 실제로 고치는지만 본다. 모델 정확도는 재생 시험이 잰다.
여행은 웹 「일정 수정」 시험과 같은 것이다(`test_trip_reopen._trip` — 어제 경복궁(끝남) · 내일 북촌 → 인사동 → N서울타워, 덕수궁은 등록만 한 공용 장소).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore

from .test_decision_unit_web import decided  # noqa: F401 — 시험 준비물
from .test_trip_reopen import _member, _trip
from .test_web_api import _fresh_limit_cache, _h, api  # noqa: F401

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture()
def chat(decided, api):
    _member(api, decided["key"])                      # 게스트 제한(여행 1개)과 섞지 않는다 — 시험 준비물이 이미 여행 하나를 만들었다
    trip = _trip({"client": decided["client"]}, decided["key"])
    return {**decided, "trip": trip, "tenant": api["tenant"]}


def _answer(chat, action, *, target=None, **fields):
    """다음 해석 답을 고정한다 — `target` · `anchor` 는 일정 이름 조각(받은 일정 목록에서 별칭을 찾는다)."""
    decider = chat["decider"]

    def structured(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        alias = (lambda name: decider._alias(user, name) if name else "none")
        extra = dict(fields)
        if "anchor" in extra:
            extra["anchor_item"] = alias(extra.pop("anchor"))
        return {"action": action, "target_item": alias(target), "target_change": "none", "fact": "none", "minutes": 0,
                "choices": [], "reads": [], "social": "", "general_requests": [], "change_scope": "none",
                "destination_text": "", "condition_text": "", **extra}
    decider.structured = structured


def _say(chat, text, request_id):
    response = chat["client"].post(f"/v1/web/trips/{chat['trip']['trip_id']}/messages", headers=_h(chat["key"]),
                                   json={"request_id": request_id, "message": text, "at": datetime.now(KST).isoformat()})
    assert response.status_code == 200, response.text
    return response.json()


def _latest(chat):
    with get_connection() as conn:
        trip, items = TripStore(chat["tenant"]).latest(conn, UUID(str(chat["trip"]["trip_id"])))
    return trip["version"], {i.title: i for i in items if i.kind != "mobility"}


def _hm(moment):
    return moment.astimezone(KST).strftime("%H:%M")


def test_a_stop_is_moved_later_by_the_minutes_said(chat):
    before, _ = _latest(chat)
    _answer(chat, "change_time", target="N서울타워", minutes=30)
    body = _say(chat, "N서울타워 30분 늦춰줘", "edit-shift")
    after, items = _latest(chat)
    assert body["status"] == "adjusted" and after == before + 1, body
    tower = items["N서울타워"]
    assert (_hm(tower.starts_at), _hm(tower.ends_at)) == ("15:30", "17:00"), body
    assert "시각을 옮겼어요" in body["answer"] and "15:30~17:00" in body["answer"], body


def test_a_stop_is_moved_to_the_time_said(chat):
    _answer(chat, "change_time", target="N서울타워", anchor_kind="time", anchor_time="17:00", at_day="none")
    body = _say(chat, "N서울타워 17시로 옮겨줘", "edit-at")
    _, items = _latest(chat)
    tower = items["N서울타워"]
    assert body["status"] == "adjusted" and (_hm(tower.starts_at), _hm(tower.ends_at)) == ("17:00", "18:30"), body


def test_a_stop_is_removed(chat):
    before, _ = _latest(chat)
    _answer(chat, "remove_item", target="N서울타워")
    body = _say(chat, "N서울타워 일정 빼줘", "edit-remove")
    after, items = _latest(chat)
    assert body["status"] == "adjusted" and after == before + 1, body
    assert "N서울타워" not in items and "일정에서 뺐어요" in body["answer"], body


def test_a_stop_is_pinned_and_unpinned(chat):
    _answer(chat, "lock_item", target="인사동")
    body = _say(chat, "인사동 고정해줘", "edit-lock")
    _, items = _latest(chat)
    assert body["status"] == "adjusted", body
    assert items["인사동"].locked or (items["인사동"].detail or {}).get("customer_pinned"), body
    _answer(chat, "unlock_item", target="인사동")
    body = _say(chat, "인사동 고정 풀어줘", "edit-unlock")
    _, items = _latest(chat)
    assert body["status"] == "adjusted", body
    assert not (items["인사동"].locked or (items["인사동"].detail or {}).get("customer_pinned")), body


def test_a_named_place_is_found_and_the_stop_changes_to_it(chat):
    """「인사동 대신 덕수궁 가자」 — 전에는 다른 안만 보이고 「바로 바꾸는 기능은 아직 없어요」였다(10-14 실서버 「창덕궁」)."""
    before, _ = _latest(chat)
    _answer(chat, "apply_change", target="인사동", destination_text="덕수궁", change_scope="place")
    body = _say(chat, "인사동 대신 덕수궁 가자", "edit-named")
    after, items = _latest(chat)
    assert body["status"] == "adjusted" and after == before + 1, body
    assert body["decision"]["action"] == "replace_named", body
    assert "덕수궁" in items and "인사동" not in items, body
    assert (items["덕수궁"].place or {}).get("name") == "덕수궁"
    assert "아직 없어" not in body["answer"] and "말씀하신 곳으로 바꿨어요" in body["answer"], body


def test_a_named_place_that_is_not_found_changes_nothing_and_offers_choices(chat):
    """말한 이름으로 장소를 한 곳 찾지 못하면(모르는 이름 · 「다른 식당」 같은 설명) 바꾸지 않고, 찾지 못했다고 밝힌 뒤 다른 안을 보인다."""
    before, _ = _latest(chat)
    _answer(chat, "apply_change", target="인사동", destination_text="없는궁궐이름", change_scope="place")
    body = _say(chat, "인사동 대신 없는궁궐이름 가자", "edit-named-missing")
    after, _ = _latest(chat)
    assert after == before and body["status"] != "adjusted", body
    assert body["decision"]["action"] == "propose_alternatives", body
    assert body["decision"]["raw"]["named_destination"]["found"] is False, body
    assert body["answer"].startswith("말씀하신 「없는궁궐이름」을(를) 장소 목록 · 관광 정보 · 지도에서 한 곳으로 찾지 못해"), body
    with get_connection() as conn, conn.cursor() as cur:      # 수정 접수를 열지 않았다 — 웹 「일정 수정」을 막지 않는다
        cur.execute("SELECT count(*) FROM trip_intakes WHERE reopen_trip_id=%s AND status='review'", (chat["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 0


def test_a_new_place_is_added_after_a_stop(chat):
    before, _ = _latest(chat)
    _answer(chat, "add_item", destination_text="덕수궁", anchor_kind="item", anchor="N서울타워", relation="after")
    body = _say(chat, "N서울타워 다음에 덕수궁 넣어줘", "edit-add")
    after, items = _latest(chat)
    assert body["status"] == "adjusted" and after == before + 1, body
    added = items["덕수궁"]
    assert (_hm(added.starts_at), _hm(added.ends_at)) == ("16:40", "17:40") and added.kind == "activity", body
    assert "일정에 넣었어요" in body["answer"], body


def test_an_add_without_a_time_or_anchor_asks_instead_of_guessing(chat):
    before, _ = _latest(chat)
    _answer(chat, "add_item", destination_text="덕수궁")
    body = _say(chat, "덕수궁 넣어줘", "edit-add-ask")
    after, _ = _latest(chat)
    assert after == before and body["status"] == "clarify" and "몇 시에" in body["answer"], body


def test_an_add_with_only_a_kind_of_place_asks_for_the_name_without_searching(chat):
    """★x600 실서버 확인(2026-10-15): 「오후 3시에 카페 하나 추가해줘」 — 「카페」를 장소 이름으로 찾으러 가 조회 한도만 쓰고 막혔다."""
    before, _ = _latest(chat)
    _answer(chat, "add_item", destination_text="카페", anchor_kind="time", anchor_time="15:00", at_day="none")
    body = _say(chat, "오후 3시에 카페 하나 추가해줘", "edit-add-kind")
    after, _ = _latest(chat)
    assert after == before and body["status"] == "clarify" and "장소 이름" in body["answer"], body


def test_two_stops_swap_their_order_without_overlapping(chat):
    _answer(chat, "swap_order", target="북촌한옥마을", anchor_kind="item", anchor="인사동")
    body = _say(chat, "북촌이랑 인사동 순서 바꿔줘", "edit-swap")
    _, items = _latest(chat)
    bukchon, insa = items["북촌한옥마을"], items["인사동"]
    assert body["status"] == "adjusted", body
    assert (_hm(insa.starts_at), _hm(insa.ends_at)) == ("10:00", "11:30"), body
    assert insa.ends_at <= bukchon.starts_at and _hm(bukchon.starts_at) == "12:00", body     # 겹치지 않는다


def test_a_stop_that_is_already_over_is_not_changed(chat):
    before, _ = _latest(chat)
    _answer(chat, "change_time", target="경복궁", minutes=30)
    body = _say(chat, "경복궁 30분 늦춰줘", "edit-past")
    after, _ = _latest(chat)
    assert after == before and body["status"] == "edit_refused" and "이미 지났거나" in body["answer"], body


def test_an_edit_can_be_rolled_back_like_any_other_change(chat):
    _answer(chat, "change_time", target="N서울타워", minutes=30)
    _say(chat, "N서울타워 30분 늦춰줘", "edit-undo-1")
    chat["decider"].structured = type(chat["decider"]).structured.__get__(chat["decider"])   # 기본 흉내(「원래대로」 → 되돌리기)
    body = _say(chat, "원래대로 돌려 줘", "edit-undo-2")
    _, items = _latest(chat)
    assert body["status"] == "rolled_back", body
    assert _hm(items["N서울타워"].starts_at) == "15:00", body


def test_an_open_edit_screen_with_unsaved_changes_is_not_overwritten(chat):
    from .test_trip_reopen import _edit, _index, _reopen

    view = _reopen({"client": chat["client"]}, chat["key"], chat["trip"]["trip_id"], chat["trip"]["version"])
    source = view["sources"][0]["source_id"]
    _edit({"client": chat["client"]}, chat["key"], view,
          {"source_id": source, "field": f"items[{_index(view, '인사동')}].starts_at", "value": "12:10"})
    before, _ = _latest(chat)
    _answer(chat, "remove_item", target="N서울타워")
    body = _say(chat, "N서울타워 빼줘", "edit-screen-open")
    after, _ = _latest(chat)
    assert after == before and body["status"] == "edit_refused" and "일정 수정 화면에서 고치던" in body["answer"], body


def test_several_stops_in_a_range_shift_together(chat):
    """「내일 오후 일정 전부 한 시간씩 밀어줘」 — 범위(조회 범위와 같은 계산)에 드는 일정을 한꺼번에 옮긴다."""
    before, _ = _latest(chat)
    _answer(chat, "change_time", minutes=60, query={"day": "tomorrow", "period": "afternoon", "kind": "all", "position": "all"})
    body = _say(chat, "내일 오후 일정 전부 한 시간씩 밀어줘", "edit-bulk")
    after, items = _latest(chat)
    assert body["status"] == "adjusted" and after == before + 1, body
    assert (_hm(items["인사동"].starts_at), _hm(items["N서울타워"].starts_at)) == ("13:00", "16:00"), body
    assert _hm(items["북촌한옥마을"].starts_at) == "10:00", body                 # 오전 일정은 그대로


def test_an_empty_edit_screen_left_open_is_not_shared_and_is_closed(chat):
    """`[2026-10-15 Codex 검토]` 웹 「일정 수정」을 열어만 두고(고친 값 없음) 채팅으로 고치면 — 그 접수를 같이 쓰지 않고 닫은 뒤 채팅 몫을 새로 연다."""
    from .test_trip_reopen import _reopen

    web = _reopen({"client": chat["client"]}, chat["key"], chat["trip"]["trip_id"], chat["trip"]["version"])
    _answer(chat, "remove_item", target="N서울타워")
    body = _say(chat, "N서울타워 빼줘", "edit-empty-screen")
    assert body["status"] == "adjusted", body
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM trip_intakes WHERE intake_id=%s", (web["intake_id"],))
        assert cur.fetchone()[0] == "closed"                                   # 웹이 연 빈 접수는 닫혔다(채팅이 쓰지 않았다)
        cur.execute("SELECT count(*) FROM trip_intakes WHERE reopen_trip_id=%s AND status='review'", (chat["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 0


def test_a_whole_range_shifts_even_when_the_model_gave_no_range(chat):
    """`[2026-10-15]` 재생에서 「오후 일정 전부 한 시간씩 밀어줘」 6문장이 모델이 범위(query)를 안 적어 되묻기로 끝났다 — 문장의 「전부 · 오후」로 범위를 만든다."""
    before, _ = _latest(chat)
    _answer(chat, "change_time", minutes=60)                        # 대상 · 범위 없음 — 문장에서만 읽는다
    body = _say(chat, "오후 일정 전부 한 시간씩 밀어줘", "edit-bulk-sentence")
    after, items = _latest(chat)
    assert body["status"] == "adjusted" and after == before + 1, body
    assert (_hm(items["인사동"].starts_at), _hm(items["N서울타워"].starts_at)) == ("13:00", "16:00"), body
    assert _hm(items["북촌한옥마을"].starts_at) == "10:00", body                 # 오전은 그대로


def test_a_single_stop_without_all_words_is_not_turned_into_a_range(chat):
    before, _ = _latest(chat)
    _answer(chat, "change_time", minutes=60)
    body = _say(chat, "일정 한 시간 밀어줘", "edit-not-range")
    after, _ = _latest(chat)
    assert after == before and body["status"] == "clarify" and "어느 일정을 옮길지" in body["answer"], body


def test_a_stop_the_customer_already_touched_can_still_be_replaced_or_removed_by_chat(chat):
    """★x600 실서버 확인(2026-10-15): 앞선 고치기 · 되돌리기가 일정에 붙인 「고객이 만진 일정」 표시가 다시 열면 고정으로 실려
    「경복궁 대신 창덕궁 가자」가 「고정한 일정이라 바꿀 수 없습니다」로 거절됐다. 고객이 지금 직접 말한 요청은 그 자동 표시를 풀고 처리한다."""
    _answer(chat, "change_time", target="인사동", minutes=10, anchor_kind="none")
    assert _say(chat, "인사동 10분 늦춰줘", "touch-shift")["status"] == "adjusted"
    _answer(chat, "apply_change", target="인사동", destination_text="덕수궁", change_scope="place")
    body = _say(chat, "인사동 대신 덕수궁 가자", "touch-named")
    _, items = _latest(chat)
    assert body["status"] == "adjusted" and "덕수궁" in items and "인사동" not in items, body
    _answer(chat, "remove_item", target="덕수궁")
    body = _say(chat, "덕수궁 빼줘", "touch-remove")
    _, items = _latest(chat)
    assert body["status"] == "adjusted" and "덕수궁" not in items, body


def test_a_stop_pinned_in_chat_is_replaced_when_the_customer_later_asks_for_it_directly(chat):
    """고객이 「고정해줘」로 고정한 일정도 같은 칸(`customer_pinned`)이라 자동 표시와 가를 수 없다 — 나중에 직접 말한 바꾸기 요청이 이긴다."""
    _answer(chat, "lock_item", target="인사동")
    assert _say(chat, "인사동 고정해줘", "pin-lock")["status"] == "adjusted"
    _answer(chat, "apply_change", target="인사동", destination_text="덕수궁", change_scope="place")
    body = _say(chat, "인사동 대신 덕수궁 가자", "pin-named")
    _, items = _latest(chat)
    assert body["status"] == "adjusted" and "덕수궁" in items and "인사동" not in items, body


def test_a_lodging_change_on_a_trip_without_lodging_does_not_change_another_stop(chat):
    """★x600 실서버 확인(2026-10-15): 「숙소 다른 데로 바꿔줘」 — 숙소 일정이 없는 여행에서 모델이 가까운 활동을 대상으로 골라 엉뚱한 곳으로 바꿔 버렸다."""
    before, items_before = _latest(chat)
    _answer(chat, "apply_change", target="인사동", change_scope="place")
    body = _say(chat, "숙소 다른 데로 바꿔줘", "lodging-none")
    after, items = _latest(chat)
    assert after == before and set(items) == set(items_before), body
    assert "숙소가 들어 있지 않아" in body["answer"], body


def test_a_stop_moves_to_the_meal_time_said_even_without_a_clock_time(chat):
    """★x600 실서버 확인(2026-10-15): 「내일 점심을 오늘 저녁으로 옮겨줘」 — 끼니 말만 있으면 시각을 못 읽어 「이미 되어 있어요」가 나왔다."""
    _answer(chat, "change_time", target="N서울타워", anchor_kind="none", at_day="none")
    body = _say(chat, "N서울타워를 내일 저녁으로 옮겨줘", "meal-evening")
    _, items = _latest(chat)
    tower = items["N서울타워"]
    assert body["status"] == "adjusted" and _hm(tower.starts_at) == "18:00", body


def test_a_stop_is_not_moved_to_a_day_outside_the_trip_and_the_trip_days_are_told(chat):
    before, _ = _latest(chat)
    _answer(chat, "change_time", target="N서울타워", anchor_kind="none", at_day="none")
    body = _say(chat, "N서울타워를 모레 저녁으로 옮겨줘", "meal-outside")
    after, _ = _latest(chat)
    assert after == before and "없는 날" in body["answer"] and "여행은" in body["answer"], body


def test_an_add_pushes_the_pinned_later_stops_instead_of_refusing(chat):
    """★`[2026-10-15 사용자 결정]` 넣기가 앞뒤 고정 일정에 막히면(B) 그날 고정 표시를 이 요청 동안만 풀고 뒤 일정을 밀어 자리를 만든 뒤 다시 고정한다."""
    for name, rid in (("북촌한옥마을", "push-lock-a"), ("인사동", "push-lock-b")):
        _answer(chat, "lock_item", target=name)
        assert _say(chat, f"{name} 고정해줘", rid)["status"] == "adjusted"
    before, _ = _latest(chat)
    _answer(chat, "add_item", destination_text="덕수궁", anchor_kind="item", anchor="북촌한옥마을", relation="after")
    body = _say(chat, "북촌한옥마을 다음에 덕수궁 넣어줘", "push-add")
    after, items = _latest(chat)
    assert body["status"] == "adjusted" and after == before + 1, body
    assert _hm(items["덕수궁"].starts_at) == "11:40", body
    assert _hm(items["인사동"].starts_at) > "12:00", body                       # 뒤 일정이 밀렸다
    for name in ("북촌한옥마을", "인사동"):                                      # 고정은 그대로
        assert items[name].locked or (items[name].detail or {}).get("customer_pinned"), (name, body)


def test_the_open_slot_text_is_found_when_nothing_can_make_room():
    """C: 자리를 못 만들면 빈 시간을 찾아 「이 시각에 넣을까요」로 안내한다 — 빈 시간이 아예 없으면 그렇게 말한다."""
    from types import SimpleNamespace

    from app.domains.travel_ops.components.conversation.chat_edit import EditOp, _no_room_text

    def stop(title, start, end):
        return SimpleNamespace(kind="activity", title=title, starts_at=datetime.fromisoformat(f"2026-10-16T{start}").replace(tzinfo=KST),
                               ends_at=datetime.fromisoformat(f"2026-10-16T{end}").replace(tzinfo=KST))
    now = datetime.fromisoformat("2026-10-15T14:00").replace(tzinfo=KST)
    op = EditOp("add", date="2026-10-16", starts_at="11:40", ends_at="12:40", place_name="덕수궁", title="덕수궁")
    gappy = [stop("가", "10:00", "11:30"), stop("나", "12:00", "13:30"), stop("다", "16:30", "18:00")]
    text = _no_room_text([op], gappy, now)
    assert "「덕수궁」" in text and "13:45" in text and "덕수궁 넣어줘" in text, text           # 13:30 끝 + 이동 15분
    packed = [stop("가", "08:00", "11:30"), stop("나", "12:00", "21:30")]
    assert "빈 시간이 없어" in _no_room_text([op], packed, now)


def test_a_lunch_stop_named_as_a_palace_becomes_that_palace_not_a_restaurant_with_its_name(chat):
    """★x600 실서버 확인(2026-10-15): 식사 일정에 「덕수궁」이라고만 말하면 식당에서 찾아 「탁사발두부공방 덕수궁점」으로 바뀌었다 — 이름으로 찾아 그 종류(활동)로 맞춘다."""
    from .test_trip_reopen import TOMORROW, _h as _hh, _item, _place

    body = {"request_id": "meal-trip", "title": "점심 시험", "locale": "ko", "party_size": 2, "constraints": {},
            "places": [_place("bc", "북촌한옥마을", 37.5826, 126.9836), {**_place("mj", "미진", 37.5712, 126.9790), "kind": "dining"},
                       _place("is", "인사동", 37.5740, 126.9850), _place("ds", "덕수궁", 37.5658, 126.9751)],
            "items": [_item(1, "activity", "북촌한옥마을", "bc", TOMORROW, "10:00", "11:30"),
                      _item(2, "dining", "미진", "mj", TOMORROW, "12:00", "13:00"),
                      _item(3, "activity", "인사동", "is", TOMORROW, "14:00", "15:30")]}
    response = chat["client"].post("/v1/web/trips", json=body, headers=_hh(chat["key"]))
    assert response.status_code == 201, response.text
    chat = {**chat, "trip": response.json()}
    _answer(chat, "apply_change", target="미진", destination_text="덕수궁", change_scope="place")
    said = _say(chat, "점심 대신 덕수궁 가자", "meal-named")
    _, items = _latest(chat)
    assert said["status"] == "adjusted" and "덕수궁" in items and "미진" not in items, said
    assert items["덕수궁"].kind == "activity", items["덕수궁"].kind


def test_the_day_word_in_the_sentence_beats_the_models_day_when_it_gave_a_clock_time(chat):
    """★x600 실서버 확인(2026-10-15): 「모레 점심으로 옮겨줘」를 모델이 12:00 · 1일차로 읽어 여행 안의 날로 옮겨 버렸다 — 날은 문장의 말이 이긴다."""
    before, _ = _latest(chat)
    _answer(chat, "change_time", target="N서울타워", anchor_kind="time", anchor_time="12:00", at_day="d1")
    body = _say(chat, "N서울타워를 모레 점심으로 옮겨줘", "meal-day-word")
    after, _ = _latest(chat)
    assert after == before and "없는 날" in body["answer"], body
