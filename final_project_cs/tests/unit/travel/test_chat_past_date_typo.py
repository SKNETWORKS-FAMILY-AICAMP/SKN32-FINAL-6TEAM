# -*- coding: utf-8 -*-
"""채팅 수정이 지난 날짜 · 시각을 내면 바로 적용하지 않고 「혹시 오타 아닌가요?」로 되묻는다 — 가장 가까운 앞으로의 날짜를 버튼(choices)으로. `[2026-10-26 사용자 확정]`

모델 · DB 를 쓰지 않는다. 버튼은 기존 채팅 선택지 계약(`label` · `message` · 서버가 확인한 `item_id`, `choices_title`)을 그대로 쓴다."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import trip_desk
from app.domains.travel_ops.components.conversation.chat_edit import PAST_DATE_TITLE, EditRefused, ops_for
from app.domains.travel_ops.components.conversation.decision_unit import Decision
from app.domains.travel_ops.components.intake import agent_read

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 2, 11, 0, tzinfo=KST)


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
    place: object = None
    detail: dict | None = None


def _at(day, hour):
    return datetime(2030, 1, day, hour, 0, tzinfo=KST)


def _trip():
    return [Stop(uuid4(), 1, "activity", "창덕궁", _at(1, 10), _at(1, 12)),
            Stop(uuid4(), 2, "activity", "경복궁", _at(2, 12), _at(2, 14)),
            Stop(uuid4(), 3, "activity", "남산", _at(3, 15), _at(3, 17))]


def _start(item, time, at_day="none"):
    return Decision(action="change_time", item=item, change=None, fact="none", minutes=None, question="",
                    raw={"time_edit": {"boundary": "start", "scope": "item", "time": time, "duration_minutes": 0, "cascade": False,
                                       "continue_previous": False, "evidence": time}, "at_day": at_day})


def test_moving_to_a_past_trip_day_asks_if_it_is_a_typo_with_the_nearest_future_days():
    items = _trip()
    with pytest.raises(EditRefused) as caught:
        ops_for(_start(items[1], "10:00", at_day="d1"), items=items, now=NOW)
    refused = caught.value
    assert refused.code == "time_in_past"
    assert refused.message.startswith(PAST_DATE_TITLE) and "옮기지 않았어요" in refused.message
    # 1일차 · 2일차 10:00 은 지났다(지금 2일차 11:00) — 남은 여행 날짜 중 같은 시각이 앞으로인 날만
    assert refused.detail["choices_title"] == PAST_DATE_TITLE
    assert refused.detail["choices"] == [{"label": "1월 3일(목) 10:00", "message": "경복궁 3일차(1월 3일) 10:00으로 옮겨줘",
                                          "item_id": str(items[1].item_id)}]


def test_a_past_clock_today_also_offers_the_nearest_future_day_instead_of_applying():
    items = _trip()
    with pytest.raises(EditRefused) as caught:
        ops_for(_start(items[1], "10:30"), items=items, now=NOW)
    assert caught.value.code == "time_in_past" and items[1].starts_at.hour == 12
    assert [c["label"] for c in caught.value.detail["choices"]] == ["1월 3일(목) 10:30"]


def test_adding_at_a_past_time_asks_with_future_choices_and_no_item_id():
    items = _trip()
    add = Decision(action="add_item", item=None, change=None, fact="", minutes=None, question="",
                   raw={"destination_text": "덕수궁", "anchor_kind": "time", "anchor_time": "09:00", "at_day": "d1"})
    with pytest.raises(EditRefused) as caught:
        ops_for(add, items=items, now=NOW)
    refused = caught.value
    assert refused.code == "time_in_past" and "넣지 않았어요" in refused.message
    assert refused.detail["choices"] == [{"label": "1월 3일(목) 09:00", "message": "덕수궁 3일차(1월 3일) 09:00에 넣어줘"}]


def test_reader_adds_with_a_yearless_date_use_the_next_such_date_and_a_past_dated_add_is_asked():
    items = _trip()

    def reader(answer):
        return lambda text, today: agent_read.ground(answer, text.splitlines())

    def item(date_, quote, start, form="yearless", year_quote=None):
        return {"place_quote": "덕수궁", "day": None, "date": date_, "date_quote": quote, "year_quote": year_quote, "date_form": form,
                "start": start, "end": None,
                "time_quote": start, "kind": "activity"}

    # 연도 없는 「1월 3일」 — 모델이 연도를 붙이지 않은 값(`--01-03`)으로 바뀌어도 넣기가 죽지 않고 다가오는 1월 3일로 넣는다
    message = "1월 3일 18:00 덕수궁 넣어줘"
    answer = {"items": [item("2030-01-03", "1월 3일", "18:00")], "moves": [], "conditions": [], "preferences": [], "missing": [], "trip": {}}
    ops, _ = ops_for(Decision(action="add_item", item=None, change=None, fact="", minutes=None, question="", raw={}),
                     items=items, now=NOW, message=message, read_plan=reader(answer))
    assert [(o.kind, o.date, o.starts_at) for o in ops] == [("add", "2030-01-03", "18:00")]
    # 연도를 적은 지난 날짜 — 적용하지 않고 되묻는다
    message = "2030년 1월 1일 18:00 덕수궁 넣어줘"
    answer["items"] = [item("2030-01-01", "2030년 1월 1일", "18:00", "explicit_year", "2030년")]
    with pytest.raises(EditRefused) as caught:
        ops_for(Decision(action="add_item", item=None, change=None, fact="", minutes=None, question="", raw={}),
                items=items, now=NOW, message=message, read_plan=reader(answer))
    assert caught.value.code == "time_in_past"
    assert [c["label"] for c in caught.value.detail["choices"]] == ["1월 2일(수) 18:00", "1월 3일(목) 18:00"]


def test_trip_desk_turns_the_typo_question_into_a_clarify_reply_with_chat_choices(monkeypatch):
    items = _trip()
    store = SimpleNamespace(latest=lambda conn, trip_id: ({"customer_id": uuid4(), "version": 3}, items), tenant_id="t")
    desk = SimpleNamespace(store=store, _connect=lambda: nullcontext(None), _read_plan=lambda: None, _edit_lookups=None,
                           find_place=None)

    def never_run(**kwargs):
        raise AssertionError("지난 날짜는 저장 경로로 가지 않는다")

    monkeypatch.setattr("app.domains.travel_ops.components.conversation.chat_edit.run", never_run)
    out = trip_desk.TripDesk.edit(desk, trip_id=uuid4(), base_version=3, decision=_start(items[1], "10:00", at_day="d1"),
                                  now=NOW, message="경복궁 1일차 10시로 옮겨줘")
    assert out["status"] == "clarify" and out["reason"] == "time_in_past"
    assert out["choices_title"] == PAST_DATE_TITLE and out["choices"][0]["item_id"] == str(items[1].item_id)
    assert out["text"].startswith(PAST_DATE_TITLE)
