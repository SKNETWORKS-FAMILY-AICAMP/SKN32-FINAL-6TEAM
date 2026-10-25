"""`[2026-10-25 QA]` 화면에서 고른 일정(「국립중앙박물관에 대해 궁금한 점을 입력하세요」)에 묻는 말이 「어느 일정」 되묻기로 끝나지 않는다.

웹 채팅 막대는 고른 일정이 있으면 그 이름을 입력 안내에 쓰고 `item_id` 로 서버에 보낸다(`trip-chat.tsx`).
학습 E4B 는 이름 없는 이어 묻기(「운영시간 알려줘」 「거기 운영시간 알려줘」)를 `reference=previous` 로 적는다 —
앞 답 대상이 없으면 고객이 고른 일정이 있는데도 「가리키는 일정을 … 확인하지 못했어요」로 되물었다.
고른 일정은 고객이 보낸 구조화 값이고 현재 여행에서 확인된다. 앞 답 대상이 없을 때 이어 묻기의 대상으로만 쓴다
(문장이 이름 · 날짜 · 시각 · 끼니를 말했거나, 이름을 댄 일정 밖 장소면 쓰지 않는다).
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du, read_requests
from app.domains.travel_ops.components.conversation.fact_context import resolve

NOW = datetime(2031, 3, 10, tzinfo=timezone.utc)


def stop(name, seq, day=0, kind="activity"):
    return SimpleNamespace(item_id=uuid4(), title=name, kind=kind, seq=seq, detail={}, booking_id=None, locked=False,
                           starts_at=NOW + timedelta(days=day, hours=seq), ends_at=NOW + timedelta(days=day, hours=seq, minutes=50),
                           place={"name": name, "attributes": {}, "kind": kind})


def plan():
    return [stop("경복궁", 1), stop("토속촌 삼계탕", 2, kind="dining"), stop("국립중앙박물관", 3), stop("광장시장", 4, kind="dining")]


def read(fact, target="i3", reference="previous", text=""):
    # 실제 E4B 원출력(2026-10-25 실측)과 같은 칸 — 기준 칸은 비었다(`time_anchor.clean` 뒤 모양)
    return dict(fact=fact, target_item=target, reference=reference, origin_item="none", origin_text="", transport_mode="any",
                query=None, text=text, advice="", anchor_kind="none", anchor_item="none", anchor_time="", at_time="",
                at_day="none", relation="at", steps=1)


def render(items, request, message, selected, turns=()):
    decision = du.Decision("answer_fact", None, None, request["fact"], None, "", reads=[request])
    return read_requests.reply(decision, items=items, message=message, selected=selected, turns=list(turns), version=1,
                               now=NOW, context_now=NOW, ttl_seconds=1800, place_source=None)


def answered_about(result, target):
    outcome, basis, _ = result
    question = basis["questions"][0]
    return (question.get("item_id") == str(target.item_id) and question.get("unresolved") not in ("target", "anchor")
            and target.title in outcome["text"])


@pytest.mark.parametrize("message,target", [("운영시간 알려줘", "i3"), ("운영시간 알려줘", "none"),
                                            ("거기 운영시간 알려줘", "i3"), ("그거 자세히 알려줘", "none")])
def test_selected_stop_answers_a_subjectless_followup_without_previous_answer(message, target):
    items = plan()
    museum = items[2]
    fact = "detail" if "자세히" in message else "hours"
    result = render(items, read(fact, target), message, museum.item_id)
    assert answered_about(result, museum)
    assert "확인하지 못했어요" not in result[0]["text"]


def test_weather_followup_marked_previous_keeps_the_2026_10_18_contract():
    """`trip-chat-context.md` 2026-10-18 문맥 만료 보완 — weather/outdoor 의 reference=previous 는 유효한 앞 답 대상이 있어야 조회하고
    화면 선택으로 대신하지 않는다. 이번 수정은 그 계약을 바꾸지 않는다(바꿀지는 사용자 결정 사항)."""
    items = plan()
    museum = items[2]
    _, basis, _ = render(items, read("weather", "i3"), "거기 날씨 어때?", museum.item_id)
    assert basis["questions"][0].get("unresolved") == "target"


def test_selected_stop_answers_a_pointing_followup_the_model_also_bound_to_it():
    items = plan()
    museum = items[2]
    result = render(items, read("price", "i3"), "거기 입장료 얼마야?", museum.item_id)
    assert answered_about(result, museum)


def test_pointing_followup_the_model_did_not_bind_is_still_asked_back():
    """가리키는 말만 있고 모델이 대상을 고르지 않았으면 고른 일정으로 짐작하지 않는다(기존 되묻기 그대로)."""
    items = plan()
    museum = items[2]
    _, basis, _ = render(items, read("price", "none"), "거기 입장료 얼마야?", museum.item_id)
    assert basis["questions"][0].get("unresolved") == "target"


def test_selected_one_of_two_same_name_stops_answers_that_stop():
    items = plan() + [stop("국립중앙박물관", 2, day=1)]
    second = items[4]
    result = render(items, read("hours", "i5"), "국립중앙박물관 운영시간 알려줘", second.item_id)
    assert answered_about(result, second)


def test_two_same_name_stops_without_selection_still_ask():
    items = plan() + [stop("국립중앙박물관", 2, day=1)]
    _, basis, _ = render(items, read("hours", "i3"), "국립중앙박물관 운영시간 알려줘", None)
    assert basis["questions"][0]["unresolved"] == "target"


def test_selection_never_answers_a_named_place_outside_the_trip():
    items = plan()
    museum = items[2]
    outcome, basis, _ = render(items, read("hours", "none"), "롯데월드 운영시간 알려줘", museum.item_id)
    assert basis["questions"][0].get("item_id") != str(museum.item_id)
    assert museum.title not in outcome["text"]


def test_explicit_pointing_with_an_outside_name_does_not_borrow_the_selection():
    items = plan()
    museum = items[2]
    outcome, basis, _ = render(items, read("hours", "none", "explicit"), "그 롯데월드 운영시간 알려줘", museum.item_id)
    assert basis["questions"][0].get("item_id") != str(museum.item_id)


def test_a_valid_previous_answer_target_still_wins_over_the_selection():
    items = plan()
    palace, museum = items[0], items[2]
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(palace.item_id), "version": 1, "at": NOW.isoformat()}}}]
    result = render(items, read("hours", "none"), "거기 운영시간 알려줘", museum.item_id, turns)
    assert answered_about(result, palace)


def test_a_scoped_followup_does_not_borrow_the_selection():
    items = plan()
    museum = items[2]
    decision = du.Decision("answer_fact", None, None, "hours", None, "", reads=[read("hours", "none")])
    got, focus, _ = resolve(decision, items=items, message="내일 운영시간 알려줘", selected=museum.item_id,
                            turns=[], version=1, now=NOW, ttl_seconds=1800)
    assert got.item is None and focus is None


def test_chip_text_with_selected_stop_answers_that_stop():
    """「선택 일정」 칩이 보내는 문장 그대로(`askAbout`) — 이름이 하나로 잡혀 그 일정을 답한다(전부터 맞았다, 회귀 방지)."""
    items = plan()
    museum = items[2]
    message = "2031-03-10 03:00 국립중앙박물관 일정의 상세를 알려 주세요."
    result = render(items, read("detail", "i3", text=message), message, museum.item_id)
    assert answered_about(result, museum)


def test_resolve_reports_the_selection_as_its_source():
    items = plan()
    museum = items[2]
    decision = du.Decision("answer_fact", None, None, "hours", None, "", reads=[read("hours", "none")])
    got, focus, stale = resolve(decision, items=items, message="운영시간 알려줘", selected=museum.item_id,
                                turns=[], version=1, now=NOW, ttl_seconds=1800)
    assert got.item is museum and not stale
    assert focus["source"] == "selection" and focus["item_id"] == str(museum.item_id)


# ── 실제 E4B 원출력 모양(2026-10-25 실측 3/4): 고른 일정에 묻는 말에 기준 칸 = 고른 일정, 앞뒤 = before, 답 대상 = 고른 일정 ──
def e4b_read(fact, text, anchor_item="i3", target="i3", relation="before"):
    # `time_anchor.clean` 뒤 모양 — 원출력 anchor_kind=none 이어도 anchor_item 이 있으면 item 으로 올라간다
    return {**read(fact, target, text=text), "anchor_kind": "item" if anchor_item != "none" else "none",
            "anchor_item": anchor_item, "relation": relation, "origin_item": "i3"}


@pytest.mark.parametrize("fact,message", [("hours", "운영시간 알려줘"), ("detail", "자세히 알려줘"),
                                          ("hours", "거기 운영시간 알려줘"), ("price", "입장료 얼마야?"),
                                          ("hours", "국립중앙박물관 운영시간 알려줘")])
def test_selected_stop_is_not_replaced_by_its_neighbour_when_target_and_anchor_are_the_selection(fact, message):
    items = plan()
    museum, lunch = items[2], items[1]
    outcome, basis, _ = render(items, e4b_read(fact, message), message, museum.item_id)
    question = basis["questions"][0]
    assert question.get("item_id") == str(museum.item_id)
    assert lunch.title not in outcome["text"].split("\n")[0]
    assert question.get("relation_dropped", {}).get("reason") == "target_is_selected_stop"


def test_no_anchor_before_now_during_the_trip_does_not_answer_the_previous_stop_for_the_selection():
    items = plan()
    museum, lunch = items[2], items[1]
    decision = du.Decision("answer_fact", None, None, "hours", None, "", reads=[e4b_read("hours", "운영시간 알려줘", anchor_item="none")])
    during = NOW + timedelta(hours=3, minutes=20)
    outcome, basis, _ = read_requests.reply(decision, items=items, message="운영시간 알려줘", selected=museum.item_id, turns=[],
                                            version=1, now=during, context_now=NOW, ttl_seconds=1800, place_source=None)
    assert basis["questions"][0].get("item_id") == str(museum.item_id)
    assert lunch.title not in outcome["text"]


def test_a_real_before_question_without_the_selection_as_target_is_still_computed():
    """「그 전 일정」 — 모델이 답 대상을 비웠다(앞뒤 질문 약속대로). 고른 일정 바로 앞을 계산한다(기존 그대로)."""
    items = plan()
    museum, lunch = items[2], items[1]
    _, basis, _ = render(items, e4b_read("hours", "그 전 일정 운영시간 알려줘", target="none"), "그 전 일정 운영시간 알려줘", museum.item_id)
    assert basis["questions"][0].get("item_id") == str(lunch.item_id)


def test_named_before_question_without_selection_is_still_computed():
    items = plan()
    lunch = items[1]
    message = "국립중앙박물관 바로 앞 일정 운영시간 알려줘"
    _, basis, _ = render(items, e4b_read("hours", message, target="none"), message, None)
    assert basis["questions"][0].get("item_id") == str(lunch.item_id)


def test_next_stop_question_from_the_selection_still_answers_the_next_stop():
    """「다음 일정」 칩(`askNext`) — 고른 일정 바로 뒤를 답한다. 사실 종류가 앞뒤 그 자체라 손대지 않는다."""
    items = plan()
    museum, dinner = items[2], items[3]
    message = "국립중앙박물관 다음 일정을 알려 주세요."
    _, basis, _ = render(items, e4b_read("next", message, relation="after"), message, museum.item_id)
    assert basis["questions"][0].get("item_id") == str(dinner.item_id)
