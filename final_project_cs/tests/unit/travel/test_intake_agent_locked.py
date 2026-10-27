"""I06 — 고객이 원문에서 명시한 고정은 모델 판단 + 원문 인용으로만 locked 값 줄이 된다.

합성 I06 원문(SYN- 예약번호)만 쓴다. 모델 호출 · DB · 네트워크 없음(가짜 reader).
"""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake import agent_read
from app.domains.travel_ops.components.intake.assemble import assemble
from app.domains.travel_ops.components.intake.pipeline import read_source

I06 = "2030-01-02 서울 2명, 19:00~20:30 명동난타극장 예약 완료, 예약번호 SYN-KY-20931. 이 일정은 고정해 주세요."
TODAY = date(2029, 12, 20)


class Reader:
    model = "i06-locked-fixture"

    def __init__(self, item_extra, text=I06):
        self.item_extra = item_extra
        self.text = text
        self.schemas = []

    def structured(self, system, user, schema, *, num_predict=160):
        self.schemas.append(schema)
        item = {"place_quote": "명동난타극장", "day": 1, "date": "2030-01-02", "date_quote": "2030-01-02",
                "start": "19:00", "end": "20:30", "time_quote": "19:00~20:30", "kind": "activity", **self.item_extra}
        return {"guard": {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None},
                "pieces": [{"kind": "plan_item", "quote": "명동난타극장 예약 완료, 예약번호 SYN-KY-20931"}],
                "items": [item], "moves": [], "conditions": [], "preferences": [], "gaps": [], "missing": [],
                "trip": {"party_size": 2, "days": None, "nights": None}}


def _run(extra, text=I06):
    reader = Reader(extra, text)
    claims = read_source(text, today=TODAY, agent=reader, agent_mode="on")
    sid = "syn-i06"
    got = assemble(intake_id="syn-i06", revision=1,
                   sources=[{"source_id": sid, "position": 0, "transcript": text}],
                   claims=[{**c, "source_id": sid} for c in claims])
    return reader, claims, got


def _claim(claims, field):
    return next((c for c in claims if c["field"] == field), None)


def test_generation_schema_has_nullable_locked_slot_with_quote():
    # `[2026-10-27 G · I05]` 항목 스키마는 날짜 유무 두 갈래(`agent_read._dated_items`) — 모든 갈래에 같은 고정 칸이 있어야 한다
    item_schema = agent_read.SCHEMA["properties"]["items"]["items"]
    branches = item_schema["anyOf"] if "anyOf" in item_schema else [item_schema]
    assert branches
    for branch in branches:
        props = branch["properties"]
        assert props["locked"] == {"type": ["boolean", "null"]}
        assert props["locked_quote"] == {"type": ["string", "null"]}
        assert {"locked", "locked_quote"} <= set(branch["required"])


def test_i06_explicit_lock_reaches_claim_assemble_and_keeps_booking_date_time():
    reader, claims, got = _run({"locked": True, "locked_quote": "이 일정은 고정해 주세요"})
    # contract_correction(role-manager 이식): 원 시험은 날짜/시각 variant(anyOf) 패치가 있는 트리를 가정했다. 그 패치는 별도
    #   묶음(L05)이라 이 트리에는 없을 수 있다 — 보낸 스키마의 **모든** 항목 갈래에 locked·locked_quote 가 있어야 한다(의도 그대로).
    item_schema = reader.schemas[0]["properties"]["items"]["items"]
    branches = item_schema["anyOf"] if "anyOf" in item_schema else [item_schema]
    for sent in (branch["properties"] for branch in branches):
        assert "locked" in sent and "locked_quote" in sent
        assert {"locked", "locked_quote"} <= set(item_schema.get("required") or branches[0]["required"])
    locked = _claim(claims, "items[0].locked")
    assert locked is not None and locked["value"] is True and locked["method"] == "llm_agent"
    ev = locked["evidence"]
    assert I06[ev["start"]:ev["end"]] == ev["text"] == "이 일정은 고정해 주세요"
    assert _claim(claims, "items[0].booked")["value"] is True
    assert _claim(claims, "items[0].booking_no")["value"] == "SYN-KY-20931"
    item = got.body["items"][0]
    assert item["detail"]["customer_pinned"] is True
    assert item["detail"]["booking"]["booking_no"] == "SYN-KY-20931"
    assert item["starts_at"].startswith("2030-01-02T19:00") and item["ends_at"].startswith("2030-01-02T20:30")
    assert item["detail"]["intake"]["source_id"] == "syn-i06"


def test_booked_only_without_lock_mention_stays_unlocked():
    text = "2030-01-02 서울 2명, 19:00~20:30 명동난타극장 예약 완료, 예약번호 SYN-KY-20931."
    _, claims, got = _run({"locked": None, "locked_quote": None}, text)
    assert _claim(claims, "items[0].locked") is None
    assert _claim(claims, "items[0].booked")["value"] is True
    assert "customer_pinned" not in got.body["items"][0]["detail"]


def test_explicit_not_locked_is_carried_as_false():
    text = "2030-01-02 19:00 명동난타극장 예약 완료, 예약번호 SYN-KY-20931. 이 일정은 고정하지 마세요."
    _, claims, got = _run({"locked": False, "locked_quote": "고정하지 마세요", "time_quote": "19:00", "end": None}, text)
    locked = _claim(claims, "items[0].locked")
    assert locked is not None and locked["value"] is False
    assert "customer_pinned" not in got.body["items"][0]["detail"]


@pytest.mark.parametrize("extra", [
    {"locked": True, "locked_quote": None},                       # 인용 없음
    {"locked": True, "locked_quote": "꼭 고정해 주세요"},             # 원문에 없는 인용
    {"locked": "yes", "locked_quote": "이 일정은 고정해 주세요"},     # 잘못된 타입
])
def test_lock_without_valid_quote_is_unknown_not_permanent(extra):
    _, claims, got = _run(extra)
    assert _claim(claims, "items[0].locked") is None
    assert "customer_pinned" not in got.body["items"][0]["detail"]


def test_booked_is_not_promoted_to_locked_without_model_judgement():
    _, claims, _ = _run({})                                         # 옛 모양 응답(슬롯 없음)
    assert _claim(claims, "items[0].locked") is None


def test_review_source_rows_project_locked_and_booked_from_same_fixture():
    """review.build 는 assemble.collect 의 행에서 `locked` 를 투영한다(review.py `bool(r["locked"])`)."""
    from app.domains.travel_ops.components.intake.assemble import collect
    reader = Reader({"locked": True, "locked_quote": "이 일정은 고정해 주세요"})
    claims = read_source(I06, today=TODAY, agent=reader, agent_mode="on")
    got = collect(sources=[{"source_id": "syn-i06", "position": 0, "transcript": I06}],
                  claims=[{**c, "source_id": "syn-i06"} for c in claims])
    row = got.rows[0]
    assert (row["locked"], row["booked"], row["booking_no"], row["date"], row["start"], row["end"], row["source_id"]) == \
        (True, True, "SYN-KY-20931", "2030-01-02", "19:00", "20:30", "syn-i06")
