# -*- coding: utf-8 -*-
"""등록한 여행 채팅 「○○호텔 넣어 줘」 — 숙소면 종류(숙박 · 활동 · 식사)를 확인한다. `[2026-10-27 B 채팅 전수검사]`

☆사용자 보고: 등록 뒤 채팅으로 호텔을 넣으면 숙박이 아니라 액티비티로 들어간다. 원인(`chat_edit`):
  단일 넣기는 찾은 곳의 종류를 「식사가 아니면 활동」으로 정했고(숙소 찾기 `_resolve_lodging` 은 kind=activity · 분류 32 를 낸다),
  리더 넣기(`_read_adds`)도 이해 에이전트가 lodging 으로 읽은 것을 activity 로 바꿨다.
계약(호텔 줄 — 접수와 같다, Codex 검토 codex/q1.out):
  ①넣을 곳이 숙소(분류 32)면 원문 말이 종류를 **하나로** 정할 때만 그 종류로 넣는다(`pipeline._said_kinds` — 접수와 같은 말). 리더가 읽은
    종류가 있으면 그것과도 같아야 한다(리더 단독으로 확정하지 않는다).
  ②아니면 넣지 않고 되묻는다(`need_kind`, 선택지 셋). 선택지 문장을 그대로 누르면 **모델 없이** 고른 종류로 넣는다(`kind_choice`).
  ③숙박의 끝(체크아웃)은 수정 접수 조립의 숙박 규칙(`assemble._stays`, 체크아웃 규칙 채움)이 등록과 같게 정한다 — 새 일정 계약이 끝 칸을
    요구해 같은 날 끝을 보내지만 조립이 다시 정한다(정상 입구 시험 `tests/e2e/test_chat_add_lodging_kind_web.py` 가 다음 날 11:00 을 본다).
  ④숙소가 아닌 곳은 지금 그대로(찾은 곳의 종류).
모델 · DB 를 쓰지 않는다.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import chat_edit
from app.domains.travel_ops.components.conversation.chat_edit import EditOp, EditRefused, ops_for
from app.domains.travel_ops.components.conversation.decision_unit import Decision
from app.domains.travel_ops.components.intake import agent_read, pipeline, places, reopen, reopen_commit

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2031, 3, 10, 9, 0, tzinfo=KST)
HOTEL = places.Resolved("resolved", "tour_api", "롯데호텔 서울", "롯데호텔 서울", "activity", 37.565, 126.981, content_type_id="32")
MUSEUM = places.Resolved("resolved", "tour_api", "국립중앙박물관", "국립중앙박물관", "activity", 37.52, 126.98, content_type_id="14")


@dataclass
class Stop:
    item_id: object
    seq: int
    kind: str
    title: str
    starts_at: datetime
    ends_at: datetime | None
    booking_id: object = None
    locked: bool = False
    detail: dict | None = None
    place: dict | None = None


ITEMS = [Stop(uuid4(), 1, "activity", "경복궁", datetime(2031, 3, 11, 10, 0, tzinfo=KST), datetime(2031, 3, 11, 12, 0, tzinfo=KST),
              detail={})]


def _add_decision(**raw):
    return Decision(action="add_item", item=None, change=None, fact="", minutes=None, question="",
                    raw={"anchor_kind": "time", "at_day": "d1", **raw})


def _world(monkeypatch, *, found, ops):
    """`chat_edit._run_locked` 의 경계만 바꾼다 — 고친 값(`pipeline.edit` 의 edits)과 찾기 호출을 적는다."""
    intake_id, seen = uuid4(), {"edits": [], "resolved": []}
    store = SimpleNamespace(latest=lambda conn, trip_id: ({"version": 4}, list(ITEMS)))

    @contextmanager
    def connect():
        yield None
    monkeypatch.setattr(reopen, "open_for_trip", lambda conn, **kw: (intake_id, False))
    monkeypatch.setattr(chat_edit, "_revision", lambda conn, tenant, intake: 1)
    monkeypatch.setattr(pipeline, "_claims", lambda conn, tenant, intake, revision: [])
    monkeypatch.setattr(pipeline, "_sources", lambda conn, tenant, intake: [{"source_id": "s1"}])
    monkeypatch.setattr(pipeline, "_our_places", lambda conn, tenant, trip_id=None: [])
    monkeypatch.setattr(reopen, "origins", lambda claims: {("s1", 0): ITEMS[0].item_id})
    monkeypatch.setattr(reopen, "_policy_locked", lambda i: False)

    def resolve(name, **kw):
        seen["resolved"].append(name)
        return found

    monkeypatch.setattr(places, "resolve", resolve)

    def edit(conn, **kw):
        seen["edits"].append(kw["edits"])
        return 2
    monkeypatch.setattr(pipeline, "edit", edit)
    monkeypatch.setattr(pipeline, "view", lambda conn, **kw: None)
    monkeypatch.setattr(pipeline, "draft", lambda conn, **kw: ("review", None, SimpleNamespace(problems=[])))
    monkeypatch.setattr(reopen, "session", lambda conn, **kw: {"trip_id": "t", "version": 4, "frozen_item_ids": []})
    monkeypatch.setattr(pipeline, "rejudge", lambda *a, **k: None)
    monkeypatch.setattr(reopen_commit, "commit", lambda **kw: (5, True, SimpleNamespace()))
    monkeypatch.setattr(pipeline, "mark_confirmed", lambda conn, **kw: None)
    monkeypatch.setattr(reopen, "cancel", lambda conn, **kw: seen.setdefault("cancel", 0))

    def run():
        return chat_edit._run_locked(store=store, connect=connect, tenant="unit", customer_id=uuid4(), trip_id=uuid4(),
                                     base_version=4, ops=ops, lookups=lambda: (None, None, None), now=NOW, cause_extra=None)
    return run, seen


def _fields(batch):
    return {e["field"].split(".", 1)[1]: e["value"] for e in batch if e["field"].startswith("items[1].")}


# ── ① · ② 단일 넣기 ──────────────────────────────────────────────
def test_a_hotel_added_by_chat_without_a_kind_word_is_asked_back_not_added_as_an_activity(monkeypatch):
    ops, _ = ops_for(_add_decision(destination_text="롯데호텔 서울", anchor_time="15:00"), items=ITEMS, now=NOW,
                     message="1일차 3시에 롯데호텔 서울 넣어줘")
    run, seen = _world(monkeypatch, found=HOTEL, ops=ops)
    with pytest.raises(EditRefused) as refused:
        run()
    assert refused.value.code == "need_kind"
    assert seen["edits"] == []                                   # 아무것도 쓰지 않는다
    choices = refused.value.detail["choices"]
    assert [c["label"] for c in choices] == ["숙박", "활동", "식사"]
    assert all("롯데호텔 서울" in c["message"] for c in choices)
    offer = refused.value.detail["kind_offer"]
    assert offer["version"] == 4
    assert [o["message"] for o in offer["options"]] == [c["message"] for c in choices]
    assert [o["ops"][0]["item_kind"] for o in offer["options"]] == ["lodging", "activity", "dining"]


def test_a_hotel_added_with_a_check_in_word_is_added_as_a_stay(monkeypatch):
    ops, _ = ops_for(_add_decision(destination_text="롯데호텔 서울", anchor_time="15:00"), items=ITEMS, now=NOW,
                     message="1일차 3시에 롯데호텔 서울 체크인 넣어줘")
    run, seen = _world(monkeypatch, found=HOTEL, ops=ops)
    run()
    fields = _fields(seen["edits"][0])
    assert fields["kind"] == "lodging"
    assert fields["starts_at"] == "15:00" and fields["date"] == "2031-03-11"


def test_a_hotel_meal_said_in_the_message_is_added_as_a_meal(monkeypatch):
    ops, _ = ops_for(_add_decision(destination_text="롯데호텔 서울", anchor_time="08:00"), items=ITEMS, now=NOW,
                     message="1일차 8시에 롯데호텔 서울 조식 넣어줘")
    run, seen = _world(monkeypatch, found=HOTEL, ops=ops)
    run()
    assert _fields(seen["edits"][0])["kind"] == "dining"


def test_conflicting_kind_words_are_asked_back(monkeypatch):
    ops, _ = ops_for(_add_decision(destination_text="롯데호텔 서울", anchor_time="15:00"), items=ITEMS, now=NOW,
                     message="1일차 3시에 롯데호텔 서울 체크인하고 점심 넣어줘")
    run, seen = _world(monkeypatch, found=HOTEL, ops=ops)
    with pytest.raises(EditRefused) as refused:
        run()
    assert refused.value.code == "need_kind" and seen["edits"] == []


def test_a_place_that_is_not_lodging_keeps_the_found_kind(monkeypatch):
    ops, _ = ops_for(_add_decision(destination_text="국립중앙박물관", anchor_time="15:00"), items=ITEMS, now=NOW,
                     message="1일차 3시에 국립중앙박물관 넣어줘")
    run, seen = _world(monkeypatch, found=MUSEUM, ops=ops)
    run()
    fields = _fields(seen["edits"][0])
    assert fields["kind"] == "activity" and fields["ends_at"] == "16:00"


# ── 리더 넣기 ───────────────────────────────────────────────────
def _reader(answer):
    def read(text, today):
        return agent_read.ground(answer, text.splitlines())
    return read


def _it(place, day_date, start, kind, quote):
    return {"place_quote": place, "day": None, "date": day_date, "date_quote": "3월 11일", "start": start, "end": None,
            "time_quote": quote, "kind": kind}


def test_the_reader_lodging_reading_is_kept_and_confirmed_by_the_check_in_word(monkeypatch):
    message = "3월 11일 3시에 롯데호텔 서울 체크인"
    answer = {"items": [_it("롯데호텔 서울", "2031-03-11", "15:00", "lodging", "3시")]}
    ops, _ = ops_for(_add_decision(), items=ITEMS, now=NOW, message=message, read_plan=_reader(answer))
    assert [o.item_kind for o in ops] == ["lodging"]
    run, seen = _world(monkeypatch, found=HOTEL, ops=ops)
    run()
    assert _fields(seen["edits"][0])["kind"] == "lodging"


def test_the_reader_lodging_reading_alone_does_not_settle_the_kind(monkeypatch):
    message = "3월 11일 3시에 롯데호텔 서울"
    answer = {"items": [_it("롯데호텔 서울", "2031-03-11", "15:00", "lodging", "3시")]}
    ops, _ = ops_for(_add_decision(), items=ITEMS, now=NOW, message=message, read_plan=_reader(answer))
    run, seen = _world(monkeypatch, found=HOTEL, ops=ops)
    with pytest.raises(EditRefused) as refused:
        run()
    assert refused.value.code == "need_kind" and seen["edits"] == []


def test_a_reader_activity_reading_of_a_hotel_is_not_silently_an_activity(monkeypatch):
    message = "3월 11일 3시에 롯데호텔 서울"
    answer = {"items": [_it("롯데호텔 서울", "2031-03-11", "15:00", "activity", "3시")]}
    ops, _ = ops_for(_add_decision(), items=ITEMS, now=NOW, message=message, read_plan=_reader(answer))
    run, seen = _world(monkeypatch, found=HOTEL, ops=ops)
    with pytest.raises(EditRefused) as refused:
        run()
    assert refused.value.code == "need_kind" and seen["resolved"] == ["롯데호텔 서울"]


# ── ② 고른 선택지 → 모델 없이 그 종류로 ───────────────────────────
def test_the_stored_choice_ops_add_the_chosen_kind_without_asking_again(monkeypatch):
    ops, _ = ops_for(_add_decision(destination_text="롯데호텔 서울", anchor_time="15:00"), items=ITEMS, now=NOW,
                     message="1일차 3시에 롯데호텔 서울 넣어줘")
    run, _ = _world(monkeypatch, found=HOTEL, ops=ops)
    with pytest.raises(EditRefused) as refused:
        run()
    stay = refused.value.detail["kind_offer"]["options"][0]
    decision = Decision("add_item", None, None, "none", None, "",
                        raw={"source": "kind_choice", "model_called": False, "ops": stay["ops"]})
    again, what = ops_for(decision, items=ITEMS, now=NOW, message=stay["message"])
    assert [(o.kind, o.item_kind, o.kind_confirmed) for o in again] == [("add", "lodging", True)]
    run2, seen2 = _world(monkeypatch, found=HOTEL, ops=again)
    run2()
    assert _fields(seen2["edits"][0])["kind"] == "lodging"


def test_kind_choice_matches_only_the_exact_offered_message_on_the_same_version():
    from app.domains.travel_ops.components.conversation import kind_choice

    offer = {"version": 4, "options": [{"message": "롯데호텔 서울 숙박으로 넣어 줘", "label": "숙박",
                                        "ops": [{"kind": "add", "place_name": "롯데호텔 서울", "item_kind": "lodging",
                                                 "kind_confirmed": True, "date": "2031-03-11", "starts_at": "15:00"}]}]}
    state = {"trip_outcome": {"kind_offer": offer}}
    assert kind_choice.pick(state, message="롯데호텔 서울 숙박으로 넣어 줘", version=4)["ops"][0]["item_kind"] == "lodging"
    assert kind_choice.pick(state, message="롯데호텔 서울 숙박으로 넣어줘", version=4) is None     # 정확히 같은 문장만
    assert kind_choice.pick(state, message="롯데호텔 서울 숙박으로 넣어 줘", version=5) is None     # 판이 바뀌었으면 다시 묻는다
    assert kind_choice.pick({}, message="롯데호텔 서울 숙박으로 넣어 줘", version=4) is None


# ── 같은 묶음 결함: 여러 곳 넣기 · 숙소로 바꾸기 ─────────────────────
def test_several_adds_are_sent_one_new_item_at_a_time_as_the_new_item_contract_requires(monkeypatch):
    """☆D-025 「2시에 북촌, 6시에 광장시장 넣어줘」 — 넣기 둘을 한 묶음에 실어 새 일정 계약(`pipeline._new_items`)이 늘
    「새 일정은 한 번에 하나씩 추가해 주세요」로 거절했다. 넣기마다 따로 보내고, 각 묶음은 그 계약을 지난다."""
    ops = [EditOp("add", date="2031-03-11", starts_at="14:00", ends_at="15:00", place_name="북촌한옥마을", title="북촌한옥마을",
                  item_kind="activity"),
           EditOp("add", date="2031-03-11", starts_at="18:00", ends_at="19:00", place_name="광장시장", title="광장시장", item_kind="dining")]
    run, seen = _world(monkeypatch, found=MUSEUM, ops=ops)
    run()
    adds = [b for b in seen["edits"] if any(".title" in e["field"] for e in b)]
    assert len(adds) == 2
    existing = {("s1", 0)}
    for batch in adds:
        triples = [(e["source_id"], e["field"], e["value"]) for e in batch]
        existing |= pipeline._new_items(triples, existing, {"s1"})        # 계약 그대로 — 거절하지 않는다
    assert existing == {("s1", 0), ("s1", 1), ("s1", 2)}


@pytest.mark.parametrize("kind", ["dining", "activity"])
def test_replacing_a_stop_with_a_hotel_keeps_the_stop_kind(monkeypatch, kind):
    """☆「점심을 롯데호텔 서울로 바꿔 줘」 — 숙소 찾기(kind=activity · 분류 32)를 따라 식사 일정이 활동이 됐다."""
    ITEMS[0].kind = kind
    try:
        run, seen = _world(monkeypatch, found=HOTEL, ops=[EditOp("place", item_id=ITEMS[0].item_id, place_name="롯데호텔 서울",
                                                                 title="롯데호텔 서울")])
        run()
    finally:
        ITEMS[0].kind = "activity"
    fields = [e["field"] for e in seen["edits"][0]]
    assert "items[0].kind" not in fields and "items[0].place" in fields
