# -*- coding: utf-8 -*-
"""일정 항목 짚기 **가르친 모델**의 제품 연결(`item_pointer.py` · `itinerary_team.set_item_pointer`). `[2026-10-07 사용자 지시]`

지키려는 것
 ①프롬프트는 가르칠 때와 같은 모양이다(오늘 날짜 + 번호 붙인 일정 + 고객 질문 + JSON 지시) — 모델 번호 → 항목 표가 맞다
 ②모델이 번호를 고르면 그 항목, `null` 이면 None 을 쓴다. 이동 항목을 고르면 None(낱말 규칙도 이동은 안 고른다)
 ③모델이 실패하면(HTTP 오류 · 형식 오류 · 목록 밖 번호) **옛 낱말 규칙으로 돌아가고**, 실패는 센다(조용히 넘기지 않는다)
 ④꺼져 있으면(`off`) 모델을 안 부른다. `shadow` 는 모델도 부르되 결과는 규칙으로 — 차이만 센다
 ⑤같은 (일정, 문장)은 한 번만 부른다(같은 요청 안에서 `mentioned_item` 이 여러 번 불려도 모델 호출은 한 번)

재현:  python -m pytest tests/unit/travel/test_item_pointer.py -v
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import item_pointer
from app.domains.travel_ops.components.conversation.item_pointer import OllamaItemPointer, build_prompt
from app.domains.travel_ops.instances._shared import itinerary_team

KST = ZoneInfo("Asia/Seoul")


def _item(seq, kind, title, day, hhmm, place=None):
    return SimpleNamespace(item_id=uuid4(), seq=seq, kind=kind, title=title, place={"name": place or title},
                           starts_at=datetime(2026, 10, day, int(hhmm[:2]), int(hhmm[3:]), tzinfo=KST))


ITEMS = [_item(1, "activity", "경복궁", 14, "10:10"), _item(2, "mobility", "지하철 이동", 14, "11:30"), _item(3, "dining", "금용문", 14, "12:00"),
         _item(4, "activity", "경희궁", 15, "09:30")]


class _Resp:
    def __init__(self, content=None, status=200):
        self.status_code, self._content = status, content
        self.text = str(content)

    def json(self):
        return {"message": {"content": self._content}}


class _Post:
    """Ollama 흉내 — 정해 둔 답을 돌려주고 받은 본문을 남긴다."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, url, payload):
        self.calls.append((url, payload))
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, Exception):
            raise a
        return a if isinstance(a, _Resp) else _Resp(a)


@pytest.fixture(autouse=True)
def _clean():
    for k in item_pointer.STATS:
        item_pointer.STATS[k] = 0
    yield
    itinerary_team.set_item_pointer(None)


def _pointer(post, mode="on"):
    return OllamaItemPointer(base_url="http://model.test", model="tripilot-pointer:e4b-ft", mode=mode, post=post)


def test_prompt_has_the_trained_shape():
    prompt, ordered = build_prompt(ITEMS, "경복궁 몇 시에 가요?", today=datetime(2026, 10, 13, 9, 0, tzinfo=KST))
    assert prompt.startswith("오늘은 2026-10-13 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n1. 1일차 10/14(수) 10:10 [activity] 경복궁 @ 경복궁\n")
    assert "\n4. 2일차 10/15(목) 09:30 [activity] 경희궁 @ 경희궁\n\n고객 질문: 경복궁 몇 시에 가요?\n\n" in prompt
    assert prompt.endswith('답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}')
    assert [i.title for i in ordered] == ["경복궁", "지하철 이동", "금용문", "경희궁"]


def test_model_number_maps_to_the_item_and_null_to_none():
    post = _Post(json.dumps({"item": 3}))
    got = _pointer(post)(ITEMS, "금용문 몇 시예요?")
    assert got is ITEMS[2]
    assert post.calls[0][0] == "http://model.test/api/chat"
    body = post.calls[0][1]
    assert body["model"] == "tripilot-pointer:e4b-ft" and body["think"] is False and body["options"]["temperature"] == 0
    assert [m["role"] for m in body["messages"]] == ["user"] and "고객 질문: 금용문 몇 시예요?" in body["messages"][0]["content"]
    assert _pointer(_Post(json.dumps({"item": None})))(ITEMS, "비트코인 시세") is None


def test_mobility_pick_is_none():
    assert _pointer(_Post(json.dumps({"item": 2})))(ITEMS, "지하철 몇 시에 타요?") is None


@pytest.mark.parametrize("answer", [json.dumps({"item": 9}), "그건 모르겠어요", json.dumps({"item": "셋째"}), _Resp("x", status=500), RuntimeError("연결 거부")])
def test_failure_falls_back_to_the_rule_and_is_counted(answer):
    assert _pointer(_Post(answer))(ITEMS, "경복궁 몇 시에 가요?") is NotImplemented
    assert item_pointer.STATS["failed"] == 1 and item_pointer.STATS["used"] == 0


def test_off_does_not_call_the_model():
    post = _Post(json.dumps({"item": 1}))
    assert _pointer(post, mode="off")(ITEMS, "경복궁 몇 시에 가요?") is NotImplemented
    assert post.calls == [] and item_pointer.STATS["calls"] == 0


def test_shadow_calls_the_model_but_keeps_the_rule_result():
    post = _Post(json.dumps({"item": 4}))
    got = _pointer(post, mode="shadow")(ITEMS, "경복궁 몇 시에 가요?", lambda: ITEMS[0])
    assert got is NotImplemented and len(post.calls) == 1
    assert item_pointer.STATS["shadow_diff"] == 1 and item_pointer.STATS["used"] == 0


def test_same_trip_and_sentence_calls_the_model_once():
    post = _Post(json.dumps({"item": 1}))
    p = _pointer(post)
    assert p(ITEMS, "경복궁 몇 시에 가요?") is ITEMS[0]
    assert p(ITEMS, "경복궁 몇 시에 가요?") is ITEMS[0]
    assert len(post.calls) == 1 and item_pointer.STATS["cache_hits"] == 1


def test_mentioned_item_uses_the_model_and_falls_back_to_words():
    from app.domains.travel_ops.components.itinerary.itinerary import Item

    stops = [Item(item_id=uuid4(), seq=n, kind=k, title=t, place_id=None, starts_at=datetime(2026, 10, 14, 10 + n, 0, tzinfo=KST), ends_at=None,
                  place={"name": t}) for n, (k, t) in enumerate([("activity", "경복궁"), ("dining", "금용문")], start=1)]
    assert itinerary_team.mentioned_item(stops, "경복궁 몇 시에 가요?") is stops[0]            # 모델 없음 — 낱말 규칙
    itinerary_team.set_item_pointer(_pointer(_Post(json.dumps({"item": 2}))))
    assert itinerary_team.mentioned_item(stops, "경복궁 몇 시에 가요?") is stops[1]            # 모델이 이긴다(on)
    itinerary_team.set_item_pointer(_pointer(_Post(RuntimeError("꺼짐"))))
    assert itinerary_team.mentioned_item(stops, "경복궁 몇 시에 가요?") is stops[0]            # 모델 실패 → 규칙


def test_register_from_settings_needs_the_model_name():
    assert item_pointer.register_from_settings(SimpleNamespace(ollama_pointer_model="", ollama_base_url="http://x")) is None
    assert itinerary_team._POINTER is None
    assert item_pointer.register_from_settings(SimpleNamespace(ollama_pointer_model="m", ollama_base_url="")) is None
