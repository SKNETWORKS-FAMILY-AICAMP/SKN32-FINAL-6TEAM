# -*- coding: utf-8 -*-
"""고객이 읽는 문장 — 요식 시연 흐름에서 화면에 그대로 보인 결함 셋. `[2026-10-16 화면 점검]`

①확인 화면의 장소 줄 「장소 정보 **정보로** 「서울 원조할머니 기름떡볶이」를 찾았어요」 — 요식 원장(`dining_ledger`)이 출처 이름표에 없어
  기본값 「장소 정보」 뒤에 「정보로」가 또 붙었다.
②묻는 알림의 `**바꾸지 않았어요.**` — 채팅 · 웹 알림은 마크다운을 그리지 않아 별표가 그대로 보였다.
③「문 닫았대」 신고로 연 질문이 「일정에 문제가 생겼어요」 — 원인(고객 신고)에 고객에게 보일 말이 없었다.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import review
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning.pending import Decision, proposal_notice

KST = ZoneInfo("Asia/Seoul")


def _row(title, source, *, needs_review=True):
    return {"title": title, "kind": "dining",
            "claims": {"place": {"needs_review": needs_review, "evidence": {"source": source}}}}


@pytest.mark.parametrize("source", ["dining_ledger", "something_new"])
def test_a_place_line_never_says_jeongbo_twice(source):
    line = review._place_line(_row("통인시장", source), "found",
                              {"name": "서울 원조할머니 기름떡볶이", "source": source})
    assert "정보 정보" not in line["text"], line
    assert "「서울 원조할머니 기름떡볶이」를 찾았어요" in line["text"], line


def _item():
    place = {"place_id": uuid4(), "name": "하동관 명동본점", "kind": "dining"}
    return Item(item_id=uuid4(), seq=1, kind="dining", title="하동관 명동본점", place_id=place["place_id"],
                starts_at=datetime(2026, 10, 20, 12, 34, tzinfo=KST), ends_at=datetime(2026, 10, 20, 13, 34, tzinfo=KST),
                place=place)


OPTIONS = [{"key": "a", "rank": 1, "name": "장수촌 풍천장어"}, {"key": "b", "rank": 2, "name": "이강순실비집"}]
CLOSED = [{"category": "customer_report", "type": "closed", "from": "하동관 명동본점",
           "message": "하동관 명동본점 오늘 문 닫았대", "evidence": "고객 신고"}]


@pytest.mark.parametrize("reason, safety", [("protected", False), ("safety_alert", True), ("ask_first", False)])
def test_an_asking_notice_has_no_markdown_stars(reason, safety):
    notice = proposal_notice(item=_item(), decision=Decision("ask", reason, "customer_pinned", safety),
                             causes=CLOSED, options=OPTIONS, proposal_id=uuid4())
    assert "**" not in notice["text"], notice["text"]
    assert "답이 없으면 원래 일정을 그대로 둡니다" in notice["text"]


def test_a_closed_report_says_what_the_customer_reported():
    from app.domains.travel_ops.components.itinerary.itinerary_changes import plan_fresh_alternate

    home = {"place_id": uuid4(), "name": "하동관 명동본점", "kind": "dining", "latitude": 37.56443, "longitude": 126.98502,
            "attributes": {"hours": ["07:00", "22:00"]}}
    other = {"place_id": uuid4(), "name": "명동교자 본점", "kind": "dining", "latitude": 37.5640, "longitude": 126.9853,
             "attributes": {"hours": ["07:00", "22:00"]}}
    item = Item(item_id=uuid4(), seq=1, kind="dining", title="하동관 명동본점", place_id=home["place_id"],
                starts_at=datetime(2030, 1, 1, 12, tzinfo=KST), ends_at=datetime(2030, 1, 1, 13, tzinfo=KST), place=home)
    plan = plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[item],
                                places=[home, other], item_id=item.item_id, message="하동관 명동본점 문 닫았대",
                                request_id="r1", reported_closed=True)
    notice = proposal_notice(item=item, decision=Decision("ask", "ask_first", None, False), causes=plan.causes,
                             options=OPTIONS, proposal_id=uuid4())
    assert "일정에 문제가 생겼어요" not in notice["text"], notice["text"]
    assert "닫았다고 알려 주셨어요" in notice["text"], notice["text"]
