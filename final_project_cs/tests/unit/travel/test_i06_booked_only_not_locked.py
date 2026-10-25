"""I06 잔여 — 예약 사실(booked) 인용은 고정(locked) 근거가 될 수 없다.

계약: D-020 「오전 정정 A」 — 보호 대상은 고객이 「변경 안 할 일정」으로 고른 항목뿐이고 예약·결제 여부는 보지 않는다.
D-025 — 모델이 읽고 분류하며, 코드는 원문 인용을 확인 · 저장만 한다. 같은 원문 조각이 규칙이 읽은 예약 사실의 근거이면
그 조각은 「고정 요청」의 독립 근거가 아니므로 locked 값 줄을 만들지 않고 버린 수를 `reading.agent.dropped.locked_booking` 에 센다.

합성 원문(SYN- 예약번호)만 쓴다. 모델 호출 · DB · 네트워크 없음(가짜 reader).
"""
from datetime import date
import hashlib
import json

import pytest

from app.domains.travel_ops.components.intake import agent_read
from app.domains.travel_ops.components.intake.assemble import assemble, collect
from app.domains.travel_ops.components.intake.pipeline import read_source

BOOKED = "2030-01-02 서울 2명, 19:00~20:30 명동난타극장 예약 완료, 예약번호 SYN-KY-20931."
TODAY = date(2029, 12, 20)


class Reader:
    model = "i06-booked-fixture"

    def __init__(self, items):
        self.items = items

    def structured(self, system, user, schema, *, num_predict=160):
        return {"guard": {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None},
                "pieces": [], "items": self.items, "moves": [], "conditions": [], "preferences": [], "gaps": [],
                "missing": [], "trip": {"party_size": 2, "days": None, "nights": None}}


def _item(place="명동난타극장", **extra):
    return {"place_quote": place, "day": 1, "date": "2030-01-02", "date_quote": "2030-01-02",
            "start": "19:00", "end": "20:30", "time_quote": "19:00~20:30", "kind": "activity", **extra}


def _run(items, text):
    claims = read_source(text, today=TODAY, agent=Reader(items), agent_mode="on")
    src = [{"source_id": "syn", "position": 0, "transcript": text}]
    tagged = [{**c, "source_id": "syn"} for c in claims]
    return claims, assemble(intake_id="syn", revision=1, sources=src, claims=tagged), collect(sources=src, claims=tagged)


def _claims(claims, field):
    return [c for c in claims if c["field"] == field]


def _agent(claims):
    return next(c["value"] for c in claims if c["field"] == "reading.agent")


# --- RED 대상: 예약 사실 인용 → 고정 불가 -------------------------------------------------

@pytest.mark.parametrize("quote", ["예약 완료", "예약번호 SYN-KY-20931", "SYN-KY-20931", "명동난타극장 예약 완료"])
def test_booked_only_quote_cannot_ground_lock(quote):
    claims, got, rows = _run([_item(locked=True, locked_quote=quote)], BOOKED)
    assert _claims(claims, "items[0].booked")[0]["value"] is True          # 예약 사실은 그대로 남는다
    assert _claims(claims, "items[0].locked") == []
    assert "customer_pinned" not in got.body["items"][0]["detail"]
    assert rows.rows[0]["locked"] is False and rows.rows[0]["booked"] is True
    assert _agent(claims)["dropped"]["locked_booking"] == 1


def test_booking_quote_cannot_ground_explicit_not_locked_either():
    claims, got, _ = _run([_item(locked=False, locked_quote="예약 완료")], BOOKED)
    assert _claims(claims, "items[0].locked") == []
    assert _agent(claims)["dropped"]["locked_booking"] == 1


def test_mixed_booking_and_keep_quote_overlapping_booking_span_is_not_lock():
    """「예약 완료라 못 바꿔요」 — 인용이 예약 사실 조각을 포함하면 예약을 고정으로 등치한 것과 구별할 수 없다(부모 계약 질문 Q1)."""
    text = "2030-01-02 19:00~20:30 명동난타극장 예약 완료라 못 바꿔요."
    claims, got, _ = _run([_item(locked=True, locked_quote="예약 완료라 못 바꿔요")], text)
    assert _claims(claims, "items[0].booked")[0]["value"] is True
    assert _claims(claims, "items[0].locked") == []
    assert "customer_pinned" not in got.body["items"][0]["detail"]


def test_multi_item_booking_drop_does_not_remove_other_items_explicit_lock():
    text = "2030-01-02 19:00 명동난타극장 예약 완료.\n2030-01-02 15:00 덕수궁 이건 꼭 고정."
    items = [_item(locked=True, locked_quote="예약 완료", start="19:00", end=None, time_quote="19:00"),
             _item("덕수궁", locked=True, locked_quote="이건 꼭 고정", start="15:00", end=None, time_quote="15:00")]
    claims, got, rows = _run(items, text)
    by_title = {r["title"]: r for r in rows.rows}
    assert by_title["명동난타극장"]["locked"] is False and by_title["명동난타극장"]["booked"] is True
    assert by_title["덕수궁"]["locked"] is True
    locked = [c for c in claims if c["field"].endswith(".locked")]
    assert [(c["value"], c["evidence"]["text"]) for c in locked] == [(True, "이건 꼭 고정")]
    assert _agent(claims)["dropped"]["locked_booking"] == 1


# --- 회귀 보존: 명시 고정 · 고정하지마 · 빈/원문 밖 인용 ----------------------------------------

def test_explicit_keep_words_still_lock_with_quote():
    text = BOOKED + " 이건 꼭 고정."
    claims, got, _ = _run([_item(locked=True, locked_quote="이건 꼭 고정")], text)
    locked = _claims(claims, "items[0].locked")
    assert len(locked) == 1 and locked[0]["value"] is True and locked[0]["method"] == "llm_agent"
    ev = locked[0]["evidence"]
    assert text[ev["start"]:ev["end"]] == ev["text"] == "이건 꼭 고정"
    assert got.body["items"][0]["detail"]["customer_pinned"] is True
    assert _agent(claims)["dropped"].get("locked_booking", 0) == 0


def test_mixed_case_quote_outside_booking_span_keeps_model_judgement():
    """같은 문장이라도 모델이 예약 사실이 아닌 고객의 말(「못 바꿔요」)만 인용하면 코드는 의미를 재판정하지 않는다."""
    text = "2030-01-02 19:00~20:30 명동난타극장 예약 완료라 못 바꿔요."
    claims, _, _ = _run([_item(locked=True, locked_quote="못 바꿔요")], text)
    assert [c["value"] for c in _claims(claims, "items[0].locked")] == [True]


def test_explicit_do_not_lock_stays_false():
    text = BOOKED + " 이 일정은 고정하지 마세요."
    claims, got, rows = _run([_item(locked=False, locked_quote="고정하지 마세요")], text)
    assert [c["value"] for c in _claims(claims, "items[0].locked")] == [False]
    assert rows.rows[0]["locked"] is False
    assert "customer_pinned" not in got.body["items"][0]["detail"]


@pytest.mark.parametrize("quote", [None, "", "  ", "원문에 없는 고정 요청"])
def test_empty_or_outside_quote_cannot_lock(quote):
    claims, got, _ = _run([_item(locked=True, locked_quote=quote)], BOOKED + " 이건 꼭 고정.")
    assert _claims(claims, "items[0].locked") == []
    assert "customer_pinned" not in got.body["items"][0]["detail"]


# --- 프롬프트: 예약만 있는 항목의 예시 + 버전 등록 -----------------------------------------------

def test_prompt_example_shows_booked_item_with_null_lock_and_version_is_bumped():
    text = agent_read.system_for(date(2026, 10, 25))
    message = text.split("Message: ", 1)[1].split("\n", 1)[0]
    example = json.loads(text.split("Output: ", 1)[1])
    assert "예약 완료" in message
    booked_items = [i for i in example["items"] if "예약 완료" in message and i["place_quote"] in message]
    assert booked_items and all(i["locked"] is None and i["locked_quote"] is None for i in example["items"])
    assert "never use booking words as locked_quote" in agent_read.SYSTEM
    assert agent_read.PROMPT_VERSION == "intake.agent_read.v3-booked-not-locked"
    assert agent_read.PROMPT_HASH == hashlib.sha256(agent_read.SYSTEM.encode()).hexdigest()
