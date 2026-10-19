# -*- coding: utf-8 -*-
"""못 찾은 장소 — 후보 보이고 묻기 + 직접 고르기(수정 · 추가 모드로 넘기기). `[2026-10-19 사용자 결정]`

설계 `wiki/records/plans/2026-10-19_못찾은장소_후보와_직접고르기_설계.md`.
"""
from uuid import uuid4

from app.domains.travel_ops.components.conversation.chat_edit import EditOp, pick_card
from app.domains.travel_ops.components.intake import prefill
from app.domains.travel_ops.components.intake.gaps import Gap, Proposal


def _item(item_id: str, index: int, title: str, state: str = "unresolved") -> dict:
    return {"id": item_id, "source_id": "s1", "index": index, "title": title, "place_state": state, "kind": "dining"}


def _place_claim(index: int, *, blocked: list[str] | None) -> dict:
    evidence = {"source": "rule", "tried": ["places", "tour_api", "kakao"]}
    if blocked is not None:
        evidence["blocked"] = blocked
    return {"source_id": "s1", "field": f"items[{index}].place", "value": None, "evidence": evidence}


# ── 계획 읽기 — 먼저 채우기의 질문 ─────────────────────────────────

def test_unfound_line_question_offers_candidates_or_picking_instead_of_only_asking_for_a_name():
    out = prefill.check_gaps({"items": [_item("s1-0", 0, "을지로 그 집")]})
    assert [(g.kind, g.where) for g in out] == [("place_not_found", {"item": "s1-0"})]
    assert out[0].reason == "「을지로 그 집」을 지도에서 찾지 못했어요 — 후보에서 고르거나 직접 골라 주세요"


def test_question_card_points_at_the_item_and_carries_the_three_buttons():
    gap = Gap("place_not_found", {"item": "s1-2"}, "r", source="check", quote="을지로 그 집")
    p = Proposal(gap, "ask_customer", [{"question": gap.reason}])
    row = prefill._question(p, {"s1-2": _item("s1-2", 2, "을지로 그 집")}, set())
    assert row == {"kind": "place_not_found", "question": "「을지로 그 집」을 지도에서 찾지 못했어요 — 후보에서 고르거나 직접 골라 주세요",
                   "quote": "을지로 그 집", "item": "s1-2", "source_id": "s1", "index": 2, "mode": "change",
                   "actions": ["pick_candidate", "pick_myself", "no_place"], "blocked": False}


def test_question_says_the_lookup_was_blocked_when_retrying_did_not_help():
    gap = Gap("place_not_found", {"item": "s1-2"}, "r", source="check", quote="을지로 그 집")
    row = prefill._question(Proposal(gap, "ask_customer", [{"question": "r"}]), {"s1-2": _item("s1-2", 2, "을지로 그 집")}, {"s1-2"})
    assert row["blocked"] is True
    assert row["question"].startswith("「을지로 그 집」은 장소 조회가 막혀 다시 찾아봤지만 찾지 못했어요")


def test_other_questions_keep_their_plain_shape():
    gap = Gap("first_day_date", {"trip": "first_day_date"}, "여행 첫날이 언제인가요?")
    row = prefill._question(Proposal(gap, "ask_customer", [{"question": gap.reason}]), {}, set())
    assert row == {"kind": "first_day_date", "question": "여행 첫날이 언제인가요?", "quote": None}


# ── 계획 읽기 — 막힌 조회는 묻기 전에 한 번 더 ────────────────────

def test_blocked_lookup_is_retried_once_and_a_found_place_leaves_the_questions():
    items = [_item("s1-0", 0, "을지로 우래옥"), _item("s1-1", 1, "민수네 들르기")]
    claims = [_place_claim(0, blocked=["kakao:timeout"]), _place_claim(1, blocked=None)]
    gaps = prefill.check_gaps({"items": items})
    calls = []

    def refind(item, query):
        calls.append((item["id"], query))
        return True

    left, filled, still = prefill.retry_blocked(gaps, claims=claims, items=items, refind=refind)
    assert calls == [("s1-0", "을지로 우래옥")]                      # 막히지 않고 못 찾은 줄(지도에 없는 곳)은 다시 찾지 않는다
    assert [g.where["item"] for g in left] == ["s1-1"]
    assert filled[0]["item"] == "s1-0" and filled[0]["owner"] == "refind"
    assert "다시 찾아 채웠어요" in filled[0]["reason"]
    assert still == set()


def test_blocked_lookup_that_still_fails_stays_a_question_marked_blocked():
    items = [_item("s1-0", 0, "을지로 우래옥")]
    gaps = prefill.check_gaps({"items": items})
    left, filled, still = prefill.retry_blocked(gaps, claims=[_place_claim(0, blocked=["kakao:budget_exhausted"])], items=items,
                                                refind=lambda item, query: False)
    assert [g.kind for g in left] == ["place_not_found"] and filled == [] and still == {"s1-0"}


def test_blocked_query_reads_the_latest_place_claim_of_that_line_only():
    item = _item("s1-0", 0, "광장시장 그 집")
    older, newer = _place_claim(0, blocked=["kakao:timeout"]), _place_claim(0, blocked=None)
    assert prefill.blocked_query([older, newer], item) is None
    assert prefill.blocked_query([newer, older], item) == "광장시장 그 집"
    assert prefill.blocked_query([_place_claim(3, blocked=["kakao:timeout"])], item) is None


# ── 채팅 — 「직접 고르기」 카드 ────────────────────────────────────

def test_changing_to_an_unknown_place_hands_off_to_edit_mode_on_that_item():
    item_id = uuid4()
    ops = [EditOp("place", item_id=item_id, place_name="을지로 그 집", title="을지로 그 집")]
    card = pick_card(ops, "place_not_found", "말씀하신 곳을 … 찾지 못해 일정은 바꾸지 않았어요(「을지로 그 집」: 찾지 못함).")
    assert card == {"mode": "change", "item_id": str(item_id), "prefill": {}, "query": "을지로 그 집", "blocked": False,
                    "actions": ["pick_myself"]}


def test_adding_an_unknown_place_hands_off_to_the_add_form_with_only_what_the_customer_said():
    said_end = EditOp("add", date="2026-10-21", starts_at="19:00", ends_at="20:30", place_name="민수네", title="민수네",
                      item_kind="dining", end_said=True)
    card = pick_card([said_end], "place_not_found", "「민수네」")
    assert card["mode"] == "add" and card["item_id"] is None
    assert card["prefill"] == {"title": "민수네", "date": "2026-10-21", "starts_at": "19:00", "ends_at": "20:30", "kind": "dining"}

    default_end = EditOp("add", date="2026-10-21", starts_at="19:00", ends_at="20:00", place_name="민수네", title="민수네")
    card = pick_card([default_end], "place_not_found", "")
    assert card["prefill"] == {"title": "민수네", "date": "2026-10-21", "starts_at": "19:00"}   # 기본 60분 끝 · 모르는 종류는 싣지 않는다


def test_card_names_a_blocked_lookup_and_picks_the_op_the_refusal_named():
    ops = [EditOp("add", date="2026-10-21", starts_at="12:00", ends_at="13:00", place_name="경복궁", title="경복궁"),
           EditOp("add", date="2026-10-21", starts_at="15:00", ends_at="16:00", place_name="민수네", title="민수네")]
    card = pick_card(ops, "place_not_found", "지금 장소 조회가 잠시 막혀 찾지 못해 … 「민수네」")
    assert card["query"] == "민수네" and card["blocked"] is True


def test_no_card_for_other_refusals_or_when_nothing_was_read():
    ops = [EditOp("place", item_id=uuid4(), place_name="x", title="x")]
    assert pick_card(ops, "locked_item", "") is None
    assert pick_card([], "place_not_found", "") is None
    assert pick_card([EditOp("remove", item_id=uuid4())], "place_not_found", "") is None
