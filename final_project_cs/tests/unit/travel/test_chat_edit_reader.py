# -*- coding: utf-8 -*-
"""채팅 「넣기」는 계획서와 **같은 입구**다 — 메시지를 이해 에이전트(`intake.agent_read`)로 읽어 여러 곳 · 시각을 한 번에 넣는다. `[2026-10-16 D-025]`
모델 · DB 를 쓰지 않는다(가짜 이해 에이전트 답)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation.chat_edit import EditRefused, ops_for
from app.domains.travel_ops.components.conversation.decision_unit import Decision
from app.domains.travel_ops.components.intake import agent_read

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 20, 9, 0, tzinfo=KST)


@dataclass
class Stop:
    item_id: object
    seq: int
    kind: str
    title: str
    starts_at: datetime
    ends_at: datetime | None
    booking_id: object = None


ITEMS = [Stop(uuid4(), 1, "activity", "경복궁", datetime(2026, 10, 21, 10, 0, tzinfo=KST), datetime(2026, 10, 21, 12, 0, tzinfo=KST))]


def _decision(raw=None):
    return Decision(action="add_item", item=None, change=None, fact="", minutes=None, question="", raw=raw or {})


def _reader(answer):
    def read(text, today):
        return agent_read.ground(answer, text.splitlines())
    return read


def _it(place, day_date, start, kind="activity", quote=None):
    return {"place_quote": place, "day": None, "date": day_date, "date_quote": "내일" if day_date else None, "start": start, "end": None,
            "time_quote": quote or start, "kind": kind}


def test_a_message_with_several_stops_and_times_adds_each_of_them():
    message = "내일 2시에 북촌한옥마을, 6시에 광장시장 넣어줘"
    answer = {"items": [_it("북촌한옥마을", "2026-10-21", "14:00", quote="2시"), _it("광장시장", "2026-10-21", "18:00", "dining", quote="6시")]}
    ops, what = ops_for(_decision(), items=ITEMS, now=NOW, message=message, read_plan=_reader(answer))
    assert [(o.kind, o.title, o.date, o.starts_at, o.ends_at, o.item_kind) for o in ops] == [
        ("add", "북촌한옥마을", "2026-10-21", "14:00", "15:00", "activity"), ("add", "광장시장", "2026-10-21", "18:00", "19:00", "dining")]
    assert what == "북촌한옥마을 · 광장시장 넣기"


def test_a_stop_already_in_the_trip_or_without_a_time_is_not_added_by_the_reader():
    message = "경복궁 10시, 그리고 남산 어디쯤"
    answer = {"items": [_it("경복궁", "2026-10-21", "10:00", quote="10시"), _it("남산", None, None)]}
    # 이해 에이전트로 넣을 것이 없으면 지금 길(해석 칸)로 간다 — 시각이 없어 묻는다(경복궁은 이미 있어 넣지 않는다)
    with pytest.raises(EditRefused) as refused:
        ops_for(_decision({"destination_text": "남산"}), items=ITEMS, now=NOW, message=message, read_plan=_reader(answer))
    assert refused.value.code == "need_time"


def test_when_the_reader_fails_the_old_single_add_path_is_used():
    def broken(text, today):
        raise TimeoutError("slow")

    ops, what = ops_for(_decision({"destination_text": "북촌한옥마을", "anchor_time": "14:00"}), items=ITEMS, now=NOW,
                        message="북촌한옥마을 2시에 넣어줘", read_plan=broken)
    assert [(o.kind, o.title, o.starts_at) for o in ops] == [("add", "북촌한옥마을", "14:00")] and what == "북촌한옥마을 넣기"


def test_no_reader_keeps_the_old_behaviour():
    ops, _ = ops_for(_decision({"destination_text": "북촌한옥마을", "anchor_time": "14:00"}), items=ITEMS, now=NOW, message="북촌 넣어줘")
    assert [(o.kind, o.title, o.starts_at) for o in ops] == [("add", "북촌한옥마을", "14:00")]
